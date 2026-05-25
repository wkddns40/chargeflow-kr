from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.routes import router as routes_router
from app.api.search import router as search_router
from app.api.stations import router as stations_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ChargeFlow KR API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(stations_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(routes_router, prefix="/api")
    return app


app = create_app()
