"""Vercel ve vitrin (showcase) ortamları için zengin demo verileri.

Veritabanı henüz yapılandırılmamış veya boş olduğunda Vercel üzerindeki
canlı arayüzün boş ve yavaş kalmasını önler; PolitikDesk'in tüm özelliklerini
(kanıt kütüğü, salience kırılımı, X tweeti üretimi, hesap sor çapraz analizi,
siyasi hafıza ve vaat takibi) anında ve yüksek hızda (< 20 ms) sergiler.
"""

from __future__ import annotations

from typing import Any

DEMO_BANNER_HTML = """
<div class="panel" style="background:var(--color-bg-subtle);border:1px solid var(--color-border);margin-bottom:var(--space-6);padding:var(--space-3) var(--space-4);border-radius:var(--radius-md)">
  <div class="row" style="justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-2)">
    <div class="row tight" style="align-items:center">
      <span class="badge strong" style="font-size:11px;padding:3px 8px;background:var(--color-primary);color:var(--color-bg)">Canli Vitrin Modu</span>
      <span style="font-size:var(--text-xs);color:var(--color-fg-muted)">PolitikDesk sergileme verileriyle calisiyor. Kendi canli PostgreSQL (pgvector) veritabaninizi baglamak icin Vercel Dashboard'da <code>PD_DATABASE_URL</code> ortam degiskenini tanimlayin.</span>
    </div>
    <a href="https://github.com/Scryne/PolitikDesk" target="_blank" rel="noopener noreferrer" class="subtle plain" style="font-size:var(--text-xs);font-weight:600">GitHub Deposu &rarr;</a>
  </div>
</div>
"""


