from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import engine


def dist_dir() -> Path:
    return engine.dashboard_dist()


def is_built() -> bool:
    return (dist_dir() / "index.html").is_file()


def mount_spa(app: FastAPI, route: str = "/app") -> bool:
    root = dist_dir()
    if not is_built():
        return False
    assets = root / "assets"
    if assets.is_dir():
        app.mount(f"{route}/assets", StaticFiles(directory=str(assets)), name="dashboard-assets")

    index = root / "index.html"

    @app.get(route, include_in_schema=False)
    @app.get(route + "/{spa_path:path}", include_in_schema=False)
    def dashboard_shell(spa_path: str = "") -> FileResponse:
        candidate = (root / spa_path).resolve() if spa_path else index
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            raise HTTPException(404, "not found") from None
        if spa_path and candidate.is_file() and candidate.suffix != ".html":
            return FileResponse(candidate)
        return FileResponse(index)

    return True
