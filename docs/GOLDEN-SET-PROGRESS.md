# Golden Set Genişletme ve Kalite Takip Kütüğü (B-57)

**Amaç:** B-57 gereği Golden Set veri setini 300 makale + 150 iddia hacmine ulaştırmak ve doğruluğunu garanti altına almak.  
**Mevcut Durum (15 Ağustos 2026):** 55 makale · 24 iddia (%18 makale, %16 iddia)  
**Hedef:** 300 makale · 150 iddia  
**Oran Kuralı:** ~0,5 iddia / makale dengesi korunur.

---

## 1. Haftalık İlerleme ve Hedef Tablosu

| Hafta | Tarih Aralığı | Hedeflenen Makale | Gerçekleşen Makale | Hedeflenen İddia | Gerçekleşen İddia | Kümülatif Tamamlanma | Not & Denetim |
|---|---|---|---|---|---|---|---|
| **Başlangıç** | 15 Ağustos 2026 | 55 | 55 | 24 | 24 | %18,3 / %16,0 | Başlangıç baseline donduruldu (`eval/golden_set_v1.jsonl`, `eval/golden_claims_v1.jsonl`) |
| **Hafta 1 (W1)** | 16–22 Ağustos 2026 | +35 (90) | | +18 (42) | | | İlk haftalık genişletme koşumu |
| **Hafta 2 (W2)** | 23–29 Ağustos 2026 | +35 (125) | | +18 (60) | | | Siyaset/yasama dikey örnekleri dahil |
| **Hafta 3 (W3)** | 30 Ağu – 05 Eyl 2026 | +35 (160) | | +18 (78) | | | Yarı eşik (150 makale) |
| **Hafta 4 (W4)** | 06–12 Eylül 2026 | +35 (195) | | +18 (96) | | | Çapraz teyit / çok kaynaklı olaylar |
| **Hafta 5 (W5)** | 13–19 Eylül 2026 | +35 (230) | | +18 (114) | | | Çelişkili olay ve iddia örnekleri |
| **Hafta 6 (W6)** | 20–26 Eylül 2026 | +35 (265) | | +18 (132) | | | Nadir gösterge ve kurumlar |
| **Hafta 7 (W7)** | 27 Eyl – 03 Eki 2026 | +35 (300) | | +18 (150) | | | **300+150 Hedef Kapanışı** |

---

## 2. Tekrarlanabilir Etiketleme İş Akışı

1. **Makale Seçimi (`eval/golden_set_v1.jsonl`):**
   - Canlı akıştan veya geçmiş bültenlerden farklı yayın gruplarına (TÜİK, TCMB, Resmî Gazete, AA, Reuters, BloombergHT, vb.) ait metinler seçilir.
   - Aynı olayı anlatan makalelere aynı `event_id` verilir.
   - JSONL satır biçimi:
     ```json
     {"article_id": "art-056", "event_id": "ev-037", "title": "...", "excerpt": "...", "published_at": "2026-08-15T10:00:00+03:00", "entities": ["TÜİK"], "key_entities": ["TÜİK"]}
     ```

2. **İddia ve Kanıt Seçimi (`eval/golden_claims_v1.jsonl`):**
   - Makalelerden çıkarılan olgusal/sayısal iddialar deterministik kural motoru için etiketlenir.
   - JSONL satır biçimi:
     ```json
     {
       "claim_id": "gc-025",
       "claim_text": "TÜİK Temmuz ayı işsizlik oranını %8,8 olarak açıkladı.",
       "claim_type": "number",
       "normalized_value": {"value": 8.8, "unit": "percent", "period": "2026-07"},
       "expected_status": "strongly_corroborated",
       "expected_rule": "R2",
       "evidence": [
         {"source_slug": "tuik", "tier": 1, "kind": "official", "stance": "supports", "independence_group": "tuik"}
       ]
     }
     ```

3. **Otomatik Doğrulama ve Ölçüm:**
   - Yeni satırlar eklendikten sonra `eval/run.py` koşturulur:
     ```bat
     pd eval
     ```
   - JSONL sözdizimi ve formatı `tests/test_eval_tools.py` tarafından otomatik denetlenir.

---

## 3. Kalite ve Kabul Kriterleri

- [ ] Hiçbir makalede eksik `published_at` veya `event_id` bulunamaz.
- [ ] Sayısal iddiaların `normalized_value` alanı B-82 tam tarih veya dönem formatına uygun olmalıdır.
- [ ] `eval/run.py` çıktısında `pairwise precision >= 0.90` ve `false merge <= 0.05` korunmalıdır.
- [ ] `evidence_status doğruluğu >= 0.95` ve `sayısal normalizasyon >= 0.95` korunmalıdır.