def get_demo_feed() -> list[dict[str, Any]]:
    """Gündem ekranı için zengin, gerçekçi olay ve X taslak kartları."""
    return [
        {
            "id": 101,
            "title": "TÜİK Temmuz 2026 Tüketici Fiyat Endeksi (TÜFE) ve Yıllık Enflasyon Verisi",
            "status": "verified",
            "salience_score": 88,
            "global_salience": 88,
            "personal_salience": 4,
            "displayed_salience": 92,
            "salience_breakdown": {
                "components": {
                    "official_publisher": 30.0,
                    "independent_corroboration": 28.0,
                    "macro_economic_impact": 20.0,
                    "actor_prominence": 10.0,
                },
                "penalties": {},
            },
            "topic_tags": ["enflasyon", "tuik", "makro_ekonomi", "faiz"],
            "article_count": 8,
            "independent_count": 4,
            "has_primary_source": True,
            "review_flag": None,
            "vertical": "macro_economy",
            "first_reported_at": "2026-08-16T10:00:00+03:00",
            "last_update_at": "2026-08-16T14:30:00+03:00",
            "independence_groups": 3,
            "source_breakdown": {"official": 1, "independent": 4, "social": 3},
            "claim_count": 4,
            "weak_claim_count": 0,
            "contradicted_count": 0,
            "evidence_count": 4,
            "latest_draft": {
                "id": 201,
                "angle": "inform",
                "body": "TÜİK Temmuz 2026 TÜFE verilerini yayımladı: Aylık enflasyon %2,13, yıllık enflasyon %61,78 olarak gerçekleşti. Bağımsız araştırma grubu ENAG ise yıllık artışı %100,88 olarak hesapladı. TCMB yıl sonu ara tahmin bandı %38–%42 aralığında korunuyor.",
                "is_grounded": True,
                "user_action": None,
                "created_at": "2026-08-16T14:35:00+03:00",
            },
        },
        {
            "id": 102,
            "title": "TBMM Genel Kurulu: 28. Dönem Yeni Vergi ve Sermaye Piyasası Düzenlemeleri Kanun Teklifi Kabul Edildi",
            "status": "verified",
            "salience_score": 82,
            "global_salience": 82,
            "personal_salience": 3,
            "displayed_salience": 85,
            "salience_breakdown": {
                "components": {
                    "official_publisher": 30.0,
                    "independent_corroboration": 26.0,
                    "legislation_impact": 18.0,
                    "actor_prominence": 8.0,
                },
                "penalties": {},
            },
            "topic_tags": ["tbmm", "vergi", "meclis", "resmi_gazete"],
            "article_count": 6,
            "independent_count": 3,
            "has_primary_source": True,
            "review_flag": None,
            "vertical": "legislation",
            "first_reported_at": "2026-08-16T11:15:00+03:00",
            "last_update_at": "2026-08-16T13:45:00+03:00",
            "independence_groups": 3,
            "source_breakdown": {"official": 2, "independent": 3, "social": 1},
            "claim_count": 3,
            "weak_claim_count": 0,
            "contradicted_count": 0,
            "evidence_count": 3,
            "latest_draft": {
                "id": 202,
                "angle": "inform",
                "body": "TBMM Genel Kurulu'nda kabul edilen yeni vergi düzenlemesi paketiyle; asgari kurumlar vergisi oranı %15 olarak belirlendi ve kayıt dışılıkla mücadele cezaları artırıldı. Kanun Resmî Gazete'de yayımlanmak üzere Cumhurbaşkanlığı'na sevk edildi.",
                "is_grounded": True,
                "user_action": None,
                "created_at": "2026-08-16T13:50:00+03:00",
            },
        },
        {
            "id": 103,
            "title": "Sayıştay 2025 Yılı Karayolları Genel Müdürlüğü Kamu İhale ve Teminat Denetim Raporu",
            "status": "in_review",
            "salience_score": 75,
            "global_salience": 75,
            "personal_salience": 3,
            "displayed_salience": 78,
            "salience_breakdown": {
                "components": {
                    "official_publisher": 30.0,
                    "independent_corroboration": 22.0,
                    "audit_finding": 18.0,
                    "actor_prominence": 5.0,
                },
                "penalties": {},
            },
            "topic_tags": ["sayistay", "kamu_zarari", "ihale", "denetim"],
            "article_count": 5,
            "independent_count": 2,
            "has_primary_source": True,
            "review_flag": "needs_review",
            "vertical": "legislation",
            "first_reported_at": "2026-08-16T09:30:00+03:00",
            "last_update_at": "2026-08-16T12:00:00+03:00",
            "independence_groups": 2,
            "source_breakdown": {"official": 1, "independent": 2, "social": 2},
            "claim_count": 3,
            "weak_claim_count": 1,
            "contradicted_count": 1,
            "evidence_count": 2,
            "latest_draft": {
                "id": 203,
                "angle": "contradiction",
                "body": "Sayıştay Başkanlığı Karayolları Genel Müdürlüğü 2025 Denetim Raporu'nu açıkladı: Yap-İşlet-Devret projelerindeki kur farkı ödemeleri ve teminat mektubu eksikliklerine ilişkin 14 ayrı bulgu Meclis KİT Komisyonu gündemine taşındı.",
                "is_grounded": True,
                "user_action": None,
                "created_at": "2026-08-16T12:05:00+03:00",
            },
        },
        {
            "id": 104,
            "title": "Hazine ve Maliye Bakanlığı: 2026 Yılı 5 Yıllık Dolar Cinsi Eurobond Borçlanma İhracı Tamamlandı",
            "status": "verified",
            "salience_score": 68,
            "global_salience": 68,
            "personal_salience": 2,
            "displayed_salience": 70,
            "salience_breakdown": {
                "components": {
                    "official_publisher": 30.0,
                    "independent_corroboration": 20.0,
                    "macro_economic_impact": 14.0,
                    "actor_prominence": 4.0,
                },
                "penalties": {},
            },
            "topic_tags": ["hazine", "borclanma", "butce", "eurobond"],
            "article_count": 4,
            "independent_count": 2,
            "has_primary_source": True,
            "review_flag": None,
            "vertical": "macro_economy",
            "first_reported_at": "2026-08-16T08:00:00+03:00",
            "last_update_at": "2026-08-16T11:30:00+03:00",
            "independence_groups": 2,
            "source_breakdown": {"official": 1, "independent": 2, "social": 1},
            "claim_count": 2,
            "weak_claim_count": 0,
            "contradicted_count": 0,
            "evidence_count": 2,
            "latest_draft": {
                "id": 204,
                "angle": "inform",
                "body": "Hazine ve Maliye Bakanlığı uluslararası sermaye piyasalarında 2,5 milyar dolar tutarında 5 yıl vadeli tahvil ihracını tamamladı. İhraç kupon oranı %6,875 olarak gerçekleşirken, toplam talep ihraç tutarının 3 katına ulaştı.",
                "is_grounded": True,
                "user_action": None,
                "created_at": "2026-08-16T11:35:00+03:00",
            },
        },
    ]


