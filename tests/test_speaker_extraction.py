"""Konuşan atfı testleri (ADR-010 §6).

⛔ KESİNLİK ÖNCELİKLİ, KAPSAM DEĞİL.

Yanlış bir konuşan atfı, konuşan atfı olmamasından çok daha pahalıdır:
birincisi gerçek bir kişiye söylemediği bir sözü yükler. Bu testlerin
çoğu, çıkarıcının **ne zaman susması gerektiğini** sabitler.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from politikdesk.nlp import speaker as sp
from politikdesk.nlp.speaker import extract_speaker


# ═══════════════════════════ tanınan biçimler
@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        (
            "Bakan Mehmet Şimşek, vergi uyumunu artırmayı amaçladıklarını söyledi.",
            "Bakan Mehmet Şimşek",
        ),
        ("Özgür Özel, kurultayın yapılacağını belirtti.", "Özgür Özel"),
        ("Tuncer Bakırhan, 'Bu ucuzluktur' dedi.", "Tuncer Bakırhan"),
        ("TÜİK, işsizlik oranını %7,6 olarak açıkladı.", "TÜİK"),
        ("Numan Kurtulmuş stated that the word will be about brotherhood.", "Numan Kurtulmuş"),
        ("Erdoğan said he will be a candidate.", "Erdoğan"),
        ("Sinan Burhan: 'KURULTAY GELECEĞİ BELİRLEYECEK'.", "Sinan Burhan"),
    ],
)
def test_recognised_forms(metin: str, beklenen: str) -> None:
    assert extract_speaker(metin) == beklenen


def test_turkish_dotted_capitals_are_matched() -> None:
    """`İ` ve `Ş` ASCII `[A-Z]` içinde YOKTUR.

    Atlanırsa "İmamoğlu" ve "Şimşek" hiç eşleşmez — Türkçe bir üründe
    en sık yapılan hata.
    """
    assert extract_speaker("İmamoğlu, iddiaları reddettiğini söyledi.") == "İmamoğlu"
    assert extract_speaker("Şimşek, enflasyonun düşeceğini belirtti.") == "Şimşek"


# ═══════════════════════════ susması gereken durumlar
def test_no_speaker_returns_none_not_a_guess() -> None:
    """`None` dürüst bir cevaptır: 'bu cümlede kesin kalıp yok'."""
    assert extract_speaker("Kabul edilmeyince, parti değiştirecek haberleri sızdırılıyor.") is None


def test_empty_input_is_safe() -> None:
    for bos in ("", "   ", "\n"):
        assert extract_speaker(bos) is None


def test_action_verbs_do_not_establish_authorship() -> None:
    """ "Gitti"/"yaptı" bir beyan sahipliği kurmaz; yalnızca aktarma fiilleri kurar."""
    assert extract_speaker("Ahmet Yılmaz, Ankara'ya gitti.") is None


def test_conjunction_is_not_a_name() -> None:
    """ "Ancak Bakan, ... dedi" cümlesinde konuşan "Ancak" olmamalı."""
    assert extract_speaker("Ancak bakan, konuyu değerlendireceğini söyledi.") is None


def test_headline_prefix_is_not_a_speaker() -> None:
    """ "Cumhurbaşkanlığı Açıklaması:" bir ad değil, başlık önekidir."""
    assert extract_speaker("Cumhurbaşkanlığı Açıklaması: Erzurum Kongresi") is None


def test_generic_role_words_are_rejected() -> None:
    """ADR-010'da "Adayı" aktör alanına sızmıştı."""
    assert extract_speaker("Adayı, kararını açıkladı.") is None


def test_overlong_phrase_is_not_a_name() -> None:
    uzun = "Bir İki Üç Dört Beş Altı Yedi, konuyu değerlendirdiğini söyledi."
    assert extract_speaker(uzun) is None


# ═══════════════════════════ yayın organı ≠ konuşan
def test_known_publication_is_not_a_speaker() -> None:
    """Bir yayın organı haberi AKTARIR, beyanın sahibi değildir.

    "Halk TV: İBB davasında ikinci celse başlıyor" cümlesinde Halk TV
    konuşan değil, aktaran taraftır.
    """
    metin = "Halk TV: İBB davasında ikinci celse başlıyor"
    assert extract_speaker(metin) == "Halk TV"
    assert extract_speaker(metin, known_publications=frozenset({"Halk TV"})) is None


def test_resmi_gazete_is_never_a_speaker() -> None:
    """⛔ ADR-010'un doğrudan bulgusu: "Resmî Gazete"ye üç U dönüşü atfedilmişti.

    Bu, çağıranın yayın listesi vermesine bağlı bırakılmayacak kadar
    belirgin bir hata; modülün kendi kara listesinde.
    """
    assert extract_speaker("Resmî Gazete: Yeni yönetmelik yayımlandı") is None


def test_publication_matching_is_turkish_case_insensitive() -> None:
    metin = "İhlas Haber: Açıklama yapıldı"
    assert extract_speaker(metin, known_publications=frozenset({"İHLAS HABER"})) is None


def test_person_speaker_survives_publication_filter() -> None:
    """Bir bakanın X hesabı kaynak olsa da bakan meşru bir konuşandır."""
    assert (
        extract_speaker(
            "Özgür Özel, kurultayın yapılacağını söyledi.",
            known_publications=frozenset({"Halk TV", "Sözcü"}),
        )
        == "Özgür Özel"
    )


