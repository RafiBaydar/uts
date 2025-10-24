## T1 – Jelaskan karakteristik utama sistem terdistribusi dan trade-off yang umum pada desain Pub-Sub log aggregator.

Sistem terdistribusi dicirikan oleh concurrency, absence of a global clock, dan independent failures, yang menuntut desain dengan distribution transparency, openness, dependability, dan scalability (Tanenbaum & van Steen, Bab 1 hlm. 3–24).
Dalam Pub-Sub log aggregator, muncul empat trade-off pokok:
1. Consistency vs Availability – eventual consistency dipilih agar layanan tetap aktif saat sebagian node gagal.
2. Throughput vs Ordering – total ordering menambah delay.
3. Latency vs Durability – logging persisten meningkatkan ketahanan tetapi memperlambat propagasi.
4. Fault tolerance vs Complexity – replikasi & dedup store menambah keandalan namun memperumit koordinasi.
Pub-Sub menekankan loose coupling & asynchronous communication* yang cocok untuk skala besar (Coulouris et al., Bab 1 hlm. 16–26).

## T2 – Bandingkan arsitektur client-server vs publish-subscribe untuk aggregator. Kapan memilih Pub-Sub? Berikan alasan teknis.

Model client-server menggunakan komunikasi sinkron 1-to-1, sedangkan publish-subscribe bersifat indirect & asynchronous melalui broker (Tanenbaum & van Steen, Bab 2 hlm. 68–108).
Pub-Sub dipilih saat sistem memerlukan:
- Scalability horizontal (ribuan subscriber).
- Decoupling in time and space (subscriber dapat offline).
- Streaming event asinkron berfrekuensi tinggi.
Client-server unggul untuk request-reply deterministik. Pub-Sub menurunkan temporal coupling dan meningkatkan fault isolation, meski kontrol ordering lebih kompleks (Coulouris et al., Bab 6 hlm. 230–274).

## T3 – Uraikan at-least-once vs exactly-once delivery semantics. Mengapa idempotent consumer krusial di presence of retries?

At-least-once menjamin pengiriman dengan risiko duplikasi, sedangkan exactly-once menghindari duplikasi tetapi mahal karena koordinasi (Tanenbaum & van Steen, Bab 4 hlm. 208–245). Ketika jaringan tidak baik, retry dapat menimbulkan duplikat, sehingga idempotent consumer penting agar pemrosesan berulang tidak mengubah hasil akhir (Coulouris et al., Bab 6 hlm. 254–262). Kombinasi dedup store & idempotency memungkinkan sistem mencapai eventual consistency tanpa overhead komit dua-fase.

## T4 – Rancang skema penamaan untuk topic dan event_id (unik, collision-resistant). Jelaskan dampaknya terhadap dedup.

Nama harus unique, location-independent, persistent (Tanenbaum & van Steen, Bab 6 hlm. 325–333).
Skema:
Topic: hierarki (logs.app.component.level) untuk filtering efisien.
event_id: gabungan source_uuid + timestamp + counter atau hash (SHA-256).
Dampaknya yaitu false positive/negative pada dedup store dan mempercepat lookup (Coulouris et al., Bab 13 hlm. 569–584).

## T5 – Bahas ordering: kapan total ordering tidak diperlukan? Usulkan pendekatan praktis (mis. event timestamp + monotonic counter) dan batasannya.

Total ordering tidak wajib jika event antar-topic independen, cukup causal atau per-partition ordering (Tanenbaum & van Steen, Bab 5 hlm. 260–299). Pendekatan praktis: gunakan timestamp + monotonic counter atau Lamport clock untuk urutan per-producer. Keterbatasannya ialah drift jam fisik yang dapat menyebabkan reordering. Namun metode ini lebih skalabel karena tidak memerlukan konsensus global (Coulouris et al., Bab 14 hlm. 595–610).

## T6 – Identifikasi failure modes (duplikasi, out-of-order, crash). Jelaskan strategi mitigasi (retry, backoff, durable dedup store).

Kegagalan umum: duplikasi pesan, out-of-order delivery, crash consumer, dan partition jaringan (Tanenbaum & van Steen, Bab 8 hlm. 462–509).
Mitigasi:
- Retry + exponential backoff untuk packet loss.
- Durable dedup store (key-value log_id → status).
- Checkpoint + ack tracking untuk recovery.
- Leader replication / quorum write pada broker.
Pendekatan ini menyeimbangkan reliabilitas dan kinerja (Coulouris et al., Bab 15 hlm. 630–671).

## T7 – Definisikan eventual consistency pada aggregator; jelaskan bagaimana idempotency + dedup membantu mencapai konsistensi.

Eventual consistency berarti semua replica akhirnya menyatu bila tidak ada update baru (Tanenbaum & van Steen, Bab 7 hlm. 392–410). Dalam aggregator, broker dan consumer bisa menyimpan salinan sementara inkonsisten. Idempotent processing menjamin re-apply event tidak mengubah hasil, dan dedup store mencegah anomali (Coulouris et al., Bab 18 hlm. 782–814). Dua mekanisme ini mewujudkan strong eventual consistency tanpa replicated transaction mahal.

## T8 – Rumuskan metrik evaluasi sistem (throughput, latency, duplicate rate) dan kaitkan ke keputusan desain.

Tiga metrik utama Pub-Sub aggregator:
1. Throughput (event per detik) → bergantung pada komunikasi & replikasi (Bab 4 & 7).
2. Latency → waktu publish-deliver; dipengaruhi ordering & durability.
3. Duplicate rate → proporsi duplikasi; menurun dengan dedup store efisien.
Trade-off utama: menurunkan latency sering mengurangi durability, meningkatkan throughput dapat menaikkan duplicate rate. Pilihan parameter ditentukan oleh prioritas aplikasi (low-latency trading vs audit logging) (Tanenbaum & van Steen, Bab 1 hlm. 10–24; Coulouris et al., Bab 21 hlm. 915–964).

## Ringkasan Sistem Dan Arsitektur
[Publishers] --HTTP /publish--> [Aggregator API]
    -> in-memory asyncio.Queue -> [Workers/Consumers]
    -> Dedup Store (SQLite, key=(topic,event_id), INSERT OR IGNORE)
    -> Events table (for GET /events)
    -> /stats (received, unique_processed, duplicate_dropped, topics, uptime)

## Link Video Youtube Demonstrasi Aggregator
https://youtu.be/9vzZSC_RhJE
