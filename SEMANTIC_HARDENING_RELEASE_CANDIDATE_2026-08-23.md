# POLITIKDESK — SEMANTIC HARDENING, API PARITY & RELEASE CANDIDATE VERIFICATION

**Tarih:** 23 Ağustos 2026  
**Durum:** RELEASE CANDIDATE (RC-1) READY  
**Sürüm:** 0.1.0  
**Kapsam:** Temporal Data Semantics, HTML ↔ JSON API Semantic Parity, Pipeline Backlog Health Semantics & Release Verification

---

## 1. EXECUTIVE SUMMARY

PolitikDesk platformu kapsamlı mühendislik denetimleri ve bağımsız operasyonel testlerden başarıyla geçmiştir. Bu aşamada sistemin **Code Freeze** ve **Release Candidate** durumuna geçmeden önce domain semantiği ve veri yorumlama güvenliği açısından üç kritik alan incelenmiş ve sertleştirilmiştir:

1. **Temporal Data Semantics:** Tarih damgası eksik veya belirsiz olan siyasi beyanların `_parse_year()` tarafından yapay olarak cari yıla (`2026`) atanması sorunu giderilmiştir. Tip güvenli `int | None` modeli uygulanmış, tarihsiz kayıtlar zaman serisi karşılaştırmalarından izole edilmiş (`undated_statements`) ve sahte söylem çelişkisi (false positive position shift) riski tamamen ortadan kaldırılmıştır.
2. **HTML ↔ JSON API Semantic Parity:** `GET /memory/compare` (HTML Arayüzü) ve `GET /api/memory/compare` (JSON API) uçları arasındaki sorgu parametreleri, limit sınırlandırmaları (`1..100`), Türkçe/Unicode aktör aramaları (`Mehmet Şimşek`, `Özgür Özel`) ve veri çıktıları birebir semantik eşitliğe kavuşturulmuştur.
3. **Pipeline Backlog Health Semantics:** `politikdesk/pipeline_health.py` içindeki çift eksenli sağlık modeli (`worker_liveness_age` + `backlog_limit`) incelenmiş; toplu arşiv yüklemeleri (Bulk Import) ile kilitlenmiş boru hattı (Stuck Pipeline) senaryoları arasındaki operasyonel semantik sınırları belgelenmiştir.

Tüm doğrulamalar (1936 birim/entegrasyon testi, Ruff linter, Mypy tip denetimi, pip-audit güvenlik taraması, mimari koruma denetleyicisi ve Docker deployment bütünlüğü) %100 başarıyla tamamlanmıştır.

---

## 2. INITIAL STATE

Audit başlangıcında sistem durumu:
- Git HEAD: `678e06b94505` (Clean working tree + previous audit enhancements)
- Pytest Suite: 1917 test başarılı.
- `_parse_year()` fonksiyonu `None`, `""` veya geçersiz girdi aldığında `2026` tamsayısını döndürüyordu.
- `/memory/compare` arayüzü ile `/api/memory/compare` uç noktası arasında limit yönetimi ve tarihsiz beyanların ayrıştırılmasında eksiklikler mevcuttu.
- `check_deployment.py` yerel çalışma ortamındaki son düzenlemelerin konteynerlere yansıtılması için senkronizasyon kontrolü uyguluyordu.

---

## 3. TEMPORAL DATA SEMANTICS ANALYSIS

### 3.1 İncelenen Fonksiyon ve Sorun
`politikdesk/political_memory/comparison.py` dosyasındaki `_parse_year(dt_str: str | None) -> int` fonksiyonu:
```python
# Eski Davranış
def _parse_year(dt_str: str | None) -> int:
    if not dt_str:
        return 2026
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.year
    except Exception:
        match = re.search(r"\b(20\d{2})\b", str(dt_str))
        return int(match.group(1)) if match else 2026
```

### 3.2 Girdi Matrisi ve Analitik Sonuçlar
| Girdi | Eski Çıktı | Domain Etkisi | Yeni Semantik Çıktı |
|---|---|---|---|
| `None` | `2026` | ❌ Tarihi olmayan beyanı 2026 yapıp "yeni beyan" sanma | `None` |
| `""` | `2026` | ❌ Boş metni cari yıla atama | `None` |
| `" "` | `2026` | ❌ Boşluk metnini cari yıla atama | `None` |
| `"unknown"` | `2026` | ❌ Bilinmeyen tarihi 2026 sanma | `None` |
| `"invalid"` | `2026` | ❌ Geçersiz metni 2026 sanma | `None` |
| `"2026"` | `2026` | ✅ Geçerli yıl | `2026` |
| `"2025-01-15"` | `2025` | ✅ ISO tarih | `2025` |
| `"2025/01/15"` | `2025` | ✅ Slash tarih | `2025` |
| `"15.01.2025"` | `2025` | ✅ Yerelleştirilmiş nokta tarih | `2025` |
| `"2025-01-15T12:30:00"` | `2025` | ✅ ISO timestamp | `2025` |
| `"0"` | `2026` | ❌ Sıfırı 2026'ya yuvarlama | `None` |
| `"0000"` | `2026` | ❌ Sıfırları 2026'ya yuvarlama | `None` |
| `"-1"` | `2026` | ❌ Negatifi 2026'ya yuvarlama | `None` |
| `"20250"` | `2026` | ❌ Hatalı 5 basamaklı sayıyı 2026 sanma | `None` |
| `"1999-12-31"` | `1999` | ✅ 20. yy sonu geçerli tarih | `1999` |
| `"15 Ocak 2024"` | `2024` | ✅ Türkçe serbest metin içi yıl | `2024` |
| `"2150"` | `2026` | ❌ Siyaseten mantıksız aşırı gelecek | `None` |

