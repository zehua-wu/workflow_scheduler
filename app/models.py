# app/models.py

"""
    ORM Entities
"""


from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Float,
    Enum,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from .db import Base


# Enum
class JobStatus(str, enum.Enum): # Job state
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

# Enum
class JobType(str, enum.Enum):
    
    TISSUE_MASK = "tissue_mask"                   
    INSTANTSEG_CELL_SEG = "instanseg_cell_seg"    
    PREVIEW_DOWNSAMPLE = "preview_downsample"     


# Worflow data table
class Workflow(Base):
    __tablename__ = "workflows" # table name

    id = Column(String, primary_key=True, index=True) # primary key
    user_id = Column(String, index=True) 
    name = Column(String) 
    created_at = Column(DateTime, default=datetime.utcnow)

    branches = relationship("Branch", back_populates="workflow") # One-to-many with Branch


# Branch data table
class Branch(Base):
    __tablename__ = "branches" # table name

    id = Column(String, primary_key=True, index=True) # primary key
    workflow_id = Column(String, ForeignKey("workflows.id")) # foreign key
    name = Column(String) 

    workflow = relationship("Workflow", back_populates="branches")
    jobs = relationship("Job", back_populates="branch", order_by="Job.order_index")


# Job data table
class Job(Base):
    __tablename__ = "jobs" # table name

    id = Column(String, primary_key=True, index=True) # primary key
    workflow_id = Column(String, ForeignKey("workflows.id"), index=True) 
    branch_id = Column(String, ForeignKey("branches.id"), index=True)
    user_id = Column(String, index=True)

    
    type = Column(Enum(JobType), nullable=False)

    input_path = Column(String)
    output_path = Column(String)

    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    progress = Column(Float, default=0.0)

    
    order_index = Column(Integer, nullable=False)

    
    total_tiles = Column(Integer, default=0)
    processed_tiles = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    branch = relationship("Branch", back_populates="jobs")
