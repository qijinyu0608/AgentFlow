from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
from ..common import ensure_config_loaded, logger
from ..common.paths import get_frontend_dist_path

from .task_api import router as task_router
from .websocket_api import router as websocket_router
from .memory_api import router as memory_router
from .conversation_api import router as conversation_router
from .config_api import router as config_router
from .rag_ingest_api import router as rag_ingest_router


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response

        index_path = Path(self.directory) / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return response


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    ensure_config_loaded()
    
    app = FastAPI(
        title="AgentMesh API",
        description="Multi-agent system API for task management",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    cors_origins_raw = os.environ.get("AGENTMESH_CORS_ORIGINS", "*")
    cors_origins = [x.strip() for x in cors_origins_raw.split(",") if x.strip()]
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(task_router)
    app.include_router(websocket_router)
    app.include_router(memory_router)
    app.include_router(conversation_router)
    app.include_router(config_router)
    app.include_router(rag_ingest_router)

    frontend_dist = get_frontend_dist_path()
    if frontend_dist.exists():
        app.mount("/", SPAStaticFiles(directory=os.fspath(frontend_dist), html=True), name="frontend")
    else:
        logger.warning("Frontend dist directory not found: %s", frontend_dist)
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.exception("Unhandled API exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "data": None
            }
        )
    
    return app


# Create app instance
app = create_app() 