### 3.3 Domain Açısından Tehlike Senaryosu
Bir siyasi aktörün 3 beyanı olduğunda:
- **Beyan A (2018):** "Faiz artışına karşıyız." (oppose)
- **Beyan B (Tarih Bilinmiyor):** "Sıkılaşmayı destekliyoruz." (support)
- **Beyan C (2024):** "Faiz artışına karşıyız." (oppose)

`split_year = 2020` seçildiğinde:
- **Eski Sistemde:** Beyan B `2026` atanıyordu. 2020 sonrası listesine (later) giriyordu. Sistem A (2018, oppose) ile B (2026, support) arasında çelişki tespit edip:
  > *"Aktör 2020 öncesinde eleştirdiği politikayı 2020 sonrasında desteklemiştir."*
  diyerek **tamamen sahte bir tutarsızlık ve pozisyon kayması** üretiyordu.
- **Yeni Modelde:** Beyan B `year=None` olarak çözümlenir ve `undated_statements` havuzuna ayrılır. 2018 (oppose) ile 2024 (oppose) karşılaştırılır ve aktörün tutarlı olduğu doğru bir şekilde raporlanır (`shift_detected=False`, `consistency_score=0.90`).

---

## 4. SELECTED DOMAIN MODEL

1. **Tip Güvenliği ve Açıklık:** `_parse_year(dt_str: str | None) -> int | None`
   - Geçerli siyasi/tarihsel aralık: `1900 <= year <= 2100`.
   - ISO `fromisoformat` ve regex `\b(19\d{2}|20\d{2})\b` bir arada çalışır.
   - Tanımsız/hatalı/boş girdiler daima `None` döner.
2. **TemporalStatement Veri Modeli:**
   - `year: int | None`
   - `date_str: str` ("Bilinmiyor" veya geçerli tarih dizesi)
3. **StatementComparisonResult Veri Modeli:**
   - `earlier_statements: list[TemporalStatement]` (year < split_year)
   - `later_statements: list[TemporalStatement]` (year >= split_year)
   - `undated_statements: list[TemporalStatement]` (year is None — izole havuz)
4. **Boş Aktör Koruması:** Aktör adı boş veya sadece boşluktan oluşuyorsa veritabanına sorgu atılmadan temiz boş karşılaştırma nesnesi döndürülür.

---

## 5. API SEMANTIC PARITY ANALYSIS

`GET /memory/compare` (HTML) ve `GET /api/memory/compare` (JSON API) arayüzleri denetlenmiş ve tam eşitlik sağlanmıştır:

| Parametre / Davranış | GET /memory/compare (HTML) | GET /api/memory/compare (JSON) | Eşitlik Durumu |
|---|---|---|---|
| `actor` | Varsayılan `"Mehmet Şimşek"`, boşluk strip | Varsayılan `"Mehmet Şimşek"`, boşluk strip | ✅ Tam Eşit |
| `topic` | `""` veya slug (`topic if topic else None`) | `None` veya slug (`topic if topic else None`) | ✅ Tam Eşit |
| `year` | Varsayılan `2025` | Varsayılan `2025` | ✅ Tam Eşit |
| `limit` | Varsayılan `50` (1..100 aralığına kenetlenir) | Varsayılan `50` (1..100 aralığına kenetlenir) | ✅ Tam Eşit |
| `shift_detected` | Analitik Değerlendirme panosu & Rozet | JSON `shift_detected: bool` | ✅ Semantik Eşit |
| `consistency_score`| KPI Kutusu `%{int(score*100)}` | JSON `consistency_score: float` | ✅ Semantik Eşit |
| `undated_statements`| "Tarihi Belirsiz Beyanlar" kartı | JSON `undated_statements: list` | ✅ Semantik Eşit |
| Türkçe Karakterler | UTF-8 tam destek (`Şimşek`, `Özel`, vb.) | UTF-8 JSON response | ✅ Tam Eşit |

---

## 6. PIPELINE HEALTH ANALYSIS & OPERATIONAL LIMITS

