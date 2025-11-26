# app/repositories/workflow_repo.py

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import Workflow
from datetime import datetime
import uuid

def create_workflow(db: Session, user_id: str, name: str) -> Workflow:
    wf = Workflow(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        created_at=datetime.utcnow(),
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf

def get_workflow_by_id(db: Session, workflow_id: str, user_id: str) -> Optional[Workflow]:
    return (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == user_id)
        .first()
    )


def list_workflows(db: Session, user_id: str) -> List[Workflow]:
    
    return (
        db.query(Workflow)
        .filter(Workflow.user_id == user_id)
        .order_by(desc(Workflow.created_at))
        .all()
    )