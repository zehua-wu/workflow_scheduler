# app/image_tasks/instanseg_seg.py

import os
import json
import asyncio
import numpy as np
import cv2
from PIL import Image, ImageDraw


import torch
import instanseg

from sqlalchemy.orm import Session
from ..models import Job
from .utils import SmartSlide  


TILE_SIZE = 512       
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


_model_cache = None
def get_model():
    global _model_cache
    if _model_cache is None:
        print(f"[InstanSeg] Loading model on {DEVICE}...")
        
        _model_cache = instanseg.InstanSeg("nuclei", device=DEVICE)
    return _model_cache

def mask_to_polygons(mask_array, offset_x, offset_y):
    
    polygons = []
    cell_ids = np.unique(mask_array)
    
    for cid in cell_ids:
        if cid == 0: continue 
        
        
        binary = (mask_array == cid).astype(np.uint8)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if len(contour) < 3: continue 
            
            
            points = []
            for pt in contour:
                px, py = pt[0]
                points.append([int(px + offset_x), int(py + offset_y)])
            
            if len(points) >= 3:
                polygons.append(points)
    return polygons

async def run_instanseg_job(db: Session, job: Job) -> None:
    if not os.path.exists(job.input_path):
        print(f"[InstanSeg] Missing: {job.input_path}")
        return 

    
    try:
        slide = SmartSlide(job.input_path)
        width, height = slide.dimensions
    except Exception as e:
        print(f"[InstanSeg] Error opening: {e}")
        return

    print(f"[InstanSeg] Processing {width}x{height} ({slide.mode}) | Job: {job.id}")
    
    
    try:
        model = get_model()
    except Exception as e:
        print(f"[InstanSeg] Model load failed: {e}")
        return

    
    tiles = []
    for y in range(0, height, TILE_SIZE):
        for x in range(0, width, TILE_SIZE):
            w = min(TILE_SIZE, width - x)
            h = min(TILE_SIZE, height - y)
            tiles.append((x, y, w, h))
            
    job.total_tiles = len(tiles)
    job.processed_tiles = 0
    job.progress = 0.0
    db.commit()

    all_cells = []
    
   
    for i, (tx, ty, tw, th) in enumerate(tiles):
        await asyncio.sleep(0) 
        
        try:
            
            region = slide.read_region((tx, ty), 0, (tw, th))
            img_np = np.array(region.convert("RGB"))
            
            
            labeled_output = model.eval_small_image(img_np, progress_bar=False)
            
            
            mask_np = labeled_output[0].cpu().numpy()
            polys = mask_to_polygons(mask_np, tx, ty)
            
            for poly in polys:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                all_cells.append({
                    "id": len(all_cells) + 1,
                    "polygon": poly,
                    "bbox": [min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)],
                    "score": 0.95
                })

        except Exception as e:
            print(f"[InstanSeg] Tile error: {e}")

        
        job.processed_tiles = i + 1
        job.progress = (i + 1) / len(tiles)
        if i % 5 == 0 or i == len(tiles)-1: db.commit()

    
    out_dir = os.path.dirname(job.output_path)
    if out_dir: os.makedirs(out_dir, exist_ok=True)

    with open(job.output_path, "w") as f:
        json.dump({"metadata": {"dims": [width, height]}, "cells": all_cells}, f)

    
    try:
        thumb = slide.get_thumbnail((2048, 2048))
        t_w, t_h = thumb.size
        scale_x, scale_y = t_w / width, t_h / height
        
        draw = ImageDraw.Draw(thumb)
        for cell in all_cells:
            
            poly = [(int(p[0]*scale_x), int(p[1]*scale_y)) for p in cell['polygon']]
            if len(poly) > 2:
                draw.line(poly + [poly[0]], fill="#00ff00", width=2)
        
        overlay_path = job.output_path.replace(".json", "_overlay.png")
        thumb.save(overlay_path)
        print(f"[InstanSeg] Overlay saved: {overlay_path}")
        
    except Exception as e:
        print(f"[InstanSeg] Viz failed: {e}")

    slide.close()