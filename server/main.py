from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import jobs

app = FastAPI(title="Hack the Heritage API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api/v1")
