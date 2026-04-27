"""
FastAPI entry for the field-rep app (routes.reformchiropractic.app).

Runs as a Docker container on Coolify. Startup lifespan spawns the Redis
cache warmer; shutdown cancels it and closes the Redis connection.
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allow `from hub.* import ...` when this file is launched as
# `uvicorn field_rep.app:app` from the `execution/` build context.
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .auth import router as auth_router
from .routes.api import router as api_router
from .routes.pages import router as pages_router
from .warm import _warm_once, warm_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Block until the Redis cache is populated so the first user request
    # after a deploy reads warm data instead of paying the full Baserow
    # round-trip on every table.
    try:
        await _warm_once()
    except Exception as e:
        print(f"[lifespan] initial warm failed (continuing anyway): {e}")
    warmer = asyncio.create_task(warm_loop())
    try:
        yield
    finally:
        warmer.cancel()
        try:
            await warmer
        except asyncio.CancelledError:
            pass
        await storage.close()


app = FastAPI(title="Reform Routes", lifespan=lifespan)

# PWA static assets — manifest, icons, service worker. Served unauthenticated
# so the install + sw registration flow works before login.
_STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

app.include_router(auth_router)
app.include_router(pages_router)
app.include_router(api_router)


@app.get("/manifest.json")
async def manifest_passthrough():
    """Serve manifest.json from the root for browsers that look for it there."""
    return FileResponse(str(_STATIC / "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js")
async def sw_passthrough():
    """Serve sw.js from the root so its scope is '/' (covers the whole app)."""
    return FileResponse(str(_STATIC / "sw.js"), media_type="application/javascript")


@app.get("/healthz")
async def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "field_rep.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