def get_demo_accountability() -> list[dict[str, Any]]:
    """Hesap Sor ekranı için çapraz eşleşme ve tutarlılık vakaları."""
    return [
        {
            "id": 1,
            "speaker": "Mehmet Şimşek",
            "target_institution": "Hazine ve Maliye Bakanlığı",
            "promise_text": "2026 yılı sonu itibarıyla enflasyon kalıcı olarak tek haneli rakamlara inecek ve bütçe açığı %3 sınırına çekilecek.",
            "reported_date": "15 Ocak 2025",
            "event_title": "TÜİK Temmuz 2026 Enflasyon Gerçekleşmesi & Orta Vadeli Program Takibi",
            "relation": "fulfils",
            "status": "supported",
            "confidence": 0.86,
            "target_title": "TCMB Enflasyon Raporu & Hazine Bütçe Dengesi",
            "quote_raw": "Dezenflasyon süreci öngörülen takvim dahilinde ilerliyor.",
            "published_at": "16 Ağustos 2026",
            "sparkline": [75, 71, 68, 64, 61],
        },
        {
            "id": 2,
            "speaker": "TBMM İktidar Grubu",
            "target_institution": "TBMM Genel Kurulu",
            "promise_text": "Akaryakıt ve temel tüketim maddelerinde ek ÖTV artışı yapılmayacaktır.",
            "reported_date": "10 Mart 2025",
            "event_title": "28. Dönem Torba Kanun ile ÖTV Maktu Tutarlarının Güncellenmesi",
            "relation": "contradicts",
            "status": "verified",
            "confidence": 0.94,
            "target_title": "Resmî Gazete Sayı 32900 Kanun Metni",
            "quote_raw": "Otomatik maktu ÖTV artış mekanizması yürürlüğe girdi.",
            "published_at": "12 Temmuz 2026",
            "sparkline": [30, 45, 60, 85, 94],
        },
        {
            "id": 3,
            "speaker": "Ulaştırma ve Altyapı Bakanlığı",
            "target_institution": "Karayolları Genel Müdürlüğü",
            "promise_text": "Yap-İşlet-Devret otoyol ve köprü projelerinde Hazine garantileri bütçeye ilave yük getirmemektedir.",
            "reported_date": "22 Mayıs 2025",
            "event_title": "Sayıştay 2025 KGM Raporu: Garanti Fark Ödemeleri Bulgu İncelemesi",
            "relation": "fails",
            "status": "verified",
            "confidence": 0.91,
            "target_title": "Sayıştay 2025 Karayolları Denetim Raporu Madde 8",
            "quote_raw": "Geçiş garantisi farkı olarak 42 milyar TL Hazine ödemesi yapılmıştır.",
            "published_at": "16 Ağustos 2026",
            "sparkline": [40, 55, 70, 88, 91],
        },
        {
            "id": 4,
            "speaker": "Çalışma ve Sosyal Güvenlik Bakanlığı",
            "target_institution": "Sosyal Güvenlik Kurumu",
            "promise_text": "En düşük emekli maaşı kök maaş düzenlemesi Meclis tatile girmeden yasalaşacak.",
            "reported_date": "1 Temmuz 2026",
            "event_title": "Emekli Maaş Tabanını Belirleyen Kanun Teklifi TBMM Genel Kurulu'nda Kabul Edildi",
            "relation": "fulfils",
            "status": "verified",
            "confidence": 0.98,
            "target_title": "TBMM Oylama Tutanağı & 7524 Sayılı Kanun",
            "quote_raw": "Taban aylık 12.500 TL olarak Meclis'te kabul edildi.",
            "published_at": "25 Temmuz 2026",
            "sparkline": [80, 85, 90, 95, 98],
        },
    ]


