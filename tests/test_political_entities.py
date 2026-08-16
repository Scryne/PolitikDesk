"""Siyaset dikey varlık çıkarımı ve aktör kataloğu testleri (Spec v3.5 §5)."""

from __future__ import annotations

from politikdesk.nlp.entities import (
    INSTITUTIONS,
    POLITICAL_ACTORS,
    extract,
    extract_institutions,
    extract_political_actors,
)


def test_political_actors_catalog_size() -> None:
    """Aktör ve kurum kataloğu zengin olmalı."""
    assert len(POLITICAL_ACTORS) >= 40
    assert len(INSTITUTIONS) >= 40


def test_political_leaders_alias_resolution() -> None:
    """Lider alias'ları kanonik isimlere çözülmeli."""
    text1 = "Erdoğan ve Özgür Özel Meclis açılışında bir araya geldi"
    extracted = extract(text1)
    names = {e.canonical_name for e in extracted}
    assert "Recep Tayyip Erdoğan" in names
    assert "Özgür Özel" in names

    text2 = "Bahçeli grup toplantısında önemli açıklamalarda bulundu"
    extracted2 = extract(text2)
    assert any(e.canonical_name == "Devlet Bahçeli" for e in extracted2)

    text3 = "İmamoğlu ve Mansur Yavaş yerel yönetimler zirvesine katıldı"
    extracted3 = extract(text3)
    names3 = {e.canonical_name for e in extracted3}
    assert "Ekrem İmamoğlu" in names3
    assert "Mansur Yavaş" in names3


def test_cabinet_ministers_extraction() -> None:
    """Kabine üyeleri hem unvanla hem isimle doğru çıkarılmalı."""
    text = "Dışişleri Bakanı Hakan Fidan ve İçişleri Bakanı Ali Yerlikaya ortak basın toplantısı düzenledi"
    extracted = extract(text)
    names = {e.canonical_name for e in extracted}
    assert "Hakan Fidan" in names
    assert "Ali Yerlikaya" in names


def test_high_judiciary_and_parliamentary_entities() -> None:
    """Yüksek yargı ve TBMM ihtisas komisyonları doğru tanınmalı."""
    text = "Anayasa Mahkemesi ve Yüksek Seçim Kurulu kararları TBMM Plan ve Bütçe Komisyonu gündemine geldi"
    extracted = extract(text)
    names = {e.canonical_name for e in extracted}
    assert "Anayasa Mahkemesi" in names
    assert "Yüksek Seçim Kurulu" in names
    assert "TBMM Plan ve Bütçe Komisyonu" in names


def test_political_parties_extraction() -> None:
    """Siyasi partiler ve kısaltmaları tanınmalı."""
    text = "AK Parti, CHP, MHP ve DEM Parti temsilcileri TBMM'de toplandı"
    extracted = extract(text)
    names = {e.canonical_name for e in extracted}
    assert "Adalet ve Kalkınma Partisi" in names
    assert "Cumhuriyet Halk Partisi" in names
    assert "Milliyetçi Hareket Partisi" in names
    assert "Halkların Eşitlik ve Demokrasi Partisi" in names


def test_political_key_entities_marking() -> None:
    """Kilit siyasi varlıklar is_key_entity olarak işaretlenmeli."""
    text = "TBMM Başkanı Numan Kurtulmuş ve Ekrem İmamoğlu açıklama yaptı"
    extracted = extract(text)
    key_names = {e.canonical_name for e in extracted if e.is_key_entity}
    assert "Türkiye Büyük Millet Meclisi" in key_names or "Ekrem İmamoğlu" in key_names


def test_case_insensitivity_and_diacritics() -> None:
    """Büyük/küçük harf ve Türkçe diyakritik çözümleme sağlam olmalı."""
    res1 = extract_political_actors("erdogan ve ozgur ozel gorustu")
    names1 = {e.canonical_name for e in res1}
    assert "Recep Tayyip Erdoğan" in names1
    assert "Özgür Özel" in names1

    res2 = extract_institutions("aym ve ysk kararlari")
    names2 = {e.canonical_name for e in res2}
    assert "Anayasa Mahkemesi" in names2
    assert "Yüksek Seçim Kurulu" in names2


def test_actor_freshness_validator() -> None:
    """Aktör tazelik doğrulayıcı betiği başarıyla çalışmalı."""
    from scripts.validate_actor_freshness import validate_freshness

    exit_code = validate_freshness(max_age_days=90, strict=True)
    assert exit_code == 0
