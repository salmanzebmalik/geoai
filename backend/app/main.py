from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.database import create_db_and_tables


app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


static_dir = Path("static")
static_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "GeoAI Segmentation Backend API is running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }