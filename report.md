## T1 – Jelaskan karakteristik utama sistem terdistribusi dan trade-off yang umum pada desain Pub-Sub log aggregator.

Sistem terdistribusi dicirikan oleh concurrency, ketiadaan global clock, dan partial failures—komponen bisa gagal sebagian tanpa menjatuhkan keseluruhan sistem. Konsekuensinya, desain harus mengelola heterogenitas, latensi jaringan, dan penjadwalan yang tak deterministik, sambil menjaga scalability dan fault tolerance (Coulouris et al., 2012).

Pada log aggregator berbasis publish–subscribe (Pub-Sub), trade-off yang umum:
- Decoupling vs control: longgar (publisher tidak tahu subscriber), tetapi kontrol backpressure/ordering perlu mekanisme tambahan.
- Performance vs guarantees: throughput & latensi bagus jika jaminan ordering dan delivery dilonggarkan.
- Consistency vs availability: praktik umum memilih eventual consistency dan idempotent consumer agar at-least-once delivery tetap aman dari duplikasi.

Intinya, untuk agregasi log berskala besar, dedup/idempotency di consumer lebih ekonomis daripada memaksakan total ordering atau exactly-once end-to-end (Coulouris et al., 2012; van Steen & Tanenbaum, 2023).

## T2 – Bandingkan arsitektur client-server vs publish-subscribe untuk aggregator. Kapan memilih Pub-Sub? Berikan alasan teknis.

Client–server cocok untuk request–reply deterministik dan kontrol langsung atas error; namun fan-out buruk dan terjadi tight coupling—klien mengetahui lokasi/waktu server. Sebaliknya, publish–subscribe adalah indirect communication: publisher mem-publish ke topic; subscriber menerima sesuai ketertarikan. Hasilnya loose coupling (ruang & waktu), asynchrony, dan scalability (Coulouris et al., 2012).

Pilih Pub-Sub bila:
- Sumber event banyak, subscriber dinamis, dan fan-out besar.
- Diperlukan decoupling identitas/waktu serta toleransi late joiners.

Pilih client–server bila:
- Pola query/command sinkron diprioritaskan.
- Per-request determinism dan kontrol error langsung lebih penting.

## T3 – Uraikan at-least-once vs exactly-once delivery semantics. Mengapa idempotent consumer krusial di presence of retries?

At-least-once memastikan setiap pesan paling tidak dikirim sekali; karena retry, duplikasi bisa terjadi. Exactly-once menghindari duplikasi dan kehilangan, tetapi mahal/kompleks (koordinasi, dedup state, dan transaksi end-to-end). Dalam praktik, banyak sistem memilih at-least-once + idempotent consumer: efek pemrosesan tetap sama meski event yang sama diproses berulang. Secara klasik, keandalan pesan dibahas dengan sifat validity (yang benar akhirnya terkirim) dan integrity (tidak dibuat-buat/duplikat)—namun untuk mencapainya secara ketat perlu protokol kuat; jika memakai retransmisi, konsumen harus idempotent (Coulouris et al., 2012). Aggregator kita menerapkan dedup (topic, event_id) di SQLite sehingga retry dari publisher aman; hasilnya secara state mendekati exactly-once walau saluran hanya at-least-once.

## T4 – Rancang skema penamaan untuk topic dan event_id (unik, collision-resistant). Jelaskan dampaknya terhadap dedup.

Penamaan memisahkan identifier (identitas stabil, tidak terikat lokasi) dari address (lokasi saat ini). Untuk event streaming, topic berfungsi sebagai namespace/kanal, event_id sebagai unique identifier per topic (Coulouris et al., 2012). Prinsip: gunakan collision-resistant ID (mis. UUID v4/v7) atau komposit (timestamp ISO8601 + sumber + urutan lokal) sehingga probabilitas tabrakan sangat kecil. Hindari makna semantik yang bisa berubah (alamat/host) dalam ID—ID harus tetap valid meski migrasi/replicasi terjadi (analoginya di DNS: pemisahan nama dan alamat). Dengan ID unik yang location-independent, dedup cukup INSERT OR IGNORE pada (topic,event_id), cepat dan deterministik (Coulouris et al., 2012; van Steen & Tanenbaum, 2023).

## T5 – Bahas ordering: kapan total ordering tidak diperlukan? Usulkan pendekatan praktis (mis. event timestamp + monotonic counter) dan batasannya.

