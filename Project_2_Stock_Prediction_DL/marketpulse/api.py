"""Read-only offline demonstration API. No private data, training or trading endpoints."""
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .artifact import forecast, read_bundle
from .data import load_csv

log = logging.getLogger("uvicorn.error")
ROOT = Path(__file__).resolve().parents[1]


def create_app(folder=None):
    folder = Path(folder) if folder else ROOT/"artifacts"/"demo"
    spec, report = read_bundle(folder)
    if not report["dataset"]["synthetic"]:
        raise ValueError("Public demo serves only synthetic evidence")
    series = load_csv(folder/"observations.csv", spec["ticker"], spec["source"])
    if series.fingerprint != report["dataset"]["sha256"]:
        raise ValueError("Demo data checksum mismatch")
    point = forecast(folder, series) if spec["approved"] else None
    app = FastAPI(title="MarketPulse ML", version=__version__, description="Synthetic research demonstration only")
    app.mount("/static", StaticFiles(directory=ROOT/"marketpulse"/"static"), name="static")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        # Route template only: no query/body/credentials in application logs.
        route = request.scope.get("route")
        log.info("method=%s route=%s status=%s duration_ms=%.2f", request.method,
                 getattr(route, "path", "static_or_unknown"), response.status_code,
                 (time.perf_counter()-start)*1000)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(ROOT/"marketpulse"/"static"/"index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "mode": "synthetic/offline",
                "release_gate_passed": spec["approved"]}

    @app.get("/api/report")
    def get_report():
        return report

    @app.get("/api/forecast")
    def get_forecast():
        if point is None:
            raise HTTPException(status_code=409, detail="Release gate failed: forecast unavailable")
        return {**point, "ticker": spec["ticker"], "source": spec["source"],
                "model": spec["name"], "synthetic": True, "warning": "Fictional research data; not a live price or trading signal."}

    return app


app = create_app()
