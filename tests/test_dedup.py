import time, anyio, pytest
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from src.main import create_app

@pytest.mark.anyio
async def test_dedup_basic(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(db_path=str(db))
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            ev = {"topic":"t1","event_id":"x","timestamp":"2025-01-01T00:00:00Z","source":"test","payload":{}}
            r = await ac.post("/publish", json=[ev, ev, ev]); assert r.status_code == 200
            await wait_until(ac, unique=1, dup=2)
            body = (await ac.get("/events?topic=t1")).json()
            assert body["count"] == 1 and body["events"][0]["event_id"] == "x"

@pytest.mark.anyio
async def test_dedup_persistence_across_recreate(tmp_path):
    db = tmp_path / "dedup.db"
    app1 = create_app(db_path=str(db))
    async with LifespanManager(app1):
        async with AsyncClient(app=app1, base_url="http://test") as ac:
            ev = {"topic":"persist","event_id":"id-1","timestamp":"2025-01-01T00:00:00Z","source":"test","payload":{}}
            await ac.post("/publish", json=ev)
            await wait_until(ac, unique=1, dup=0)

    app2 = create_app(db_path=str(db))
    async with LifespanManager(app2):
        async with AsyncClient(app=app2, base_url="http://test") as ac:
            ev = {"topic":"persist","event_id":"id-1","timestamp":"2025-01-01T00:00:00Z","source":"test","payload":{}}
            await ac.post("/publish", json=ev)
            await wait_until(ac, unique=1, dup=1)

async def wait_until(ac: AsyncClient, unique: int, dup: int, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = (await ac.get("/stats")).json()
        if s["unique_processed"] >= unique and s["duplicate_dropped"] >= dup:
            return
        await anyio.sleep(0.05)
    raise AssertionError("timeout")
