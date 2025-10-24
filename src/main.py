from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .models import Event, PublishResponse, StatsResponse
from .storage import DedupStore
from .stats import Stats
from .consumer import consumer_worker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("aggregator")

def create_app(db_path: str | None = None, queue_size: int = 10000, workers: int = 4) -> FastAPI:
    app = FastAPI(title="UTS Event Aggregator", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = db_path or os.getenv("DEDUP_DB_PATH", "/app/data/dedup.db")
    store = DedupStore(db_path=db_path)
    stats = Stats()
    queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
    worker_tasks: list[asyncio.Task] = []

    @app.on_event("startup")
    async def _startup():
        logger.info("Starting up, DB at %s", db_path)
        await store.init()
        for i in range(workers):
            t = asyncio.create_task(consumer_worker(f"w{i}", queue, store, stats, None))
            worker_tasks.append(t)
        logger.info("Started %d consumer workers", workers)

    @app.on_event("shutdown")
    async def _shutdown():
        logger.info("Shutting down, cancel workers")
        for t in worker_tasks:
            t.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)

    @app.post("/publish", response_model=PublishResponse)
    async def publish(request: Request):
        """Accept single Event or list[Event]. Validate schema, enqueue for processing."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        events: list[Event] = []
        errors: list[str] = []

        def validate_one(obj: dict):
            try:
                return Event.model_validate(obj)
            except Exception as e:
                errors.append(str(e))
                return None

        if isinstance(body, list):
            for item in body:
                if not isinstance(item, dict):
                    errors.append("Each item must be an object")
                    continue
                ev = validate_one(item)
                if ev:
                    events.append(ev)
        elif isinstance(body, dict):
            ev = validate_one(body)
            if ev:
                events.append(ev)
        else:
            raise HTTPException(status_code=422, detail="Body must be an object or array of objects")

        # Enqueue validated events
        accepted = 0
        for ev in events:
            item = ev.model_dump()
            try:
                await queue.put(item)
                accepted += 1
            except asyncio.QueueFull:
                raise HTTPException(status_code=503, detail="Queue is full")

        await stats.inc_received(accepted)
        return PublishResponse(accepted=accepted, queued=queue.qsize(), errors=errors or None)

    @app.get("/events")
    async def get_events(
        topic: Optional[str] = Query(default=None),
        limit: int = Query(default=1000, ge=1, le=100000),
        offset: int = Query(default=0, ge=0),
    ):
        events = await store.get_events(topic=topic, limit=limit, offset=offset)
        return {"events": events, "count": len(events)}

    @app.get("/stats", response_model=StatsResponse)
    async def stats_endpoint():
        topics = await store.list_topics()
        return StatsResponse(
            received=stats.received,
            unique_processed=stats.unique_processed,
            duplicate_dropped=stats.duplicate_dropped,
            topics=topics,
            uptime_seconds=stats.uptime(),
            queue_size=queue.qsize(),
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return {
            "service": "UTS Event Aggregator",
            "status": "ok",
            "docs": "/docs",
            "health": "/healthz",
            "stats": "/stats",
            "publish": "POST /publish",
            "events": "GET /events?topic=...&limit=&offset=",
            "version": "1.0.0",
        }

    # attach for tests
    app.state.queue = queue
    app.state.stats = stats
    app.state.store = store
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=False)
