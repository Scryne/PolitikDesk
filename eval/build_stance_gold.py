"""Faz 6.2 — duruş sınıflandırma altın kümesini üretir.

**Etiketler model üretimi DEĞİLDİR.** Her öğede iddia ve kanıt metni
birlikte kurgulandı; ilişki tanım gereği bellidir. Bu, modelden etiket
almaktan daha güçlü bir yer tutucudur ama bir alan uzmanının incelemesi
yerine geçmez — `reviewer` alanı bunu açıkça söyler.

Kullanım:
    python -m eval.build_stance_gold
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter
from datetime import UTC, datetime

DATASET_VERSION = "stance.gold.v1"
OUT = pathlib.Path(__file__).resolve().parent / "golden_stance_v1.jsonl"

_ROWS: list[dict[str, str]] = []


def ek(kid: str, kategori: str, iddia: str, kanit: str, beklenen: str,
       gerekce: str, zorluk: str = "orta") -> None:
    _ROWS.append(
        {
            "id": kid,
            "dataset_version": DATASET_VERSION,
            "category": kategori,
            "claim_text": iddia,
            "evidence_text": kanit,
            "expected_label": beklenen,
            "rationale": gerekce,
            "difficulty": zorluk,
            "reviewer": "assistant-authored (iddia ve kanit birlikte kurgulandi)",
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
    )


def build() -> list[dict[str, str]]:
    _ROWS.clear()

    # ---------------------------------------------------------- açık destek
    ek("sup-01", "clear_support",
       "TCMB politika faizini yüzde 40'ta sabit bıraktı.",
       "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu, politika "
       "faizini yüzde 40 seviyesinde değiştirmeme kararı aldı.",
       "supports", "Aynı olgu, aynı sayı.", "kolay")
    ek("sup-02", "clear_support",
       "Hazine ağustos ayında 120 milyar lira iç borçlanma yaptı.",
       "Hazine ve Maliye Bakanlığı, ağustos ayı iç borçlanma tutarının 120 "
       "milyar lira olarak gerçekleştiğini duyurdu.",
       "supports", "Kurum, dönem ve tutar örtüşüyor.", "kolay")
    ek("sup-03", "turkish_abbrev",
       "TÜİK işsizlik oranını yüzde 8,4 olarak açıkladı.",
       "Türkiye İstatistik Kurumu verilerine göre işsizlik oranı yüzde 8,4 oldu.",
       "supports", "Kısaltma ile açık ad aynı kurum.", "orta")
    ek("sup-04", "reported_speech",
       "Bakan, bütçe açığının hedefin altında kaldığını söyledi.",
       "Bakan yaptığı açıklamada bütçe açığının yıl sonu hedefinin altında "
       "kaldığını belirtti.",
       "supports", "Aktarılan söz iddiayla birebir.", "orta")

    # --------------------------------------------------------- açık çelişki
    ek("con-01", "clear_contradiction",
       "TCMB politika faizini yüzde 40'ta sabit bıraktı.",
       "Merkez Bankası politika faizini 250 baz puan artırarak yüzde 42,5'e yükseltti.",
       "contradicts", "Sabit bırakma ile artırma aynı anda doğru olamaz.", "kolay")
    ek("con-02", "numeric_contradiction",
       "Yıllık enflasyon yüzde 38,1 olarak gerçekleşti.",
       "TÜİK verilerine göre yıllık tüketici enflasyonu yüzde 44,7 oldu.",
       "contradicts", "Aynı metrik, aynı dönem, farklı değer.", "kolay")
    ek("con-03", "negation",
       "Bakanlık, doğal gaz zammı yapılacağını açıkladı.",
       "Bakanlık, doğal gaz fiyatlarına zam yapılmayacağını duyurdu.",
       "contradicts", "Olumsuzluk eki iddiayı tersine çeviriyor.", "orta")
    ek("con-04", "negation",
       "Kurul, başvurunun kabul edildiğini bildirdi.",
       "Kurul başvuruyu reddetti; talep kabul edilmedi.",
       "contradicts", "Düz ret, çift olumsuzlama yok.", "orta")
    ek("con-05", "temporal_contradiction",
       "Toplantı 12 Eylül 2026'da yapılacak.",
       "Toplantının 3 Kasım 2026'ya ertelendiği açıklandı.",
       "contradicts", "Aynı olay, farklı tarih.", "orta")
    ek("con-06", "turkish_morphology",
       "Faiz artırılacak.",
       "Yetkililer faizin artırılmayacağını, mevcut seviyede kalacağını belirtti.",
       "contradicts", "-mayacağı olumsuz gelecek eki.", "zor")
    ek("con-07", "negation",
       "Rezervler arttı.",
       "Merkez Bankası rezervlerinde artış yok; seviye geçen ayla aynı kaldı.",
       "contradicts", "'yok' ile olumsuzlama.", "orta")

    # -------------------------------------------------------------- ilgisiz
    ek("unr-01", "unrelated",
       "TCMB politika faizini sabit bıraktı.",
       "Süper Lig'de haftanın maçında ev sahibi takım 2-1 kazandı.",
       "unrelated", "Ortak konu yok.", "kolay")
    ek("unr-02", "unrelated",
       "İşsizlik oranı yüzde 8,4 oldu.",
       "Meteoroloji, hafta sonu için sağanak yağış uyarısı yaptı.",
       "unrelated", "Farklı alan.", "kolay")
    ek("unr-03", "unrelated",
       "Hazine iç borçlanma ihalesi düzenledi.",
       "Kültür Bakanlığı, müze giriş ücretlerinde düzenlemeye gitti.",
       "unrelated", "Aynı hükümet ama farklı olgu.", "orta")

    # ------------------------------------ yetersiz kanıt / halüsinasyon yemi
    ek("ins-01", "insufficient",
       "TCMB eylül 2026 toplantısında faizi indirdi.",
       "Merkez Bankası para politikası duyuruları resmî internet sitesinde "
       "yayımlanmaktadır.",
       "insufficient_evidence", "Kanıt metninde karar bilgisi yok.", "orta")
    ek("ins-02", "missing_context",
       "Enflasyon yüzde 44,7 oldu.",
       "Veriler bugün açıklandı.",
       "insufficient_evidence", "Hangi veri, hangi değer belirtilmemiş.", "orta")
    ek("ins-03", "hallucination_bait",
       "Türkiye 2026'da IMF ile stand-by anlaşması imzaladı.",
       "IMF, üye ülkelerle düzenli olarak Madde IV istişarelerini sürdürmektedir.",
       "insufficient_evidence", "Model dünya bilgisinden çıkarım yapmamalı.", "zor")
    ek("ins-04", "hallucination_bait",
       "Asgari ücrete yüzde 30 zam yapıldı.",
       "Asgari Ücret Tespit Komisyonu her yıl aralık ayında toplanır.",
       "insufficient_evidence", "Genel bilgi; ne destekler ne çürütür.", "zor")
    ek("ins-05", "misleading_headline",
       "Merkez Bankası faizi indirdi.",
       "BAŞLIK: Faizde sürpriz karar! Metin: Kurul toplantısı bugün saat "
       "14:00'te başladı.",
       "insufficient_evidence", "Başlık ima ediyor, gövdede karar yok.", "zor")
    ek("ins-06", "outdated",
       "2026 yılı büyümesi yüzde 3,2 oldu.",
       "2019 yılında Türkiye ekonomisi yüzde 0,9 büyüdü.",
       "insufficient_evidence", "Farklı dönem — çelişki değil.", "zor")

    # -------------------------------------------------------- kısmi destek
    ek("par-01", "partial",
       "Hazine ağustosta 120 milyar lira borçlandı ve faiz yüzde 41 oldu.",
       "Hazine ağustos ayı iç borçlanmasının 120 milyar lira olduğunu açıkladı.",
       "partial", "İlk kısım destekleniyor, faiz bilgisi yok.", "zor")
    ek("par-02", "partial",
       "TÜİK hem işsizliği hem enflasyonu açıkladı; işsizlik yüzde 8,4.",
       "TÜİK işsizlik oranını yüzde 8,4 olarak duyurdu.",
       "partial", "İşsizlik doğrulanıyor, enflasyon kısmı yok.", "zor")

    # ------------------------------------------- koşullu ve dolaylı anlatım
    ek("cnd-01", "conditional",
       "Faiz indirimi yapılacak.",
       "Yetkili, enflasyon hedefe yaklaşırsa faiz indiriminin gündeme "
       "gelebileceğini söyledi.",
       "insufficient_evidence", "Koşullu ifade kesin eylem bildirmez.", "zor")
    ek("cnd-02", "conditional",
       "Zam oranı yüzde 25 olacak.",
       "Komisyon üyesi, zam oranının yüzde 25 civarında olabileceğini ifade etti.",
       "insufficient_evidence", "'olabileceğini' — olasılık, gerçekleşme değil.", "zor")
    ek("quo-01", "quotation",
       "Muhalefet lideri hükümeti eleştirdi.",
       "Gazeteci köşesinde muhalefet liderinin hükümeti eleştirdiğini yazdı.",
       "supports", "Aktarım da olsa olgu bildiriliyor.", "orta")
    ek("quo-02", "quotation_boundary",
       "Bakan istifa etti.",
       "Muhabir bakanın istifa edip etmediğini sordu; bakanlık kaynakları "
       "soruyu yanıtlamadı.",
       "insufficient_evidence", "Soru cümlesi iddia değildir.", "zor")
    ek("rep-01", "reported_speech",
       "Kurum enflasyonun düşeceğini öngörüyor.",
       "Kurum başkanı, önümüzdeki dönemde enflasyonun kademeli düşeceğini "
       "öngördüklerini söyledi.",
       "supports", "Doğrudan aktarım, iddiayla örtüşüyor.", "orta")
    ek("rep-02", "reported_speech",
       "Şirket iflas başvurusu yaptı.",
       "Bir sosyal medya kullanıcısı şirketin iflas başvurusu yaptığını iddia "
       "etti; şirketten açıklama gelmedi.",
       "insufficient_evidence", "İddia edildi, gerçekleşti demek değil.", "zor")

    # ------------------------------------------- Türkçe morfoloji / kısaltma
    ek("mor-01", "turkish_morphology",
       "Vergi oranı düşürüldü.",
       "Vergi oranında herhangi bir düşüş yapılmadı, oran korundu.",
       "contradicts", "-madı olumsuz geçmiş.", "orta")
    ek("mor-02", "turkish_morphology",
       "İhracat arttı.",
       "İhracattaki artış sürüyor; rakam geçen yılın üzerinde.",
       "supports", "Farklı ek, aynı olgu.", "orta")
    ek("abr-01", "turkish_abbrev",
       "SPK yeni tebliğ yayımladı.",
       "Sermaye Piyasası Kurulu, konuya ilişkin yeni tebliği Resmî Gazete'de "
       "yayımladı.",
       "supports", "SPK = Sermaye Piyasası Kurulu.", "orta")
    ek("abr-02", "turkish_abbrev",
       "BDDK bankalara sınırlama getirdi.",
       "Bankacılık Düzenleme ve Denetleme Kurumu, kredi kullanımına yeni "
       "sınırlama getirdi.",
       "supports", "BDDK açılımı.", "orta")
    ek("abr-03", "turkish_abbrev",
       "MGK toplandı.",
       "Millî Güvenlik Kurulu bugün Cumhurbaşkanlığında toplandı.",
       "supports", "MGK açılımı.", "kolay")

    # ------------------------------------------------------ belirsiz / mecaz
    ek("amb-01", "ambiguous",
       "Ekonomide toparlanma başladı.",
       "Sanayi üretimi son iki ayda sınırlı artış gösterdi.",
       "partial", "Kısmi gösterge; iddiayı tam kurmuyor.", "zor")
    ek("fig-01", "figurative",
       "Piyasalar çöktü.",
       "Borsa endeksi günü yüzde 0,3 düşüşle tamamladı.",
       "contradicts", "'Çöküş' ile %0,3 düşüş bağdaşmıyor.", "zor")

    return list(_ROWS)


def main() -> int:
    rows = build()
    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"altin kume: {len(rows)} oge -> {OUT}")
    print("etiket   :", dict(Counter(r["expected_label"] for r in rows)))
    print("kategori :", len({r['category'] for r in rows}), "farkli")
    print("zorluk   :", dict(Counter(r["difficulty"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
