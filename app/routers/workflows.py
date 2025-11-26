# app/routers/workflows.py

from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Body, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models import JobStatus, JobType
from app.repositories import workflow_repo, job_repo
from app.services import workflow_service

router = APIRouter()

class WorkflowCreateRequest(BaseModel):
    name: str

class JobCreateRequest(BaseModel):
    branch_name: str
    job_type: str
    input_path: str
    output_path: str

class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    created_at: str

# --- API Endpoints ---

@router.get("/workflows")
async def list_workflows(
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    wfs = workflow_repo.list_workflows(db, x_user_id)
    return [
        {
            "workflow_id": wf.id,
            "name": wf.name,
            "created_at": wf.created_at.isoformat()
        }
        for wf in wfs
    ]

@router.post("/workflows")
async def create_workflow(
    req: WorkflowCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    wf = workflow_service.create_workflow_for_user(db, x_user_id, req.name)
    return {"workflow_id": wf.id, "name": wf.name}

@router.get("/workflows/{workflow_id}")
async def get_workflow_details(
    workflow_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    try:
        status_data = workflow_service.get_workflow_status(db, x_user_id, workflow_id)
        return status_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/workflows/{workflow_id}/jobs")
async def add_job(
    workflow_id: str,
    req: JobCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    try:
        job = workflow_service.add_job_to_workflow(
            db=db,
            user_id=x_user_id,
            workflow_id=workflow_id,
            branch_name=req.branch_name,
            job_type=req.job_type,
            input_path=req.input_path,
            output_path=req.output_path
        )
        return {"job_id": job.id, "status": job.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    request: Request, # app.state
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    """
    取消任务 -> 触发 DB 更新 + 强制终止内存任务
    """
    job = job_repo.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.user_id != x_user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return {"msg": f"Job is already {job.status}, cannot cancel"}

    
    job.status = JobStatus.CANCELLED
    job.finished_at = datetime.utcnow()
    db.commit()

    scheduler = request.app.state.scheduler
    killed = await scheduler.kill_task(job_id)

    job_repo.auto_cancel_blocked_jobs(db)

    return {"status": "cancelled", "job_id": job_id, "killed_running_task": killed}