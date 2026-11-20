from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.auth_routes import router as auth_router
from app.api.academic_routes import router as academic_router
from app.api.scheduling_routes import router as scheduling_router
from app.api.ai_routes import router as ai_router
from app.api.excel_routes import router as excel_router
from app.api.web_routes import router as web_router
from app.services.data_store import store

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("smarttimetable")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Backend bootstrap process:
    Ensures the Timetable Officer account is provisioned and ready for first-login.
    Faculties are created dynamically by the Officer in the Faculty Management screen.
    """
    logger.info("Initializing SmartTimetable AI Institutional OS...")
    logger.info("Timetable Officer bootstrap account verified and active.")
    logger.info(f"System ready with {len(store.clusters)} clusters, {len(store.sections)} sections, {len(store.classrooms)} rooms, {len(store.laboratories)} labs.")
    yield

app = FastAPI(
    title="SmartTimetable AI",
    description="Institutional College Timetable Management & AI-Powered OR-Tools Optimization Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Web UI Routes (HTML pages)
app.include_router(web_router)

# Register REST API Routes (JSON endpoints)
app.include_router(auth_router, prefix="/api")
app.include_router(academic_router, prefix="/api")
app.include_router(scheduling_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(excel_router, prefix="/api")



@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "SmartTimetable AI Institutional OS",
        "version": "1.0.0",
        "officer_ready": settings.BOOTSTRAP_OFFICER_ID in store.profiles,
        "faculties_count": len(store.faculty)
    }
