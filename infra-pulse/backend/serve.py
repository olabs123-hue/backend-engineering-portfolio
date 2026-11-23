"""Serve the read-only dashboard and API on one origin.

This module mounts prebuilt React assets after API routes so API routing wins.
Build the frontend first, or use backend.app:app for API-only development.
"""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from backend.app import app

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if not (DIST / "index.html").is_file():
    raise RuntimeError("Frontend not built. Run 'npm install && npm run build' in frontend/")
app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
