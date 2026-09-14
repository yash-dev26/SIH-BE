from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import forecasts, recommendations
from app.config import settings
from app.db.session import SessionLocal, get_db, init_db


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


@app.get("/ports", tags=["Master Data"])
@app.get("/api/ports", tags=["Master Data"])
def get_ports():
    from app.db.models import Port
    db = SessionLocal()
    try:
        ports = db.query(Port).all()
        return [
            {
                "id": p.port_code,
                "name": p.port_name.replace(" Port", ""),
                "country": p.country,
                "lat": p.latitude,
                "lng": p.longitude,
                "maxDraftM": p.max_draft_charted_m,
                "maxLoaM": p.max_loa_m,
                "maxBeamM": p.max_beam_m,
                "handlingRateMtpd": p.cargo_handling_rate_mt_per_day,
                "notes": p.notes or ""
            }
            for p in ports
        ]
    finally:
        db.close()


@app.get("/vessel-classes", tags=["Master Data"])
@app.get("/api/vessel-classes", tags=["Master Data"])
def get_vessel_classes():
    from app.db.models import VesselClass
    db = SessionLocal()
    try:
        vclasses = db.query(VesselClass).all()
        return [
            {
                "id": str(v.vessel_class_id),
                "name": v.class_name,
                "typicalDwt": v.dwt_max_mt,
                "loaM": v.loa_max_m,
                "beamM": v.beam_max_m,
                "designDraftM": v.draft_max_m
            }
            for v in vclasses
        ]
    finally:
        db.close()


@app.post("/recommend", tags=["Recommendation & Optimization Engine"])
@app.post("/api/recommend", tags=["Recommendation & Optimization Engine"])
def get_chartering_recommendation_alias(
    request: recommendations.RecommendationRequest,
    db: SessionLocal = Depends(get_db)
):
    from app.optimization.recommendation_service import RecommendationService
    svc = RecommendationService(db)
    return svc.generate_recommendation(
        commodity=request.commodity,
        cargo_qty_mt=request.cargo_qty_mt,
        destination_port_code=request.destination_port_code,
        laycan_start=request.laycan_start,
        laycan_end=request.laycan_end
    )

