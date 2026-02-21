from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class JobBounds(BaseModel):
    north: float
    south: float
    east: float
    west: float


class JobResult(BaseModel):
    overlay_url: str
    bounds: JobBounds
    geojson_url: str
    files: Dict[str, str]


class JobError(BaseModel):
    stage: Optional[str] = None
    message: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str] = None
    progress: float = 0.0
    created_at: str
    updated_at: str
    image_count: int = 0
    metadata: Dict[str, Any] = {}
    result: Optional[JobResult] = None
    error: Optional[JobError] = None
    poll_url: Optional[str] = None


class JobListItem(BaseModel):
    job_id: str
    status: str
    created_at: str
    image_count: int
    notes: Optional[str] = None


class JobListResponse(BaseModel):
    total: int
    items: List[JobListItem]
