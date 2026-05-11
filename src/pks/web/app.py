from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pks.kernel import Kernel
from pks.web.routes import (
    candidates,
    claims_api,
    claims_pages,
    config,
    maintenance,
    projections,
    projects,
    tokens,
)


def create_app(home: Path | None = None) -> FastAPI:
    package_dir = Path(__file__).parent
    app = FastAPI(title="PKS", version="0.1.0")
    app.state.kernel = Kernel(home)
    app.state.templates = Jinja2Templates(directory=str(package_dir / "templates"))
    app.mount("/static", StaticFiles(directory=str(package_dir / "static")), name="static")
    app.include_router(projects.router)
    app.include_router(candidates.router)
    app.include_router(claims_pages.router)
    app.include_router(claims_api.router)
    app.include_router(projections.router)
    app.include_router(maintenance.router)
    app.include_router(config.router)
    app.include_router(tokens.router)
    return app
