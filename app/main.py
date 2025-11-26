# app/main.py

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine, SessionLocal
from .models import Job, Branch, Workflow
from .scheduler import Scheduler
from .routers import status, workflows
from . import config

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_PATH = BASE_DIR / "dashboard.html"

app = FastAPI(title="Workflow Scheduler")


os.makedirs("outputs", exist_ok=True)
os.makedirs("data", exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

app.mount("/data", StaticFiles(directory="data"), name="data")

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

Base.metadata.create_all(bind=engine)

scheduler = Scheduler(
    max_workers=config.MAX_WORKERS,
    max_active_users=config.MAX_ACTIVE_USERS,
)


app.state.scheduler = scheduler

@app.on_event("startup")
async def startup_event():
    
    db = SessionLocal()
    try:
        
        db.query(Job).delete()
        db.query(Branch).delete()
        db.query(Workflow).delete()
        db.commit()
        print("[Startup] DB data cleared.")
    finally:
        db.close()

    print(f"[Startup] Scheduler started. Max Workers={config.MAX_WORKERS}, Max Users={config.MAX_ACTIVE_USERS}")
    asyncio.create_task(scheduler.start())

@app.on_event("shutdown")
async def shutdown_event() -> None:
    await scheduler.stop()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    if not DASHBOARD_PATH.exists():
        return HTMLResponse(f"<h1>dashboard.html not found</h1>", status_code=500)
    return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))

# API
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])