# ═══════════════════════════ mimari kısıtlar
def test_module_does_not_use_an_llm() -> None:
    """Konuşanın kim olduğuna yapay zekâ karar veremez — tespit deterministik."""
    agac = ast.parse(inspect.getsource(sp))
    for n in ast.walk(agac):
        adlar: list[str] = []
        if isinstance(n, ast.Import):
            adlar = [x.name for x in n.names]
        elif isinstance(n, ast.ImportFrom):
            adlar = [n.module or ""]
        assert not any(a.startswith("politikdesk.llm") for a in adlar), (
            "speaker.py LLM import ediyor"
        )


def test_module_does_not_touch_the_database() -> None:
    """Saf ve test edilebilir kalmalı; yayın listesini çağıran verir."""
    kaynak = inspect.getsource(sp)
    assert "connection" not in kaynak
    assert "SELECT" not in kaynak


def test_pipeline_persists_speaker_outside_status_reason() -> None:
    """⛔ `status_reason` kanıt motorunun malı ve her puanlamada eziliyor.

    Konuşan oraya konsaydı ilk `score_evidence` koşumunda sessizce
    silinirdi.
    """
    from politikdesk.nlp import claims_pipeline

    kaynak = inspect.getsource(claims_pipeline)
    assert "extract_speaker" in kaynak
    assert "speaker" in kaynak
    # Konuşan JSONB'ye gömülmemeli.
    assert '"speaker"' not in kaynak


def test_memory_distinguishes_strong_from_weak_attribution() -> None:
    """⛔ "Beyanı ona ait" ile "aynı olayda adı geçiyor" aynı şey değil.

    ADR-010 §1'deki yanlış isnadın kaynağı bu ayrımın olmamasıydı.
    """
    from politikdesk.political_memory.service import MemoryEntry

    alanlar = set(MemoryEntry.__dataclass_fields__)
    assert "speaker" in alanlar
    assert "attribution_strength" in alanlar
    assert MemoryEntry.__dataclass_fields__["attribution_strength"].default == "weak", (
        "Varsayilan 'strong' olsaydi, atfi bilinmeyen kayitlar sağlam sayilirdi."
    )


def test_memory_query_orders_speaker_matches_first_with_nulls_last() -> None:
    """⛔ Postgres'te `DESC` sıralamada NULL'lar BAŞA gelir.

    `NULLS LAST` olmadan, konuşanı hiç olmayan kayıtlar en öne geçiyor
    ve `LIMIT 100` aktörün kendi sözlerini listeden atıyordu — düzeltme
    tam tersine çalışıyordu. Ölçüldü: Özgür Özel 44 sağlam kayıt yerine
    0 gösteriyordu.
    """
    from politikdesk.political_memory import service

    kaynak = inspect.getsource(service.get_actor_memory)
    assert "c.speaker ILIKE" in kaynak
    assert "NULLS LAST" in kaynak


def test_migration_documents_why_not_status_reason() -> None:
    import pathlib

    yol = pathlib.Path(sp.__file__).resolve().parents[2] / "migrations" / "0020_claim_speaker.sql"
    sql = yol.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS speaker" in sql
    assert "status_reason" in sql


# ═══════════════════════════ ad varyantı normalizasyonu
def test_titles_are_stripped() -> None:
    from politikdesk.nlp.speaker import strip_title

    assert strip_title("Cumhurbaşkanı Recep Tayyip Erdoğan") == "Recep Tayyip Erdoğan"
    assert strip_title("TBMM Başkanı Numan Kurtulmuş") == "Numan Kurtulmuş"
    assert strip_title("Bakan Mehmet Şimşek") == "Mehmet Şimşek"
    assert strip_title("Gazeteci Fatih Altaylı") == "Fatih Altaylı"


def test_stripping_never_empties_the_name() -> None:
    """Adın tamamı unvandan ibaretse ad korunur, boş dize dönmez."""
    from politikdesk.nlp.speaker import strip_title

    assert strip_title("Bakan") == "Bakan"


def test_unambiguous_surname_resolves_to_full_name() -> None:
    from politikdesk.nlp.speaker import canonicalize_speaker

    tam = frozenset({"Mehmet Şimşek", "Numan Kurtulmuş"})
    assert canonicalize_speaker("Şimşek", tam) == "Mehmet Şimşek"
    assert canonicalize_speaker("Bakan Şimşek", tam) == "Mehmet Şimşek"


def test_ambiguous_surname_is_left_alone() -> None:
    """⛔ EN ÖNEMLİ TEST.

    Külliyatta "Recep Tayyip Erdoğan" ile birlikte **"Emine Erdoğan"** ve
    **"Fatoş Erdoğan"** da var. Yalın soyadı en sık geçen tam ada
    yapıştırmak üç farklı kişiyi tek kişi yapardı — ADR-010'da kapatılan
    yanlış isnadın aynısı, yeni bir yerden. Belirsizliği korumak, yanlış
    çözmekten iyidir.
    """
    from politikdesk.nlp.speaker import canonicalize_speaker

    tam = frozenset({"Recep Tayyip Erdoğan", "Emine Erdoğan", "Fatoş Erdoğan"})
    assert canonicalize_speaker("Erdoğan", tam) == "Erdoğan"
    assert canonicalize_speaker("Cumhurbaşkanı Erdoğan", tam) == "Erdoğan"
    # Tam adlar hiçbir koşulda birbirine karışmaz.
    assert canonicalize_speaker("Emine Erdoğan", tam) == "Emine Erdoğan"


def test_full_names_pass_through_unchanged() -> None:
    from politikdesk.nlp.speaker import canonicalize_speaker

    assert canonicalize_speaker("Özgür Özel", frozenset()) == "Özgür Özel"
