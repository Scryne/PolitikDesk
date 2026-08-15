# S2 — Event Relations & “Hesap Sor” Pipeline Mimari Tasarım Belgesi
**Doküman Sürümü:** v1.0 · **Tarih:** 15 Ağustos 2026 · **Kapsam:** S2 Fazı İlişki ve Hesap Verebilirlik Motoru  
**Prensip:** Evidence-First / Fail-Closed / No Fake Pass / Production-Safe

---

## 1. Mevcut Mimari ve Veri Modeli Özeti

### 1.1 Mevcut Veri Akışı
PolitikDesk veri akışı deterministik ve ayrıştırılmış katmanlardan oluşur:
1. **Ingestion Katmanı:** `config/sources*.yml` → `HttpClient` → `SourceAdapter.fetch()` → `RawItem`
2. **Normalizasyon:** `normalizer.normalize(RawItem)` → `NormalizedArticle` (UTM temizliği, SimHash, Excerpt ≤ 300 kr)
3. **Kümeleme (Clustering):** `assigner.decide()` (saf mantık, ANN kosinüs + jaccard + temporal window) → `events`
4. **İddia Çıkarımı (NLP Claims):** Regex/NLP kuralları → `claims` (tipler: `fact`, `number`, `attribution`, `prediction`, `promise`)
5. **Kanıt Motoru (Evidence Engine):** Deterministik R0–R8 kuralları (LLM yok) → `evidence` & `evidence_status` (`strongly_corroborated`, `partially_corroborated`, `single_source`, `contradicted`, `unverified`, `attribution_verified`)
6. **Tarihsel Bağlam (Context):** `context/related.py` → `event_relations` (`same_thread` / lookback 400 gün)

### 1.2 Event → Claim → Evidence → Provenance Zinciri
```
RawItem (source_slug, url, published_at, extra)
  └── NormalizedArticle (canonical_url, content_hash, simhash, published_at)
        └── Article (id, source_id, event_id, url, title, published_at, tier)
              ├── Event (id, title, centroid_embedding, first_reported_at, vertical)
              └── Claim (id, event_id, claim_text, claim_type, evidence_status, status_reason)
                    └── Evidence (claim_id, article_id, stance, quote_span, status_rule)
```

---

## 2. S2'nin Amacı ve Felsefesi

PolitikDesk **kesinlikle bir siyasi kanaat veya suçlama motoru değildir.**  
S2, "kim suçlu" veya "bu kişi kesinlikle yalan söyledi" gibi editoryal yargılar üretmez.

Bunun yerine **denetlenebilir bir ilişki ve kanıt zinciri grafiği (Evidence / Accountability Graph)** kurar:
```
  [Vaat / Beyan Olayı (TBMM / Açıklama)]
           │ (relation: fulfils / fails / contradicts / updates)
           ▼ [confidence: inferred | supported | verified]
  [İcraat / Karar Olayı (CB Kararnamesi / Resmî Gazete)]
           │
           ▼
  [Denetim Olayı (Sayıştay Raporu / Kamu Zararı Tespiti)]
```
Her adımda:
- Hangi kaynak?
- Hangi tarih?
- Hangi olay ve iddia?
- Hangi kanıtlar destekliyor/çelişiyor?
- İlişki güven skoru nedir?
- Eksik veya belirsiz halka var mı?

---

## 3. S2 Veri Modeli ve İlişki Sözlüğü (Relation Vocabulary)

### 3.1 Veri Modeli Analizi ve Karar
Mevcut şemada `event_relations` tablosu mevcuttur:
```sql
CREATE TABLE event_relations (
  from_event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  to_event_id   BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  relation      TEXT NOT NULL CHECK (relation IN ('precedes', 'updates', 'contradicts', 'same_thread', 'fulfils', 'fails')),
  similarity    REAL,
  created_by    TEXT NOT NULL CHECK (created_by IN ('system', 'user')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (from_event_id, to_event_id, relation),
  CONSTRAINT event_relations_no_self CHECK (from_event_id <> to_event_id)
);
```
S2 için yeni gereksiz tablolar icat edilmeyecektir. İlişki zincirinin zengin kanıt gerekçelendirmesi (evidence rationale, actor, match confidence, scope compatibility) için:
1. `event_relations` tablosuna `confidence` (`REAL`), `evidence_payload` (`JSONB`), `status` (`TEXT CHECK (status IN ('inferred', 'supported', 'verified', 'unresolved'))`) alanları eklenir (Migration 0011).
2. Veritabanı sorguları ve `AccountabilityCase` veri sınıfları bu yapı üzerinden işletilir.

### 3.2 İlişki Sözlüğü (Relation Vocabulary)
| İlişki Tipi | Anlamı | Tetiklenme Kriteri |
|---|---|---|
| `same_thread` | Aynı konu/dizi takibi | Yüksek kosinüs benzerliği + geniş zaman aralığı (aylık bültenler) |
| `precedes` | Zamansal öncülük | İki ilişkili olay arasındaki kronolojik sıra |
| `updates` | Politika / karar güncellemesi | Aynı aktör/kurumun önceki kararını revize eden sonraki kararı |
| `contradicts` | Çelişen beyan veya icraat | Aynı aktörün önceki beyanı ile sonraki beyanı/eylemi arasındaki zıtlık |
| `fulfils` | Vaadin yasalaşması / gerçekleşmesi | `promise` iddiasının TBMM kanun teklifi veya icraat kararıyla hayata geçmesi |
| `fails` | Vaadin reddedilmesi / boşa düşmesi | `promise` teklifinin komisyonda/genel kurulda reddi veya Sayıştayca aksinin tespiti |

