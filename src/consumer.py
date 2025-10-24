from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, Callable
from .storage import DedupStore
from .stats import Stats

logger = logging.getLogger("consumer")

async def consumer_worker(
    name: str,
    queue: asyncio.Queue,
    store: DedupStore,
    stats: Stats,
    on_processed: Callable[[Dict[str, Any]], None] | None = None
):
    """Continuously consume events, apply dedup via store, update stats and optionally call callback on new events."""
    while True:
        ev = await queue.get()
        try:
            is_new = await store.mark_processed_if_new(ev)
            if is_new:
                await stats.inc_unique()
                if on_processed:
                    try:
                        on_processed(ev)
                    except Exception:
                        logger.exception("on_processed callback error")
            else:
                await stats.inc_duplicate()
                logger.info("Duplicate dropped for (%s, %s)", ev["topic"], ev["event_id"])
        except Exception:
            logger.exception("Error processing event %s", ev)
        finally:
            queue.task_done()
