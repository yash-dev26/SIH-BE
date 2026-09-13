from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import forecasts, recommendations
from app.config import settings
from app.db.session import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB & Seed master data on startup
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(forecasts.router, prefix=settings.API_V1_STR)
app.include_router(recommendations.router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "FreightIQ API", "version": settings.VERSION}


@app.get("/health/db", tags=["Health"])
def db_health_check():
    from app.db.models import VesselClass, TradeLane, Port, ModelRegistry, Forecast
    db = SessionLocal()
    try:
        return {
            "status": "ok",
            "vessel_classes": db.query(VesselClass).count(),
            "ports": db.query(Port).count(),
            "trade_lanes": db.query(TradeLane).count(),
            "registered_models": db.query(ModelRegistry).count(),
            "persisted_forecasts": db.query(Forecast).count(),
        }
    finally:
        db.close()
