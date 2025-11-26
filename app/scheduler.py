# # app/scheduler.py




from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Dict, Set, List
from .db import SessionLocal
from .models import JobStatus
from .jobs import execute_job
from .repositories import job_repo
from . import config


class Scheduler:
    def __init__(
        self,
        max_workers: int | None = None,
        max_active_users: int | None = None,
    ) -> None:
        self.max_workers = max_workers or config.MAX_WORKERS
        self.max_active_users = max_active_users or config.MAX_ACTIVE_USERS

        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

        self._running_tasks: Dict[str, dict] = {}

        self._active_users: Set[str] = set()
       
        print(f"[Scheduler] initialized. Max Users={self.max_active_users}, Max Workers={self.max_workers}")

    
    async def kill_task(self, job_id: str) -> bool:
        
        async with self._lock:
            if job_id in self._running_tasks:
                task_info = self._running_tasks[job_id]
                task = task_info['task']
                
                
                task.cancel() 
                
                print(f"[Scheduler] Hard killing task for Job {job_id}")
                return True
            return False

     

    async def start(self) -> None:
        print("[Scheduler] Starting loop...")
        while not self._stop_event.is_set():
            try:
                await self._schedule_once()
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[Scheduler] Loop error: {e}")
           
            await asyncio.sleep(1.0)
        print("[Scheduler] Stopped.")

    async def stop(self) -> None:
        self._stop_event.set()
        async with self._lock:
            tasks = [t['task'] for t in self._running_tasks.values()]
        if tasks:
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

   

    async def _schedule_once(self) -> None:
        db = SessionLocal()
        try:
            async with self._lock:
                busy_users_in_db = job_repo.get_users_with_incomplete_jobs(db)
                current_active_list = list(self._active_users)
                
                
                for uid in current_active_list:
                    if uid not in busy_users_in_db:
                        self._active_users.remove(uid)
                        print(f"[Scheduler] User {uid} finished. Slot released.")

                
                if len(self._active_users) < self.max_active_users:
                    waiting_users = [u for u in busy_users_in_db if u not in self._active_users]
                    slots_open = self.max_active_users - len(self._active_users)
                    for i in range(min(slots_open, len(waiting_users))):
                        new_user = waiting_users[i]
                        self._active_users.add(new_user)
                        print(f"[Scheduler] User {new_user} admitted to Active Slot.")

                
                cancelled_count = job_repo.auto_cancel_blocked_jobs(db)
                
               
                if cancelled_count > 0:
                     await self._cleanup_zombies(db)

                
                if not self._active_users: return
                if len(self._running_tasks) >= self.max_workers: return

                candidates = job_repo.get_runnable_jobs(db, allowed_user_ids=self._active_users)

                
                for job in candidates:
                    if len(self._running_tasks) >= self.max_workers: break
                    if self._is_branch_running_in_memory(job.branch_id): continue

                    
                    job.status = JobStatus.RUNNING
                    job.started_at = datetime.utcnow()
                    db.commit()

                    task = asyncio.create_task(self._run_single_job(job.id, job.user_id))
                    self._running_tasks[job.id] = {
                        'task': task,
                        'branch_id': job.branch_id
                    }
                    
                    
                    task.add_done_callback(
                        lambda t, jid=job.id, uid=job.user_id: asyncio.create_task(
                            self._on_task_done(jid, uid)
                        )
                    )
                    print(f"[Scheduler] Started Job {job.id} (Branch: {job.branch_id})")

        finally:
            db.close()

    async def _cleanup_zombies(self, db):
        
        for job_id in list(self._running_tasks.keys()):
            job = job_repo.get_job_by_id(db, job_id)
            if job and job.status in [JobStatus.CANCELLED, JobStatus.FAILED]:
                await self.kill_task(job_id)

    def _is_branch_running_in_memory(self, branch_id: str) -> bool:
        for info in self._running_tasks.values():
            if info['branch_id'] == branch_id:
                return True
        return False

    async def _on_task_done(self, job_id: str, user_id: str) -> None:
        async with self._lock:
            self._running_tasks.pop(job_id, None)

    async def _run_single_job(self, job_id: str, user_id: str) -> None:
        db = SessionLocal()
        try:
            job = job_repo.get_job_by_id(db, job_id)
            if not job: return

            try:
                await execute_job(db, job)

                if job.status == JobStatus.RUNNING:
                    job.status = JobStatus.SUCCEEDED
                job.finished_at = datetime.utcnow()
                if job.progress < 1.0: job.progress = 1.0
                db.commit()
                print(f"[Scheduler] Job {job_id} Finished: {job.status}")

            except asyncio.CancelledError:
                print(f"[Scheduler] Job {job_id} was CANCELLED (Interrupted).")
                
                db.refresh(job)
                if job.status != JobStatus.CANCELLED:
                    job.status = JobStatus.CANCELLED
                    db.commit()
                raise 

            except Exception as e:
                print(f"[Scheduler] Job {job_id} Failed: {e}")
                job.status = JobStatus.FAILED
                job.finished_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()