import pytest
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from src.main import create_app

@pytest.mark.anyio
async def test_schema_validation_errors(tmp_path):
    db = tmp_path / "dedup.db"; app = create_app(db_path=str(db))
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            bad = {"topic":"a","event_id":"b","source":"s","payload":{}}
            r = await ac.post("/publish", json=bad); body = r.json()
            assert r.status_code == 200 and body["accepted"] == 0 and body["errors"]

            bad2 = {"topic":"a","event_id":"c","timestamp":"not-a-time","source":"s","payload":{}}
            r = await ac.post("/publish", json=[bad2]); body = r.json()
            assert r.status_code == 200 and body["accepted"] == 0 and body["errors"]

@pytest.mark.anyio
async def test_stats_consistency(tmp_path):
    db = tmp_path / "dedup.db"; app = create_app(db_path=str(db))
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            ev1 = {"topic":"k","event_id":"1","timestamp":"2025-01-01T00:00:00Z","source":"s","payload":{}}
            ev2 = {"topic":"k","event_id":"2","timestamp":"2025-01-01T00:00:01Z","source":"s","payload":{}}
            await ac.post("/publish", json=[ev1, ev2, ev1])
            import time, anyio
            t0 = time.time()
            while time.time() - t0 < 5:
                s = (await ac.get("/stats")).json()
                if s["received"] >= 3 and s["unique_processed"] >= 2 and s["duplicate_dropped"] >= 1:
                    break
                await anyio.sleep(0.05)
            events = (await ac.get("/events?topic=k")).json()
            assert events["count"] == 2
            topics = (await ac.get("/stats")).json()["topics"]
            assert "k" in topics
