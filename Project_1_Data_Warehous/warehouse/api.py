"""Read-only local portfolio API. Never expose to the public with private data."""
from datetime import date
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analytics import report, runs
from .db import DEFAULT_DB, ROOT, connect, assert_version
from .quality import evaluate


def create_app(db_path=None):
    path = Path(db_path or os.environ.get("WAREHOUSE_DB", DEFAULT_DB))
    app = FastAPI(title="Furniture Sales Intelligence", version="1.0.0",
                  description="Read-only analytics for a local synthetic-data warehouse.")
    app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/health")
    def health():
        try:
            with connect(path, readonly=True) as db:
                assert_version(db)
                db.execute("SELECT 1 FROM fact_sales LIMIT 1").fetchone()
        except (sqlite3.Error, RuntimeError):
            raise HTTPException(503, "Warehouse not ready")
        return {"status": "ready", "schema_version": 1}

    @app.get("/api/report")
    def analytics(start: date | None = None, end: date | None = None,
                  category: str | None = Query(default=None, min_length=1, max_length=120),
                  country: str | None = Query(default=None, min_length=1, max_length=120)):
        try:
            return report(path, start, end, category, country)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except (sqlite3.Error, RuntimeError):
            raise HTTPException(503, "Warehouse unavailable") from None

    @app.get("/api/quality")
    def quality():
        try:
            return evaluate(path)
        except (sqlite3.Error, RuntimeError):
            raise HTTPException(503, "Warehouse unavailable") from None

    @app.get("/api/runs")
    def recent_runs(limit: int = Query(default=20, ge=1, le=100)):
        try:
            return runs(path, limit)
        except (sqlite3.Error, RuntimeError):
            raise HTTPException(503, "Warehouse unavailable") from None

    return app


app = create_app()
