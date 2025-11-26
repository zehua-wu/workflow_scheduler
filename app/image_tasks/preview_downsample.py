import os
import asyncio
from sqlalchemy.orm import Session
from ..models import Job
from .utils import SmartSlide

async def run_preview_job(db: Session, job: Job) -> None:
    """
    生成 WSI 预览图 (Thumbnail)
    """
    if not os.path.exists(job.input_path):
        return

    job.total_tiles = 1
    job.processed_tiles = 0
    job.progress = 0.1
    db.commit()

    try:
        slide = SmartSlide(job.input_path)
        
        
        await asyncio.sleep(0.5)
        
        
        preview = slide.get_thumbnail((1024, 1024))
        
        out_dir = os.path.dirname(job.output_path)
        if out_dir: os.makedirs(out_dir, exist_ok=True)
        
        preview.save(job.output_path)
        print(f"[Preview] Saved: {job.output_path}")
        
        slide.close()

        job.processed_tiles = 1
        job.progress = 1.0
        db.commit()

    except Exception as e:
        print(f"[Preview] Failed: {e}")
        raise e