### 3.3 Güven Seviyeleri (Confidence Levels)
- `inferred`: Yalnızca semantik benzerlik ve konu örtüşmesi (%60–%74 skor).
- `supported`: Varlık/aktör örtüşmesi + tarih uyumluluğu + kurum bağlamı (%75–%89 skor).
- `verified`: Açık atıf (kanun numarası, teklif sıra no, doğrudan Sayıştay bulgu referansı, %90+ skor).
- `unresolved`: Varlık belirsizliği, tarih uyuşmazlığı veya kapsam farkı durumunda fail-closed düşüş.

---

## 4. Deterministik İlişki Motoru (Relation Engine)

S2 İlişki Motoru black-box LLM'e bağımlı değildir; şeffaf, puanlanabilir ve deterministik bileşenlerden oluşur:

$$\text{RelationScore} = w_{\text{entity}} \cdot S_{\text{entity}} + w_{\text{institution}} \cdot S_{\text{institution}} + w_{\text{topic}} \cdot S_{\text{topic}} + w_{\text{semantic}} \cdot S_{\text{semantic}} + w_{\text{temporal}} \cdot S_{\text{temporal}} + S_{\text{explicit}}$$

### Puanlama Bileşenleri:
1. **Entity Match ($S_{\text{entity}}$):** Aktör (kişi) ve anahtar varlık Jaccard katsayısı.
2. **Institution Match ($S_{\text{institution}}$):** Sorumlu kurum/bakanlık/belediye tam eşleşmesi.
3. **Topic & Scope Match ($S_{\text{topic}}$):** Dikey konu sınıflandırması ve kapsam uyumu.
4. **Semantic Similarity ($S_{\text{semantic}}$):** Vektör gömme kosinüs benzerliği.
5. **Temporal Compatibility ($S_{\text{temporal}}$):** $t_{\text{target}} \ge t_{\text{source}}$ kronoloji denetimi (gelecekteki vaat geçmişteki Sayıştay bulgusunu doğrulayamaz).
6. **Explicit Reference ($S_{\text{explicit}}$):** Kanun no, teklif no veya kurum rapor adı gibi doğrudan referanslar (+0.30 boost).

---

## 5. Grounding ve Fail-Closed Kuralları

1. **Aktör ve Kurum Belirsizliği:** Aynı isimli farklı kişiler veya farklı kurumlar söz konusu olduğunda relation oluşturulmaz (`UNRESOLVED`).
2. **Kapsam ve Birim Farkı:** Sayısal iddialarda birim veya kapsam uyumsuzluğu varsa (ör. 1000 konut vs 1000 fidan) doğrudan karşılaştırma yapılmaz (`SCOPE_MISMATCH`).
3. **Zaman Uyumsuzluğu:** Vaat tarihinden önceki bir denetim raporu "vaadin ihlali" olarak ilişkilendirilemez.
4. **Eksik Kanıt Zinciri:** Zincirdeki birincil kaynak linki veya alıntı eksikse "kanıt zinciri eksik" (`INSUFFICIENT_EVIDENCE`) olarak işaretlenir.

---

## 6. S2 Golden Set ve Değerlendirme Metodolojisi

- **Değerlendirme Dosyası:** `eval/golden_set_accountability_v1.jsonl`
- **İçerik:** En az 15–20 adet manuel etiketlenmiş gerçek siyasi, yasama ve Sayıştay vakası (positive relations, negative controls, ambiguous entities, temporal mismatches, scope mismatches).
- **Hedef Eşikler (Evaluation Thresholds):**
  - **Relation Precision:** $\ge 0.90$
  - **Relation Recall:** $\ge 0.80$
  - **False Relation Rate:** $\le 0.05$
  - **Temporal Compatibility Accuracy:** $1.000$ (%100)

---

## 7. Test ve İzolasyon Stratejisi

- **Unit Testler:** Puanlama motoru, aktör eşleştirme, kapsam denetimi, tarih uyumluluğu, fail-closed durumları.
- **Integration Testler:** `Event -> Relation Engine -> event_relations -> Political Memory Service`.
- **E2E Testler:** Sayıştay denetim bulgusu → Vaat eşleşmesi → Kanıt zinciri → `get_accountability_digest()`.
- **Adversarial Testler:** Aynı isimli farklı aktörler, farklı kurumlar, tarih uyuşmazlığı, sahte benzerlikler.
- **DB Güvenliği:** `$env:PD_CI_REQUIRE_DB="1"` koşulunda autouse fixture ile production DB'ye 0 satır sızıntısı güvencesi.

---

## 8. Risk Kütüğü (Risk Register)

| Risk ID | Risk Tanımı | Olasılık | Etki | Önlem / Mitigasyon |
|---|---|---|---|---|
| **R-S2-1** | Benzer başlıklı alakasız olayların yanlış birleştirilmesi (False Relation) | Orta | Yüksek | Yüksek eşik ($T_{\text{relation}} \ge 0.85$) + zorunlu kurum/aktör eşleşmesi + entity Jaccard filtresi |
| **R-S2-2** | Zamansal tutarsızlık (Sonraki vaadin önceki denetime bağlanması) | Düşük | Yüksek | $t_{\text{finding}} \ge t_{\text{promise}}$ temporal guard kontrolü |
| **R-S2-3** | Sayısal kapsam uyuşmazlığı (Elmalarla armutların kıyaslanması) | Orta | Orta | Sayısal karşılaştırmalarda metric_type ve unit zorunlu kontrolü |
| **R-S2-4** | Canlı DB test kirlenmesi | Düşük | Kritik | `tests/conftest.py` izolasyonunun `event_relations` için de devrede tutulması |
