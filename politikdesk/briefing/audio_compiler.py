"""Editoryal Sesli Brifing ve Podcast Metin Derleyicisi (Faz 5 / B-29 / Audio Briefing).

Sabah ve akşam brifinglerini, metin-konuşma (TTS) ve podcast yayınına uygun,
fonetik olarak genişletilmiş, akıcı ve yapılandırılmış bir seslendirme metnine çevirir.

⛔ MİMARİ KURAL: Deterministiktir; LLM çağırmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from politikdesk.briefing.generator import BriefingContent

# --------------------------------------------------------------------------
# 1. Fonetik Kısaltma Genişletme Sözlüğü (TTS için Doğal Okunuş)
# --------------------------------------------------------------------------
PHONETIC_EXPANSIONS: Final[dict[str, str]] = {
    r"\bTCMB\b": "Türkiye Cumhuriyet Merkez Bankası",
    r"\bTÜFE\b": "Tüketici Fiyat Endeksi",
    r"\bÜFE\b": "Üretici Fiyat Endeksi",
    r"\bPPK\b": "Para Politikası Kurulu",
    r"\bTBMM\b": "Türkiye Büyük Millet Meclisi",
    r"\bTÜİK\b": "Türkiye İstatistik Kurumu",
    r"\bBDDK\b": "Bankacılık Düzenleme ve Denetleme Kurumu",
    r"\bSPK\b": "Sermaye Piyasası Kurulu",
    r"\bSBB\b": "Strateji ve Bütçe Başkanlığı",
    r"\bKAP\b": "Kamuyu Aydınlatma Platformu",
    r"\bFED\b": "Amerikan Merkez Bankası",
    r"\bECB\b": "Avrupa Merkez Bankası",
    r"\bBOE\b": "İngiltere Merkez Bankası",
    r"\bGSYH\b": "Gayrisafi Yurt İçi Hasıla",
    r"\bCDS\b": "Kredi Risk Primi",
    r"\bPMI\b": "Satın Alma Yöneticileri Endeksi",
    r"\bÖTV\b": "Özel Tüketim Vergisi",
    r"\bKDV\b": "Katma Değer Vergisi",
    r"\bBM\b": "Birleşmiş Milletler",
    r"\bNATO\b": "Kuzey Atlantik Antlaşması Örgütü",
    r"\bAB\b": "Avrupa Birliği",
    r"\bBIST\b": "Borsa İstanbul",
}


def expand_phonetic_acronyms(text: str) -> str:
    """Metindeki finansal ve kurumsal kısaltmaları seslendirmeye uygun genişletir."""
    if not text:
        return ""
    result = text
    for pattern, replacement in PHONETIC_EXPANSIONS.items():
        result = re.sub(pattern, replacement, result)
    return result


@dataclass(frozen=True)
class AudioSection:
    """Sesli bültenin bir bölümü."""

    section_type: str  # "intro", "headline", "story", "indicator", "outro"
    title: str
    narration: str
    estimated_seconds: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_type": self.section_type,
            "title": self.title,
            "narration": self.narration,
            "estimated_seconds": self.estimated_seconds,
        }


@dataclass(frozen=True)
class AudioScript:
    """Tam sesli bülten çıktısı."""

    briefing_date: date
    slot: str
    title: str
    full_narration: str
    total_estimated_seconds: int
    sections: tuple[AudioSection, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "briefing_date": self.briefing_date.isoformat(),
            "slot": self.slot,
            "title": self.title,
            "full_narration": self.full_narration,
            "total_estimated_seconds": self.total_estimated_seconds,
            "sections": [s.as_dict() for s in self.sections],
        }


def _estimate_reading_seconds(text: str, words_per_minute: int = 140) -> int:
    """Türkçe seslendirme için kelime sayısına dayalı süre tahmini."""
    words = len(text.split())
    return max(3, int(words / (words_per_minute / 60)))


def compile_audio_script(content: BriefingContent) -> AudioScript:
    """Deterministik BriefingContent nesnesini seslendirme ve podcast metnine derler."""
    sections: list[AudioSection] = []

    slot_label = "Sabah" if content.slot == "morning" else "Akşam"
    day_str = content.briefing_date.strftime("%d %B %Y")

    # 1. Giriş / İntro
    intro_text = (
        f"Merhaba. PolitikDesk {slot_label} İstihbarat Bülteni'ne hoş geldiniz. "
        f"Bugün {day_str}. Son 12 saatte bağımsız ve resmî kaynaklardan derlenen "
        f"öne çıkan gelişmeleri ve kanıt durumlarını aktarıyoruz."
    )
    sections.append(
        AudioSection(
            section_type="intro",
            title="Giriş ve Selamlama",
            narration=intro_text,
            estimated_seconds=_estimate_reading_seconds(intro_text),
        )
    )

    # 2. Ana Olaylar (Top Stories)
    for idx, ev in enumerate(content.events[:5], start=1):
        clean_title = expand_phonetic_acronyms(ev.title)
        claim_part = ""
        if ev.top_claim:
            clean_claim = expand_phonetic_acronyms(ev.top_claim)
            status_desc = "güçlü kanıtlarla teyit edildi" if ev.top_claim_status == "strongly_corroborated" else "kaynaklarca aktarılıyor"
            claim_part = f" Bu konuda öne çıkan iddia: {clean_claim}. Bu bilgi {status_desc}."

        diversity_part = f" Gelişme {ev.independence_groups} bağımsız yayın grubu tarafından izleniyor."
        story_text = f"{idx}. başlığımız: {clean_title}.{claim_part}{diversity_part}"

        sections.append(
            AudioSection(
                section_type="story",
                title=f"Haber {idx}: {ev.title[:50]}",
                narration=story_text,
                estimated_seconds=_estimate_reading_seconds(story_text),
            )
        )

    # 3. Beklenen Gelişmeler & Takvim (Upcoming Schedule)
    if content.upcoming:
        sch_items = []
        for s in content.upcoming[:3]:
            title_exp = expand_phonetic_acronyms(s.get("title", ""))
            source_exp = expand_phonetic_acronyms(s.get("source_name", ""))
            sch_items.append(f"{source_exp} tarafından açıklanacak {title_exp}")
        schedule_text = "Günün beklenen resmî takvim gelişmeleri: " + "; ".join(sch_items) + "."
        sections.append(
            AudioSection(
                section_type="indicator",
                title="Gündem Takvimi ve Göstergeler",
                narration=schedule_text,
                estimated_seconds=_estimate_reading_seconds(schedule_text),
            )
        )

    # 4. Doğrulanmamış İddialar Uyarısı (Eğer varsa)
    if content.unverified:
        unv_count = len(content.unverified)
        unv_text = (
            f"Dikkat çeken bir not: Sosyal medyada ve kimi yayınlarda dolaşan {unv_count} iddia, "
            f"henüz birinci el kurumsal veya resmî belgelerle teyit edilmemiştir. "
            f"PolitikDesk doğrulama motoru bu iddiaları doğrulanmamış statüsünde takip etmektedir."
        )
        sections.append(
            AudioSection(
                section_type="story",
                title="Teyitsiz İddialar Uyarısı",
                narration=unv_text,
                estimated_seconds=_estimate_reading_seconds(unv_text),
            )
        )

    # 5. Kapanış / Outro
    outro_text = (
        f"PolitikDesk {slot_label} Bülteni'ni dinlediniz. Tüm olayların ayrıntılarına, "
        f"çapraz teyit kaynaklarına ve editoryal analizlere politikdesk çalışma masanızdan ulaşabilirsiniz. "
        f"İyi çalışmalar dileriz."
    )
    sections.append(
        AudioSection(
            section_type="outro",
            title="Kapanış İmzası",
            narration=outro_text,
            estimated_seconds=_estimate_reading_seconds(outro_text),
        )
    )

    full_narration = "\n\n".join(f"[{s.title.upper()}]\n{s.narration}" for s in sections)
    total_seconds = sum(s.estimated_seconds for s in sections)

    return AudioScript(
        briefing_date=content.briefing_date,
        slot=content.slot,
        title=f"PolitikDesk {slot_label} Sesli Brifingi ({day_str})",
        full_narration=full_narration,
        total_estimated_seconds=total_seconds,
        sections=tuple(sections),
    )
