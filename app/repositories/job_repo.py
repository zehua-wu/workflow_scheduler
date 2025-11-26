# app/repositories/job_repo.py

from __future__ import annotations
from typing import List, Optional, Set
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import Job, JobStatus, Branch, JobType, Workflow


def get_job_by_id(db: Session, job_id: str) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()


def get_users_with_incomplete_jobs(db: Session) -> Set[str]:
    """
    help to check which users have incomplete jobs (PENDING or RUNNING)
    determine active users occupying slots
    """
    results = (
        db.query(Job.user_id)
        .filter(Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]))
        .distinct()
        .all()
    )
    return {r[0] for r in results}



def auto_cancel_blocked_jobs(db: Session) -> int:
    """
    Fail-fast rule:
        Scan all PENDING state jobs. If we find that its predecessor job in the same branch is FAILED or CANCELLED, 
        then mark the current job as CANCELLED as well.
    
    
    return the number of jobs that were auto-cancelled
    """
    # 1. fetch all PENDING jobs
    pending_jobs = db.query(Job).filter(Job.status == JobStatus.PENDING).all()
    canceled_count = 0

    for job in pending_jobs:
        # if current PENDING state job is the first job in the branch, skip
        if job.order_index == 0:
            continue

        # 2. find predecessor job
        prev_job = (
            db.query(Job)
            .filter(
                Job.branch_id == job.branch_id,
                Job.order_index == job.order_index - 1
            )
            .first()
        )

        # 3. cascade cancel
        if prev_job and prev_job.status in [JobStatus.FAILED, JobStatus.CANCELLED]:
            print(f"[AutoCancel] Job {job.id} cancelled because prev job {prev_job.id} is {prev_job.status}")
            job.status = JobStatus.CANCELLED
            job.finished_at = datetime.utcnow()
            canceled_count += 1
    
    if canceled_count > 0:
        db.commit()
    
    return canceled_count



def get_runnable_jobs(db: Session, allowed_user_ids: Set[str]) -> List[Job]:
    """
    Find all runnable jobs
    
    conditions:
    1. at PENDING state
    2. User is in Active Slots pool
    3. Branch inner order:
       - either the 1st job in the branch (order=0) or predecessor jobs are done
       
    """
    if not allowed_user_ids:
        return []

    pending_jobs = (
        db.query(Job)
        .filter(
            Job.status == JobStatus.PENDING,
            Job.user_id.in_(allowed_user_ids)
        )
        .order_by(asc(Job.created_at)) 
        .all()
    )

    runnable = []
    
    
    for job in pending_jobs:
        if job.order_index == 0:
            
            runnable.append(job)
        else:
            
            prev_job = (
                db.query(Job)
                .filter(
                    Job.branch_id == job.branch_id,
                    Job.order_index == job.order_index - 1
                )
                .first()
            )
            
            if prev_job and prev_job.status == JobStatus.SUCCEEDED:
                runnable.append(job)

    return runnable


def list_jobs_for_workflow(db: Session, workflow_id: str, user_id: str) -> List[Job]:
    return (
        db.query(Job)
        .filter(Job.workflow_id == workflow_id, Job.user_id == user_id)
        .order_by(asc(Job.branch_id), asc(Job.order_index))
        .all()
    )

def get_or_create_branch(db: Session, workflow_id: str, branch_name: str) -> Branch:
    branch = (
        db.query(Branch)
        .filter(Branch.workflow_id == workflow_id, Branch.name == branch_name)
        .first()
    )
    if branch:
        return branch

    import uuid
    branch = Branch(id=str(uuid.uuid4()), workflow_id=workflow_id, name=branch_name)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch

def create_job(db: Session, *, workflow_id: str, branch: Branch, user_id: str, job_type: JobType, input_path: str, output_path: str) -> Job:
    import uuid
    
    last_job = (
        db.query(Job)
        .filter(Job.branch_id == branch.id)
        .order_by(desc(Job.order_index))
        .first()
    )
    next_index = (last_job.order_index + 1) if last_job else 0

    job = Job(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        branch_id=branch.id,
        user_id=user_id,
        type=job_type,
        input_path=input_path,
        output_path=output_path,
        order_index=next_index,
        status=JobStatus.PENDING,
        progress=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job