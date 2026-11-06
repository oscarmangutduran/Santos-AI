"""
Punto de entrada principal de la aplicación FastAPI (Santos-AI).
Configura el ciclo de vida asíncrono (lifespan), middlewares, logging y routers.
"""

from contextlib import asynccontextmanager
import logging
import sys
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.database import close_db, init_db
from routers.webhook import router as webhook_router


def configure_logging() -> None:
    """Configura el formato y nivel de logs para salida estándar."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestiona el inicio y apagado de recursos asíncronos:
    - Startup: Inicializa esquemas de base de datos (SQLite / PostgreSQL).
    - Shutdown: Cierra el pool de conexiones de SQLAlchemy.
    """
    logger.info("Iniciando %s en modo '%s'...", settings.APP_NAME, settings.ENVIRONMENT)
    await init_db()
    logger.info("Base de datos inicializada correctamente.")
    yield
    logger.info("Cerrando conexiones de base de datos...")
    await close_db()
    logger.info("Aplicación detenida limpiamente.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend asíncrono para Agente de IA conversacional en WhatsApp Business Cloud API "
        "con memoria persistente y procesamiento desacoplado en segundo plano."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Montaje de Routers
app.include_router(webhook_router)


@app.get("/health", tags=["Healthcheck"], summary="Estado de salud del servicio")
async def healthcheck() -> dict[str, str]:
    """Endpoint ligero para monitoreo e inspección de disponibilidad."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
    )