Total ordering diperlukan jika semua replika harus mengeksekusi state machine replication dengan urutan identik. Namun untuk log aggregation, sering tidak perlu ordering global—yang penting idempotency dan eventual convergence; urutan per-topic yang weak sudah cukup. Jika butuh urutan ringan, gunakan timestamp event + monotonic counter lokal sebagai tie-breaker; untuk sistem multi-produser, dapat ditambah Lamport clock/sequence per sumber. Keterbatasan: jam dinding bisa skew, sehingga urutan hanya approximate; Lamport clock memberi total order yang konsisten dengan happened-before, tetapi bukan real time. Untuk total order ketat lintas sumber, butuh totally ordered multicast atau broker/sequencer terpusat (biaya latensi) (van Steen & Tanenbaum, 2023).

## T6 – Identifikasi failure modes (duplikasi, out-of-order, crash). Jelaskan strategi mitigasi (retry, backoff, durable dedup store).

Failure modes umum pada pipeline event:
- Duplikasi akibat retry → mitigasi: idempotent consumer + durable dedup store (kunci (topic, event_id)).
- Out-of-order karena variasi jalur/latensi → mitigasi: timestamp, window kecil per key, atau causal/FIFO bila perlu.
- Crash pada publisher/consumer → mitigasi: retry dengan backoff, logging jelas untuk duplikat, serta persistensi pada dedup agar post-crash tidak double apply.

Secara prinsip, partial failures adalah kondisi normal; arsitektur harus fault tolerant: masking failures via retries/replication dan recovery setelah crash. Pilih jaminan komunikasi grup (reliable/FIFO/causal/atomic) sesuai kebutuhan; jangan bayar lebih dari yang diperlukan (Coulouris et al., 2012; van Steen & Tanenbaum, 2023).

## T7 – Definisikan eventual consistency pada aggregator; jelaskan bagaimana idempotency + dedup membantu mencapai konsistensi.

Eventual consistency: bila tidak ada update baru untuk durasi yang cukup, semua replika akhirnya konvergen; model ini lazim dan “murah” untuk sistem baca-berat, dengan konflik tulis yang jarang (van Steen & Tanenbaum, 2023). Pada aggregator, write adalah append log event; read (GET /events,/stats) tidak mengubah state. Karena pengiriman at-least-once dapat menghadirkan duplikasi dan reordering, idempotency + dedup menjamin state hasil sama meski ada retry. Ini memberi konsistensi eventual di storage hasil (himpunan event unik per topic) sambil menjaga availability dan throughput. Saat klien mengakses replika berbeda (analogi cache/DNS), perilaku bisa sementara tidak sinkron; namun dengan propagasi update yang terjamin, keadaan akan konvergen (van Steen & Tanenbaum, 2023).

## T8 – Rumuskan metrik evaluasi sistem (throughput, latency, duplicate rate) dan kaitkan ke keputusan desain.

Throughput (event/s) dipengaruhi decoupling Pub-Sub dan jumlah worker async; kita targetkan ≥5.000 event (≥20% duplikat). Latency (penerimaan→tersedia di /events) bergantung panjang antrean dan I/O SQLite; WAL mode + batch insert membantu. Duplicate rate memantau kualitas jaringan/publisher; harus tinggi drop-rate (duplicate_dropped) dibanding unique_processed untuk menandai dedup efektif. Availability dicapai dengan idempotent consumer + dedup persisten (tahan restart). Consistency level: eventual; /stats menyediakan pengamatan received, unique_processed, duplicate_dropped, topics, uptime sebagai dasar SLO internal. Trade-off: menolak total ordering untuk kinerja (Bab 5), memanfaatkan sifat sistem terdistribusi (concurrency, partial failure; Bab 1), memilih Pub-Sub untuk loose coupling (Bab 2), menegakkan at-least-once + idempotency (Bab 3), skema penamaan unik (Bab 4), serta mitigasi kegagalan dengan durable dedup (Bab 6) menuju eventual consistency (Bab 7). (Coulouris et al., 2012; van Steen & Tanenbaum, 2023).

## Ringkasan Sistem Dan Arsitektur
    [Publisher(s)]
         |  POST /publish  (batch/single)
         v
     [FastAPI Ingress] --> [asyncio.Queue] --> [Consumer Workers]
                                     |                |
                                     v                v
                          [Dedup Store (SQLite)]  <---|  (INSERT OR IGNORE by (topic,event_id))
                                     |
                                     |--> GET /events?topic=...
                                     |--> GET /stats (received, unique_processed, duplicate_dropped, topics, uptime)


## Link Video Youtube Demonstrasi Aggregator
https://youtu.be/9vzZSC_RhJE

## Link Laporan UTS
https://drive.google.com/file/d/1p18MjMBaMx98NQnSCrY-iuug2CIG4isc/view?usp=sharing
