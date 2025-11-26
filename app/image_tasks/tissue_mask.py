import os
from PIL import Image
import asyncio
from sqlalchemy.orm import Session
from ..models import Job
from .utils import SmartSlide

async def run_tissue_mask_job(db: Session, job: Job) -> None:
    """
    真实的 Tissue Mask 生成：
    1. 读取 WSI 的缩略图 (Level 2 或 3)
    2. 转灰度 -> 二值化 (Otsu or Threshold)
    3. 保存 Mask
    """
    if not os.path.exists(job.input_path):
        print(f"[TissueMask] Input missing: {job.input_path}")
        return

    # 更新状态
    job.total_tiles = 1
    job.processed_tiles = 0
    job.progress = 0.1
    db.commit()

    try:
        # 1. 使用智能加载器
        slide = SmartSlide(job.input_path)
        
        # 2. 获取合适大小的图用于做 Mask (限制在 2048px 以内，处理速度快)
        # 对于 SVS，这会利用金字塔结构快速读取，不需要读全图
        img = slide.get_thumbnail((2048, 2048))
        
        # 模拟处理耗时 (给前端一点反应时间)
        await asyncio.sleep(1.0)
        
        # 3. 图像处理 (灰度 -> 阈值)
        gray = img.convert("L")
        # 简单阈值: 组织通常比背景暗 (背景是白的255)
        # 小于 220 的认为是组织 (255)，否则是背景 (0)
        mask = gray.point(lambda p: 255 if p < 220 else 0)

        # 4. 保存
        out_dir = os.path.dirname(job.output_path)
        if out_dir: os.makedirs(out_dir, exist_ok=True)
        
        mask.save(job.output_path)
        print(f"[TissueMask] Generated mask: {job.output_path}")
        
        slide.close()

        # 完成
        job.processed_tiles = 1
        job.progress = 1.0
        db.commit()

    except Exception as e:
        print(f"[TissueMask] Failed: {e}")
        raise e