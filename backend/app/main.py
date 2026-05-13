from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import router
from app.database import create_db_and_tables


app = FastAPI(
    title="GeoAI Segmentation Backend API",
    description="Backend API for bounding-box based satellite image segmentation.",
    version="1.0.0"
)


origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "GeoAI Segmentation Backend API is running"
    }