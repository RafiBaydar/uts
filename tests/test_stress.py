import time, random, anyio, pytest
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from src.main import create_app

def make_event(topic: str, event_id: str, i: int):
    return {"topic":topic,"event_id":event_id,"timestamp":f"2025-01-01T00:00:{i%60:02d}Z","source":"bench","payload":{"i":i}}

@pytest.mark.anyio
async def test_stress_5000_with_duplicates(tmp_path):
    db = tmp_path / "dedup.db"
    app = create_app(db_path=str(db), workers=6)

    N = 5000
    DUP_RATIO = 0.22
    unique_ids = [f"id-{i}" for i in range(N)]
    all_ids = unique_ids + random.choices(unique_ids, k=int(N * DUP_RATIO))
    random.shuffle(all_ids)

    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test", timeout=60.0) as ac:
            batch, sent = [], 0
            t0 = time.time()
            for i, eid in enumerate(all_ids):
                batch.append(make_event("bench", eid, i))
                if len(batch) >= 500:
                    r = await ac.post("/publish", json=batch)
                    assert r.status_code == 200
                    sent += r.json()["accepted"]
                    batch = []
            if batch:
                r = await ac.post("/publish", json=batch)
                assert r.status_code == 200
                sent += r.json()["accepted"]

            deadline = time.time() + 30.0
            while time.time() < deadline:
                s = (await ac.get("/stats")).json()
                if s["unique_processed"] >= N:
                    break
                await anyio.sleep(0.05)

            elapsed = time.time() - t0
            assert s["unique_processed"] >= N
            assert elapsed < 30.0
