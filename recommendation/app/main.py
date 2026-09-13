import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.routers import auth, contracts, forecasts, ports, recommendations, risk, scenarios, vessels
from app.config import settings
from app.db.session import SessionLocal, init_db

logger = logging.getLogger("freightiq.request")
logging.basicConfig(level=logging.INFO)


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

# --- Rate limiting (Phase 5 task 4) -----------------------------------------------------
# A simple fixed-window limit per client IP, applied to every route via the middleware so
# individual routers don't each need a `@limiter.limit(...)` decorator. Toggle off with
# settings.RATE_LIMIT_ENABLED for local dev/tests where bursty requests are expected.
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(SlowAPIMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request logging middleware (Phase 5 task 4) ----------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Register Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(ports.router, prefix=settings.API_V1_STR)
app.include_router(vessels.router, prefix=settings.API_V1_STR)
app.include_router(forecasts.router, prefix=settings.API_V1_STR)
app.include_router(recommendations.router, prefix=settings.API_V1_STR)
app.include_router(scenarios.router, prefix=settings.API_V1_STR)
app.include_router(contracts.router, prefix=settings.API_V1_STR)
app.include_router(risk.router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "FreightIQ API", "version": settings.VERSION}


@app.get("/health/db", tags=["Health"])
def db_health_check():
    from app.db.models import CharterContract, Forecast, ModelRegistry, Port, TradeLane, User, VesselClass

    db = SessionLocal()
    try:
        return {
            "status": "ok",
            "vessel_classes": db.query(VesselClass).count(),
            "ports": db.query(Port).count(),
            "trade_lanes": db.query(TradeLane).count(),
            "registered_models": db.query(ModelRegistry).count(),
            "persisted_forecasts": db.query(Forecast).count(),
            "charter_contracts": db.query(CharterContract).count(),
            "users": db.query(User).count(),
        }
    finally:
        db.close()