### 6.1 Çift Eksenli Sağlık Mimarisi
`politikdesk/pipeline_health.py` aşama sağlığını iki bağımsız eksende değerlendirir:
1. **İşçi Canlılığı ve Gecikme Ekseni (`oldest_hours`):** İddia çıkarımında `max(claims_attempted_at)` veya ilk eklenme anına bakar. İşçi Celery üzerinde çalışıyor ve 10 dakikada bir kuyruğu deniyorsa yaş ekseni daima yeşildir.
2. **Kuyruk Boşalma Kapasitesi Ekseni (`backlog_limit = 180`):** Görevin tasarım hızı 30 olay/saattir. 6 saatlik alarm penceresinde sistemin eritebileceği maksimum olay sayısı 180'dir. 180'in üzerindeki kuyruklar "kuyruk kapanmıyor / varış hızı kapasiteyi aşıyor" durumunu işaret eder ve kırmızı alarm verir.

### 6.2 Operasyonel Sınır Belgesi (Documented Operational Limitation)
- **Senaryo A (Sağlıklı Toplu İçe Aktarım / Bulk Import):** Arşivden tek seferde 1500 olay yüklendiğinde kuyruk sayısı 180'i aşacağı için aşama geçici olarak `red` veya `amber` verebilir. İşçi canlıdır ancak kuyruğun erimesi matematiksel olarak 50 saat sürecektir. Bu durum sistem arızası değil, planlı operasyonel birikmedir.
- **Senaryo B (Kilitlenmiş Boru Hattı / Stuck Pipeline):** İşçi durduğunda `oldest_hours` 6 saati aşar ve kuyruk boyundan bağımsız olarak kırmızı alarm üretir.

`pipeline_health.py` modülü tasarım kuralı gereği (`"Bu modül politikdesk.llm import ETMEZ ve kanıt motoruna dokunmaz; yalnızca sayar."`) deterministik SQL sorgularıyla çalışır. Bu operasyonel davranış bilinçlidir ve operasyon ekibi için **DOKÜMANTE EDİLMİŞ OPERASYONEL SINIRLILIK** olarak tescil edilmiştir.

---

## 7. CHANGES MADE

1. **`politikdesk/political_memory/comparison.py`:**
   - `_parse_year` fonksiyonu `int | None` döndürecek şekilde yeniden yazıldı.
   - `TemporalStatement` veri modeline `year: int | None` ve güvenli `date_str` eklendi.
   - `StatementComparisonResult` modeline `undated_statements: list[TemporalStatement]` alanı eklendi.
   - `compare_actor_statements` fonksiyonunda boş/boşluk aktör adı koruması ve tarihsiz kayıtları izole etme mantığı uygulandı.
2. **`politikdesk/web/api.py`:**
   - `get_memory_comparison` uç noktasında limit sıkılaştırması (`max(1, min(limit, 100))`) ve topic normalizasyonu sağlandı.
3. **`politikdesk/web/comparison_view.py`:**
   - HTML görünüm fonksiyonuna `limit` parametresi eklendi ve tarihsiz beyanlar için bilgilendirici izole kart yapısı entegre edildi.
4. **`tests/test_political_memory_comparison.py`:**
   - 19 farklı girdi durumunu test eden `test_parse_year_exhaustive_matrix` parametrik testi eklendi.
   - `test_undated_statement_invariant_protection` ile tarihsiz beyanların yapay çelişki üretmediği doğrulandı.
   - `test_compare_actor_statements_empty_actor` eklendi.
   - `test_true_semantic_parity_html_vs_json_api` ile HTML ve JSON arayüzlerinin birebir eşitliği doğrulandı.
   - `test_api_turkish_characters_and_encoding` ile Türkçe UTF-8 uyumluluğu korundu.

---

## 8. REGRESSION TESTS & VERIFICATION RESULTS

### 8.1 Test Çıktıları
```text
tests/test_political_memory_comparison.py: 25 PASSED (100%)
tests/test_pipeline_health.py: 27 PASSED (100%)
tests/test_export_and_api.py: 5 PASSED (100%)
Full Test Suite: 1936 passed in 46.55s
```

### 8.2 Kalite, Tip ve Güvenlik Denetimleri
- **Ruff:** `All checks passed!` (0 hata)
- **Mypy:** `Success: no issues found in 183 source files`
- **Pip-Audit:** `No known vulnerabilities found`
- **Architecture Guard:** `[OK] Mimari kurallar temiz (politikdesk/evidence). [OK] Koruma dogrulandi.`
- **Deployment Checker:** `[SONUC] [PASS] DAGITIM VE SURUM BUTUNLUGU KAPISI BASARIYLA GECTI.`

---

## 9. RELEASE CANDIDATE STATUS

Aşağıdaki kontrol kriterleri doğrulanmıştır:
- [x] İlgisiz dosya değişikliği yok
- [x] Debug kodu veya geçici dosya yok
- [x] Test bypass veya devre dışı bırakma yok
- [x] Zayıflatılmış güvenlik veya doğrulama yok
- [x] Ölü kod veya kullanılmayan import yok
- [x] Geriye dönük API uyumluluğu korundu

**RELEASE CANDIDATE STATUS: READY**
PolitikDesk Platformu Release Candidate (RC-1) aşamasına geçiş ve Code Freeze için tamamen hazırdır.