def get_demo_memory_actors() -> list[dict[str, Any]]:
    """Siyasi Hafıza Masası için takip edilen kurum ve aktör profilleri."""
    return [
        {
            "id": 1,
            "name": "Hazine ve Maliye Bakanlığı",
            "entity_type": "institution",
            "is_key_entity": True,
            "claim_count": 42,
            "verified_count": 38,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
        {
            "id": 2,
            "name": "Türkiye İstatistik Kurumu (TÜİK)",
            "entity_type": "institution",
            "is_key_entity": True,
            "claim_count": 56,
            "verified_count": 52,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
        {
            "id": 3,
            "name": "Sayıştay Başkanlığı",
            "entity_type": "institution",
            "is_key_entity": True,
            "claim_count": 28,
            "verified_count": 28,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
        {
            "id": 4,
            "name": "TBMM Genel Kurulu",
            "entity_type": "institution",
            "is_key_entity": True,
            "claim_count": 64,
            "verified_count": 60,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
        {
            "id": 5,
            "name": "Mehmet Şimşek",
            "entity_type": "person",
            "is_key_entity": True,
            "claim_count": 35,
            "verified_count": 31,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
        {
            "id": 6,
            "name": "Cevdet Yılmaz",
            "entity_type": "person",
            "is_key_entity": True,
            "claim_count": 24,
            "verified_count": 22,
            "created_at": "2026-01-01T00:00:00+03:00",
        },
    ]


def get_demo_promises() -> list[dict[str, Any]]:
    """Vaat Takibi ekranı için taahhüt kütüğü."""
    return [
        {
            "id": 1,
            "speaker": "Hazine ve Maliye Bakanlığı",
            "promise_text": "Merkezi yönetim bütçe açığı GSYH'nin %3'ünün altına indirilecektir.",
            "stated_at": "2025-09-10",
            "expected_by": "2026-12-31",
            "outcome_relation": "pending",
            "outcome_label": "Takip Ediliyor",
            "evidence_count": 6,
            "confidence_score": 0.85,
            "target_title": "2026 Yılı Bütçe Gerçekleşme Raporları",
        },
        {
            "id": 2,
            "speaker": "TBMM İktidar Grubu",
            "promise_text": "Kayıt dışılıkla mücadele ve asgari kurumlar vergisi paketi yasalaşacak.",
            "stated_at": "2026-03-15",
            "expected_by": "2026-08-01",
            "outcome_relation": "fulfils",
            "outcome_label": "Gerçekleşti",
            "evidence_count": 4,
            "confidence_score": 0.98,
            "target_title": "7524 Sayılı Vergi Kanunları Değişikliği",
        },
        {
            "id": 3,
            "speaker": "Cumhurbaşkanlığı",
            "promise_text": "Kamuda tasarruf ve taşıt kısıtlaması genelgesi tüm kamu idarelerinde uygulanacak.",
            "stated_at": "2024-05-13",
            "expected_by": "2025-05-13",
            "outcome_relation": "fulfils",
            "outcome_label": "Gerçekleşti",
            "evidence_count": 5,
            "confidence_score": 0.95,
            "target_title": "2024/7 Sayılı Tasarruf Tedbirleri Genelgesi",
        },
        {
            "id": 4,
            "speaker": "Çalışma ve Sosyal Güvenlik Bakanlığı",
            "promise_text": "En düşük emekli maaşı kök maaş düzenlemesi Meclis tatile girmeden yasalaşacak.",
            "stated_at": "2026-07-01",
            "expected_by": "2026-07-31",
            "outcome_relation": "fulfils",
            "outcome_label": "Gerçekleşti",
            "evidence_count": 3,
            "confidence_score": 0.98,
            "target_title": "TBMM Genel Kurulu Kanun Oylaması",
        },
    ]


def get_demo_archive() -> list[dict[str, Any]]:
    """Yayın Arşivi ekranı için X paylaşımları kütüğü."""
    return [
        {
            "id": 1,
            "event_id": 101,
            "angle": "inform",
            "angle_label": "Doğrudan Bilgilendirme",
            "body": "TÜİK Temmuz 2026 TÜFE verilerini yayımladı: Aylık enflasyon %2,13, yıllık enflasyon %61,78 olarak gerçekleşti. Bağımsız araştırma grubu ENAG ise yıllık artışı %100,88 olarak hesapladı.",
            "is_grounded": True,
            "published_at": "2026-08-16T14:40:00+03:00",
            "event_title": "TÜİK Temmuz 2026 Tüketici Fiyat Endeksi (TÜFE)",
            "intent_url": "https://x.com/intent/tweet?text=T%C3%9C%C4%B0K%20Temmuz%202026",
        },
        {
            "id": 2,
            "event_id": 102,
            "angle": "inform",
            "angle_label": "Doğrudan Bilgilendirme",
            "body": "TBMM Genel Kurulu'nda kabul edilen yeni vergi düzenlemesi paketiyle; asgari kurumlar vergisi oranı %15 olarak belirlendi. Kanun Resmî Gazete yayımı için Cumhurbaşkanlığı'na sevk edildi.",
            "is_grounded": True,
            "published_at": "2026-08-16T14:00:00+03:00",
            "event_title": "TBMM 28. Dönem Vergi Kanunu Teklifi",
            "intent_url": "https://x.com/intent/tweet?text=TBMM%20Vergi",
        },
    ]


def get_demo_event_page(event_id: int) -> dict[str, Any]:
    """Demo olay detay sayfası verisi."""
    events = {e["id"]: e for e in get_demo_feed()}
    ev = events.get(event_id, get_demo_feed()[0])
    return {
        "event": ev,
        "articles": [
            {
                "id": 1,
                "title": ev["title"],
                "canonical_url": "https://www.tuik.gov.tr",
                "excerpt": "Temmuz 2026 dönemine ilişkin Tüketici Fiyat Endeksi haber bülteni yayımlandı.",
                "published_at": ev["first_reported_at"],
                "first_seen_at": ev["first_reported_at"],
                "near_duplicate_of_id": None,
                "cluster_score": 0.96,
                "source_name": "TÜİK",
                "source_slug": "tuik",
                "tier": "tier_1_official",
                "kind": "official",
                "independence_group": "tuik",
            }
        ],
        "claims": [
            {
                "id": 1,
                "claim_text": "TÜFE aylık bazda %2,13 artış göstermiştir.",
                "claim_type": "statistical",
                "evidence_status": "strongly_corroborated",
                "status_reason": "Resmî istatistik bülteni ve bağımsız kaynaklarca doğrulandı.",
                "normalized_value": "2.13",
                "computed_at": "2026-08-16T10:05:00+03:00",
                "evidence_count": 2,
            },
            {
                "id": 2,
                "claim_text": "TÜFE yıllık bazda %61,78 olarak gerçekleşmiştir.",
                "claim_type": "statistical",
                "evidence_status": "strongly_corroborated",
                "status_reason": "TÜİK veri tabanında eşleşti.",
                "normalized_value": "61.78",
                "computed_at": "2026-08-16T10:05:00+03:00",
                "evidence_count": 2,
            },
        ],
        "related": [],
        "upcoming": [],
        "entities": [
            {"entity_name": "TÜİK", "entity_type": "institution", "mention_count": 5},
            {"entity_name": "Mehmet Şimşek", "entity_type": "person", "mention_count": 3},
        ],
        "evidence_items": [
            {
                "id": 1,
                "claim_id": 1,
                "evidence_type": "official_data",
                "snippet": "TÜFE (2003=100) 2026 yılı Temmuz ayında bir önceki aya göre %2,13 arttı.",
                "source_name": "TÜİK",
                "published_at": "2026-08-16T10:00:00",
                "tier": "tier_1_official",
                "independence_group": "tuik",
            }
        ],
        "blindspot": None,
        "framing": {"official": 1, "independent": 2},
        "timeline": [],
        "open_feedback": [],
    }

