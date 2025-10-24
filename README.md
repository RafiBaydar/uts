# UTS Event Aggregator (FastAPI + asyncio + SQLite)

Aggregator sederhana untuk menerima event via HTTP, memasukkan ke antrean in-memory (asyncio.Queue), memproses secara asinkron oleh beberapa consumer, dan menjaga idempotensi via dedup (topic, event_id) yang persisten di SQLite.
  
## Fitur singkat

- POST /publish: terima single atau batch event (validasi skema).
- GET /events?topic=...: daftar event unik yang sudah diproses.
- GET /stats: received, unique_processed, duplicate_dropped, topics, uptime_seconds, queue_size.
- GET /healthz: health check.
- Swagger UI: /docs.
  
## Arsitektur (ringkas)
Publisher --> POST /publish --> asyncio.Queue --> consumer worker(s)
                                           |--> SQLite.dedup (PK: topic,event_id)
                                           |--> SQLite.events (data unik)

- FastAPI + asyncio untuk I/O cepat dan worker paralel.
- Idempotensi: INSERT OR IGNORE ke tabel dedup(topic,event_id) → duplikat tidak diproses ulang.
- Persisten: SQLite file dedup.db (di-mount ke host) → dedup tetap efektif setelah restart.
- Ordering: tidak menjamin total ordering (fokus aggregator idempotent). Jika butuh ordering ketat, gunakan sequencer/broker (di luar scope).
- Performa: beberapa worker (default 4), antrean besar (default 10k), SQLite WAL.

## Skema Event (minimal)
>{
>  "topic": "string",
>  "event_id": "string-unik",
>  "timestamp": "ISO8601",
>  "source": "string",
>  "payload": { }
>}

## Quickstart (Docker)
Windows PowerShell (disarankan). Sesuaikan port jika 8080 sudah terpakai.
1. Build image
>docker build -t uts-aggregator .
2. Jalankan container (DB persisten)
>if (!(Test-Path .\data)) { mkdir data | Out-Null }  # folder untuk SQLite
>
>docker rm -f uts-agg 2>$null
>
>$P = (Get-Location).Path
>docker run -d --name uts-agg `
>  -p 8080:8080 `
>  -v "$P\data:/app/data" `
>  uts-aggregator
3. Cek service
>curl.exe http://localhost:8080/healthz
>curl.exe http://localhost:8080/stats
># Swagger: http://localhost:8080/docs

## Contoh Pemakaian
Kirim 1 event (unik)
@'
{"topic":"orders","event_id":"o-1","timestamp":"2025-01-01T00:00:00Z","source":"cli","payload":{"total":123}}
'@ | Out-File -Encoding utf8 payload.json

curl.exe -X POST http://localhost:8080/publish -H "Content-Type: application/json" --data-binary "@payload.json"

Kirim duplikat (simulasi at-least-once)
curl.exe -X POST http://localhost:8080/publish -H "Content-Type: application/json" --data-binary "@payload.json"

Lihat events & stats
curl.exe "http://localhost:8080/events?topic=orders&limit=100"
curl.exe http://localhost:8080/stats


Ekspektasi:

Duplikat → duplicate_dropped naik, tanpa menambah event unik.

Setelah restart container, kirim o-1 lagi → tetap terhitung duplikat (dedup persisten).

Menjalankan tanpa Docker (opsional)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:DEDUP_DB_PATH="$PWD\data\dedup.db"
python -m src.main
# http://localhost:8080/healthz

Endpoint Detail
POST /publish

Body: objek event atau array event.

Response:

{ "accepted": <int>, "queued": <int>, "errors": [ "..."] | null }


Validasi skema: topic, event_id, timestamp(ISO8601), source, payload{}.

GET /events

Query: topic (opsional), limit, offset.

Response:

{ "events": [ ... ], "count": <int> }

GET /stats

Field:

received: jumlah event diterima sejak proses start (in-memory).

unique_processed: jumlah unik kumulatif dari DB (persisten).

duplicate_dropped: jumlah duplikat sejak proses start (in-memory).

topics: daftar topik yang pernah diproses.

uptime_seconds, queue_size.

GET /healthz

{"status":"ok"}.

Pengujian (Unit Tests)

Total 5–10 test (repo ini menyediakan 6). Jalankan di host (bukan di dalam container).

Install alat test:

python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio trio


Jalankan test:

python -m pytest -q tests
# atau subset:
# python -m pytest -q tests\test_dedup.py tests\test_schema_stats.py


Stress test (≥ 5.000 event, ≥ 20% duplikat) sudah disediakan di tests/test_stress.py.

Catatan penting untuk lulus test persisten:
unique_processed pada /stats diambil dari DB (count(*) from dedup), bukan counter in-memory.

Dockerfile (ringkas)

Base: python:3.11-slim

Non-root user

Dependency caching via requirements.txt

CMD: python -m src.main

Port: 8080

Contoh struktur:

FROM python:3.11-slim
WORKDIR /app
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8080
CMD ["python", "-m", "src.main"]

Konfigurasi & Asumsi

Local-only, tanpa layanan eksternal (DB embedded: SQLite).

Volume disarankan: map ./data:/app/data agar dedup persisten lintas restart.

ENV:

DEDUP_DB_PATH (default /app/data/dedup.db)

PORT (default 8080)

LOG_LEVEL (default INFO)

CORS: dibuka untuk kemudahan uji lokal (batasi untuk produksi).

Ordering: tidak dijamin. Jika diperlukan, gunakan partisi/sequencer/broker (di luar scope).

Troubleshooting

Invalid JSON body → pastikan JSON tanpa komentar, kutip ganda "...", dan tanpa koma terakhir.

Queue is full (503) → kirim batch lebih kecil atau naikkan queue_size saat membuat app.

Stats tak langsung naik → tunggu 0.5–1 dtk (consumer async) lalu panggil /stats lagi.

Dedup tak persisten → pastikan volume ./data:/app/data terpasang dan data/dedup.db tidak terhapus.

Port 8080 bentrok → jalankan -p 8081:8080 dan akses http://localhost:8081.

Lisensi

Tugas akademik. Gunakan seperlunya.