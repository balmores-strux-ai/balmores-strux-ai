"""
Entry point shim — full app lives in `app.py`.
Render / production: `uvicorn app:app --host 0.0.0.0 --port $PORT`
Local alt: `uvicorn main:app` (same ASGI app).
"""
from app import app

__all__ = ["app"]
