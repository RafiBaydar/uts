import time, anyio, pytest
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from src.main import create_app

@pytest.mark.anyio
async def test_publish_and_get_events(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(db_path=str(db))
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            ev = {"topic":"orders","event_id":"ord-1","timestamp":"2025-01-01T00:00:00Z","source":"test","payload":{"a":1}}
            r = await ac.post("/publish", json=ev); assert r.status_code == 200
            await wait_until_processed(ac, expected_unique=1)
            data = (await ac.get("/events?topic=orders")).json()
            assert data["count"] == 1 and data["events"][0]["event_id"] == "ord-1"

async def wait_until_processed(ac: AsyncClient, expected_unique: int, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = (await ac.get("/stats")).json()
        if s["unique_processed"] >= expected_unique:
            return
        await anyio.sleep(0.05)
    raise AssertionError("timeout")
