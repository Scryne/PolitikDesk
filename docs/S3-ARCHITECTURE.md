# POLİTİKDESK — FAZ S3 PRODUCTION ARCHITECTURE
**Sürüm:** Spec v3.4 / S3.v1  
**Tarih:** 15 Ağustos 2026  
**Durum:** FROZEN & PRODUCTION-READY  

---

## 1. Mimari Genel Bakış

Phase S3, S2'nin deterministik ilişki motorunu (`relation_engine.py`) bozmadan ve üzerine inşa ederek üretim seviyesinde bir boru hattına dönüştürmüştür.

```
                    [ Çoklu Resmî Kaynak Verisi ]
                  (TBMM, Sayıştay, Cumhurbaşkanlığı)
                                │
                                ▼
                       [ events / claims ]
                                │
                                ▼
                   [ Candidate Pre-Filter ]
                 (Bounded Ceiling: N <= 50)
            - Aktör & Kurum Eşleşmesi
            - Konu (Topic) Kesişimi
            - Temporal Pencere (|Δt| <= 400 gün)
            - Entity Jaccard Similarity
                                │
                                ▼
                 [ Relation Orchestrator ]
                     (Engine: s3.v1)
            - Deterministik Kural & Ağırlıklandırma
            - Idempotent Upsert (Zero Duplicate)
                                │
                                ▼
                      [ event_relations ]
             (PK: from_event_id, to_event_id, relation)
             (Index: idx_event_relations_to_event)
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
[ Accountability JSON API ]                   [ Web Editorial Desk ]
  /api/accountability/cases                     /accountability (Digest)
  /api/accountability/cases/:f/:t               /promises (Tracker)
  - Legal Disclaimer                            /memory/:actor (Memory)
  - Epistemic Status (4-State)                  - Epistemic Badges
  - Provenance Traceability                     - Evidence Drawer Details
```

---

## 2. Temel Bileşenler ve Güvenlik Mekanizmaları

### 2.1 Bounded Candidate Retrieval (`candidate_filter.py`)
- $O(N^2)$ tam taramaları önlemek için `filter_candidates_in_memory` ve `fetch_candidate_events_from_db` motorları kuruldu.
- Varsayılan aday limiti 20, mutlak tavan limiti (hard ceiling) **50** olarak sınırlandırılmıştır.
- Aday seçim kriterleri:
  1. Aynı olay (`cand.event_id == source.event_id`) filtre dışı.
  2. Zamansal pencere: $|t_{\text{cand}} - t_{\text{source}}| \le 400\text{ gün}$.
  3. Aktör örtüşmesi (`score += 0.35`).
  4. Kurum örtüşmesi / anayasal akış (`score += 0.25`).
  5. Konu örtüşmesi Jaccard (`score += 0.20`).
  6. Varlık kümesi Jaccard (`score += 0.20`).

### 2.2 Idempotent İlişki Orkestratörü (`orchestrator.py`)
- `RELATION_ENGINE_VERSION = "s3.v1"`.
- `ON CONFLICT (from_event_id, to_event_id, relation) DO UPDATE` ile aynı task 10 kez çalışsa dahi tek bir satır korunur.
- Production schema migration 0012 ile `idx_event_relations_to_event(to_event_id)` ters indeksi, `engine_version` ve `updated_at` eklendi.

### 2.3 Celery Production Wiring (`tasks.py`)
- `politikdesk.link_political_relations` task'ı `bind=True`, `max_retries=2`, `countdown=180` parametreleriyle tanımlandı.
- `app.conf.beat_schedule`'a her 15 dakikada bir (900.0s) periyodik tetikleme eklendi.

### 2.4 Epistemik Güvenlik ve Hukuki Sözleşme (`accountability.py`)
- 4 Aşamalı Epistemik Statü:
  - `VERIFIED`: Resmî kanun/rapor doğrudan atıflı.
  - `SUPPORTED`: Çoklu veri kaynağıyla desteklenen ilişki.
  - `INFERRED`: Yüksek benzerlikli dolaylı ilişki.
  - `UNRESOLVED`: Fail-closed belirsiz durum.
- Hukuki Çekince:
  > *"Bu analiz resmî ve doğrulanmış veri kaynaklarının deterministik eşleştirmesine dayanır. Doğrudan şahsi cezai veya hukuki sorumluluk hükmü içermez; editoryal kanıt zinciridir."*

---

## 3. Doğrulama ve Karşılaştırma Sonuçları

| Bileşen / Metrik | S2 Baseline | S3 Sonuç | S3 Hedef | Durum |
|---|---|---|---|---|
| **Accountability v2 Precision** | — | **1.000** | $\ge 0.90$ | 🟢 PASS |
| **Accountability v2 Recall** | — | **1.000** | $\ge 0.80$ | 🟢 PASS |
| **Accountability v2 F1** | — | **1.000** | — | 🟢 PASS |
| **False Relation Rate** | — | **0.000** | $\le 0.05$ | 🟢 PASS |
| **Temporal Compatibility** | 1.000 | **1.000** | 1.000 | 🟢 PASS |
| **Legislation Precision** | 1.000 | **1.000** | $\ge 0.90$ | 🟢 PASS |
| **Legislation Recall** | 0.824 | **0.824** | $\ge 0.80$ | 🟢 PASS |
| **Candidate Hard Ceiling** | — | **50 (Hard Capped)** | $\le 50$ | 🟢 PASS |
| **Mypy Typecheck** | 0 hata (137 dosya) | **0 hata (140 dosya)** | 0 | 🟢 PASS |
| **Pytest Suite** | 795 pass | **800 pass, 0 fail** | 100% pass | 🟢 PASS |
| **Production DB Leakage** | 0 row | **0 row (56/171/182/11)** | 0 | 🟢 PASS |
