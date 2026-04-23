"""
Background cache warmer. Replaces the hub's Modal scheduled function
(`warm_cache` at `modal_outreach_hub.py:142`) with an asyncio loop that's
spawned from the FastAPI lifespan handler at startup.

Keeps the Redis table cache fresh every 90s for the tables the field-rep app
actually reads. If a table isn't warm yet, the on-demand `storage.cached_table`
will fetch it — so the warmer is just an optimization, not a correctness
requirement.
"""
import asyncio
import os

from hub.constants import (
    T_ACTIVITIES, T_COMPANIES, T_EVENTS, T_GOR_ACTS, T_GOR_BOXES,
    T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_GOR_VENUES, T_LEADS, T_STAFF,
)

from . import storage
from .routes.api import _fetch_table_all

_WARM_PERIOD = 90  # seconds

_WARM_TABLES = [
    T_GOR_ROUTES, T_GOR_ROUTE_STOPS, T_GOR_ACTS,
    T_GOR_VENUES, T_GOR_BOXES, T_EVENTS, T_STAFF,
    T_COMPANIES, T_ACTIVITIES, T_LEADS,
]


async def _warm_once() -> None:
    br = os.environ.get("BASEROW_URL", "")
    bt = os.environ.get("BASEROW_API_TOKEN", "")
    if not br or not bt:
        return
    results = await asyncio.gather(
        *[_fetch_table_all(br, bt, tid) for tid in _WARM_TABLES if tid],
        return_exceptions=True,
    )
    for tid, rows in zip([t for t in _WARM_TABLES if t], results):
        if isinstance(rows, Exception):
            print(f"[warm] table {tid} failed: {rows}")
            continue
        try:
            await storage.set_cached_table(tid, rows)
        except Exception as e:
            print(f"[warm] redis set table {tid} failed: {e}")


async def warm_loop() -> None:
    """Run forever — meant to be scheduled via FastAPI lifespan."""
    while True:
        try:
            await _warm_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[warm] unexpected error: {e}")
        try:
            await asyncio.sleep(_WARM_PERIOD)
        except asyncio.CancelledError:
            raise
