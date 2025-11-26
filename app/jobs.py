# app/jobs.py

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Job, JobStatus, JobType
from .image_tasks import tissue_mask, instanseg_seg, preview_downsample


async def execute_job(db: Session, job: Job) -> None:
    
    if job.type == JobType.TISSUE_MASK:
        await tissue_mask.run_tissue_mask_job(db, job)

    elif job.type == JobType.INSTANTSEG_CELL_SEG:
        await instanseg_seg.run_instanseg_job(db, job)

    elif job.type == JobType.PREVIEW_DOWNSAMPLE:
        await preview_downsample.run_preview_job(db, job)

    else:
        print(f"[jobs] Unknown job type {job.type}, mark FAILED")
        job.status = JobStatus.FAILED
        db.commit()
        
        raise RuntimeError(f"Unknown job type {job.type}")
