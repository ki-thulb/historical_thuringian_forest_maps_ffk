import asyncio
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()

# In-memory job store — resets on server restart (intentional for stub phase)
_jobs: dict = {}

# Upload storage location
_store = Path("/tmp/hack-heritage")
_store.mkdir(exist_ok=True)

# Simulated processing stages with (stage_name, cumulative_progress)
_STAGES = [
    ("border_removal", 0.15),
    ("fold_detection", 0.35),
    ("fold_removal", 0.55),
    ("stitching", 0.75),
    ("georeferencing", 1.0),
]

# Known mocks: filename fragment → (overlay image, WGS84 bounds)
# Bounds extracted from georeferenced GeoTIFFs (EPSG:25832 → WGS84)
_MOCK_MAPS = {
    "jena": {
        "overlay_url": "/jena-03-overlay.png",
        "bounds": {"north": 50.966492, "south": 50.933940, "east": 11.666109, "west": 11.615517},
    },
    "weimar": {
        "overlay_url": "/weimar-64-overlay.png",
        "bounds": {"north": 50.784942, "south": 50.729728, "east": 10.883992, "west": 10.765325},
    },
}

_DEFAULT_MOCK = _MOCK_MAPS["jena"]


def _pick_mock(filenames: list) -> dict:
    """Select mock data based on uploaded filenames, falling back to Jena."""
    combined = " ".join(filenames).lower()
    for key, mock in _MOCK_MAPS.items():
        if key in combined:
            return mock
    return _DEFAULT_MOCK


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _simulate_processing(job_id: str) -> None:
    await asyncio.sleep(0.5)  # brief queue delay

    for stage, progress in _STAGES:
        if _jobs.get(job_id, {}).get("status") == "cancelled":
            return
        _jobs[job_id].update(
            status="processing",
            stage=stage,
            progress=progress,
            updated_at=_now(),
        )
        await asyncio.sleep(2)

    if _jobs.get(job_id, {}).get("status") == "cancelled":
        return

    mock = _pick_mock(_jobs[job_id].get("filenames", []))
    _jobs[job_id].update(
        status="completed",
        stage=None,
        progress=1.0,
        updated_at=_now(),
        result={
            "overlay_url": mock["overlay_url"],
            "bounds": mock["bounds"],
            "geojson_url": f"/api/v1/jobs/{job_id}/geojson",
            "files": {
                "clean_image": f"/api/v1/jobs/{job_id}/files/clean.jpg",
            },
        },
    )


@router.post("/jobs", status_code=202)
async def create_job(
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    tiles_x: Optional[int] = Form(None),
    tiles_y: Optional[int] = Form(None),
    notes: Optional[str] = Form(None),
):
    if not images:
        raise HTTPException(422, "No images provided")

    first_job = None
    for i, img in enumerate(images):
        content = await img.read()
        filename = img.filename or f"image_{i}.jpg"

        job_id = str(uuid.uuid4())
        upload_dir = _store / job_id / "uploads"
        upload_dir.mkdir(parents=True)
        (upload_dir / filename).write_bytes(content)

        now = _now()
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "stage": None,
            "progress": 0.0,
            "created_at": now,
            "updated_at": now,
            "image_count": 1,
            "filenames": [filename],
            "metadata": {"tiles_x": tiles_x, "tiles_y": tiles_y, "notes": notes},
            "result": None,
            "error": None,
            "poll_url": f"/api/v1/jobs/{job_id}",
        }

        background_tasks.add_task(_simulate_processing, job_id)
        if first_job is None:
            first_job = _jobs[job_id]

    return first_job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    return _jobs[job_id]


@router.get("/jobs/{job_id}/overlay")
async def get_overlay(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")

    job = _jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(
            status_code=202,
            content={"status": job["status"], "retry_after": 5},
        )

    upload_dir = _store / job_id / "uploads"
    images = sorted(upload_dir.glob("*"))
    if not images:
        raise HTTPException(404, "No uploaded image found")

    return FileResponse(images[0])


@router.get("/jobs/{job_id}/geojson")
async def get_geojson(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    # OCR/geocoding not yet implemented — return empty FeatureCollection
    return {"type": "FeatureCollection", "features": []}


@router.get("/jobs/{job_id}/files/{filename}")
async def get_file(job_id: str, filename: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")

    path = _store / job_id / "uploads" / filename
    if not path.exists():
        raise HTTPException(404, "File not found")

    return FileResponse(path)


@router.get("/jobs")
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
):
    items = list(_jobs.values())
    if status:
        items = [j for j in items if j["status"] == status]

    items.sort(key=lambda j: j["created_at"], reverse=True)
    total = len(items)
    page = items[offset : offset + limit]

    return {
        "total": total,
        "items": [
            {
                "job_id": j["job_id"],
                "status": j["status"],
                "created_at": j["created_at"],
                "image_count": j["image_count"],
                "filenames": j.get("filenames", []),
                "notes": j["metadata"].get("notes"),
            }
            for j in page
        ],
    }


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    if _jobs[job_id]["status"] == "processing":
        raise HTTPException(409, "Job is currently processing — cancel it first")

    job_dir = _store / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)

    del _jobs[job_id]


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    if _jobs[job_id]["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(409, f"Job already in terminal state: {_jobs[job_id]['status']}")

    _jobs[job_id].update(status="cancelled", updated_at=_now())
    return {"job_id": job_id, "status": "cancelled"}
