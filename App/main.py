"""
CIA Network Monitor — FastAPI application.
Serves the dashboard on port 80, runs background monitor + capture services.
"""
import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# Ensure App/ is on sys.path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db
from routes.devices import router as devices_router
from routes.flows import router as flows_router
from routes.ap import router as ap_router
from routes.stats import router as stats_router
from services.monitor import monitor_loop
from services.capture import capture_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + launch background tasks."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database ready")

    # Launch background services
    monitor_task = asyncio.create_task(monitor_loop())
    capture_task = asyncio.create_task(capture_loop())
    logger.info("Background services started (monitor + capture)")

    yield

    # Shutdown
    monitor_task.cancel()
    capture_task.cancel()
    logger.info("Background services stopped")


app = FastAPI(title="CIA Network Monitor", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# API routes
app.include_router(devices_router)
app.include_router(flows_router)
app.include_router(ap_router)
app.include_router(stats_router)


@app.get("/", response_class=HTMLResponse)
async def index():
    tpl_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(tpl_path, "r") as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=80,
        reload=False,
        log_level="info",
    )
