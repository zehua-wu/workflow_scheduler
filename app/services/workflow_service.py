
# app/services/workflow_service.py

from __future__ import annotations
from sqlalchemy.orm import Session, joinedload
from app.models import Job, JobType, JobStatus, Branch
from app.repositories import workflow_repo, job_repo

def create_workflow_for_user(db: Session, user_id: str, name: str):
    return workflow_repo.create_workflow(db, user_id, name)

def add_job_to_workflow(
    db: Session,
    *,
    user_id: str,
    workflow_id: str,
    branch_name: str,
    job_type: JobType | str,
    input_path: str,
    output_path: str,
) -> Job:
    wf = workflow_repo.get_workflow_by_id(db, workflow_id, user_id)
    if not wf:
        raise ValueError("Workflow not found")

    if isinstance(job_type, str):
        job_type = JobType(job_type)

    branch = job_repo.get_or_create_branch(db, workflow_id, branch_name)

    job = job_repo.create_job(
        db=db,
        workflow_id=workflow_id,
        branch=branch,
        user_id=user_id,
        job_type=job_type,
        input_path=input_path,
        output_path=output_path,
    )
    return job

def get_workflow_status(db: Session, user_id: str, workflow_id: str):
    
    wf = workflow_repo.get_workflow_by_id(db, workflow_id, user_id)
    if not wf:
        raise ValueError("Workflow not found")

    jobs = (
        db.query(Job)
        .options(joinedload(Job.branch))
        .filter(Job.workflow_id == workflow_id, Job.user_id == user_id)
        .order_by(Job.branch_id, Job.order_index)
        .all()
    )

    if not jobs:
        return {
            "workflow_id": workflow_id,
            "status": "EMPTY",
            "progress": 0.0,
            "jobs": [],
        }

    
    progresses = [j.progress or 0.0 for j in jobs]
    avg_progress = sum(progresses) / len(jobs) if jobs else 0.0

    
    if any(j.status == JobStatus.RUNNING for j in jobs):
        wf_status = "RUNNING"
    elif any(j.status == JobStatus.PENDING for j in jobs):
        
        wf_status = "PENDING"
    elif any(j.status == JobStatus.FAILED for j in jobs):
        wf_status = "FAILED"
    elif any(j.status == JobStatus.CANCELLED for j in jobs):
        wf_status = "CANCELLED"
    else:
        wf_status = "SUCCEEDED"

    return {
        "workflow_id": workflow_id,
        "status": wf_status,
        "progress": avg_progress,
        "jobs": [
            {
                "job_id": j.id,
                "branch_id": j.branch_id,
                "branch_name": j.branch.name if j.branch else "unknown", 
                "order_index": j.order_index,
                "type": j.type.value if j.type else None,
                "status": j.status.value if j.status else None,
                "progress": j.progress or 0.0,
                "input_path": j.input_path,
                "output_path": j.output_path, 
            }
            for j in jobs
        ],
    }