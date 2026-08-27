"""Faz 1 — NLP testleri (F1-13…F1-16)."""

from __future__ import annotations

import math

import pytest

from politikdesk.config import Settings
from politikdesk.nlp.embedder import (
    EMBEDDING_DIM,
    HashingEmbedder,
    build_backend,
    embedding_text,
    to_pgvector,
)
from politikdesk.nlp.entities import (
    INSTITUTIONS,
    KEY_ENTITIES,
    EntityIndex,
    entity_set,
    extract,
    extract_institutions,
    extract_people,
    has_common_key_entity,
    jaccard,
)


# ---------------------------------------------------------------- F1-13
def test_hashing_embedder_produces_schema_dimension() -> None:
    vectors = HashingEmbedder().embed(["enflasyon verisi acikllandi"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM


def test_embedder_is_deterministic() -> None:
    embedder = HashingEmbedder()
    a = embedder.embed(["TCMB faiz karari"])[0]
    b = embedder.embed(["TCMB faiz karari"])[0]
    assert a == b


def test_embedding_vectors_are_l2_normalized() -> None:
    vector = HashingEmbedder().embed(["enflasyon faiz butce"])[0]
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, abs_tol=1e-6)


def test_empty_text_yields_zero_vector_without_error() -> None:
    vector = HashingEmbedder().embed([""])[0]
    assert len(vector) == EMBEDDING_DIM
    assert all(v == 0.0 for v in vector)


def test_default_backend_is_marked_not_production_ready() -> None:
    """D16 verilmeden üretim embedder'ı seçilmiş sayılmamalı."""
    backend = build_backend(Settings(embedding_provider=""))
    assert backend.name == "hashing"
    assert backend.is_production_ready is False


def test_unknown_provider_raises_at_settings_layer() -> None:
    """İlk savunma hattı: ayar nesnesi kurulurken (uygulama açılışında)."""
    with pytest.raises(ValueError, match="Bilinmeyen embedding"):
        Settings(embedding_provider="sihirli", embedding_model="x")


def test_unknown_provider_raises_at_backend_layer() -> None:
    """İkinci savunma hattı: `Settings` atlanıp elle nesne kurulsa bile.

    `build_backend` doğrudan çağrılabildiği için kendi kontrolünü korur;
    ayar doğrulamasına güvenip bu dalı silmek sessiz `KeyError` üretirdi.
    """
    settings = Settings(embedding_provider="local", embedding_model="x")
    object.__setattr__(settings, "embedding_provider", "sihirli")
    with pytest.raises(ValueError, match="Bilinmeyen embedding"):
        build_backend(settings)


def test_provider_without_model_raises() -> None:
    with pytest.raises(ValueError, match="PD_EMBEDDING_MODEL"):
        build_backend(Settings(embedding_provider="voyage", embedding_model=""))


def test_embedding_text_matches_benchmark_format() -> None:
    """eval/pairs_tr.jsonl ile aynı biçim olmalı (eval/README.md)."""
    assert embedding_text("Baslik", "Ozet metni") == "Baslik Ozet metni"
    assert embedding_text("Baslik", None) == "Baslik"


def test_pgvector_literal_format() -> None:
    assert to_pgvector([0.5, -0.25]) == "[0.500000,-0.250000]"


# ---------------------------------------------------------------- F1-15
def test_extracts_core_institutions() -> None:
    """DoD: TCMB, TÜİK, Hazine doğru çıkarılıyor."""
    text = "TCMB ve TÜİK verileri Hazine tarafından değerlendirildi"
    names = {e.canonical_name for e in extract_institutions(text)}
    assert "Türkiye Cumhuriyet Merkez Bankası" in names
    assert "Türkiye İstatistik Kurumu" in names
    assert "Hazine ve Maliye Bakanlığı" in names


def test_institution_extraction_is_case_insensitive() -> None:
    assert extract_institutions("tcmb açıklama yaptı")
    assert extract_institutions("TCMB açıklama yaptı")


def test_extracts_minister_names() -> None:
    """DoD: bakan isimleri doğru çıkarılıyor."""
    people = extract_people("Hazine ve Maliye Bakanı Mehmet Şimşek açıklama yaptı")
    assert [p.canonical_name for p in people] == ["Mehmet Şimşek"]


def test_extracts_governor_names() -> None:
    people = extract_people("TCMB Başkanı Fatih Karahan sunum yaptı")
    assert "Fatih Karahan" in {p.canonical_name for p in people}


def test_does_not_treat_institution_as_person() -> None:
    """'Merkez Bankası Başkanı' ifadesinde kurum kişiye dönüşmemeli."""
    people = extract_people("Merkez Bankası Başkanı konuştu")
    assert all("Bankası" not in p.canonical_name for p in people)


def test_unnamed_capitalized_words_are_not_people() -> None:
    """Unvansız büyük harfli sözcükler kişi sayılmaz (doğruluk kısıtı)."""
    assert extract_people("Ankara Istanbul Izmir raporu") == []


def test_extract_returns_both_types() -> None:
    found = extract("TCMB Başkanı Fatih Karahan enflasyon raporunu sundu")
    types = {e.entity_type for e in found}
    assert types == {"institution", "person"}


# ---------------------------------------------------------------- F1-16
def test_alias_resolution_unifies_institution_names() -> None:
    """DoD: 'Merkez Bankası' = 'TCMB' = tam ad -> tek varlık."""
    index = EntityIndex.build()
    canonical = "Türkiye Cumhuriyet Merkez Bankası"
    for alias in ("TCMB", "Merkez Bankası", "merkez bankasi", "Türkiye Cumhuriyet Merkez Bankası"):
        assert index.resolve(alias) == canonical


def test_alias_resolution_returns_none_for_unknown() -> None:
    assert EntityIndex.build().resolve("Bilinmeyen Kurum") is None


def test_same_entity_mentioned_twice_yields_one_result() -> None:
    found = extract_institutions("TCMB açıkladı. Merkez Bankası kararı yineledi.")
    assert len([e for e in found if e.canonical_name == "Türkiye Cumhuriyet Merkez Bankası"]) == 1


def test_longer_alias_wins_over_shorter() -> None:
    """'merkez bankası' -> TCMB; 'merkez' tek başına eşleşmemeli."""
    found = extract_institutions("Avrupa Merkez Bankası faiz kararı")
    names = {e.canonical_name for e in found}
    assert "Avrupa Merkez Bankası" in names


def test_key_entities_flagged_for_salience() -> None:
    """Spec §8.4 salience 'varlik_onemi' bileşeninin girdisi."""
    found = extract_institutions("TÜİK verisi")
    assert found[0].is_key_entity is True

    other = extract_institutions("Borsa İstanbul işlem hacmi")
    assert other[0].is_key_entity is False


def test_key_entities_are_subset_of_institutions() -> None:
    assert set(INSTITUTIONS) >= KEY_ENTITIES


# --------------------------------------------------------------- B-56
def test_ministries_and_boards_are_recognized() -> None:
    """B-56: Golden Set'in %38'inde hiç varlık tanınmıyordu.

    Bakanlıklar, düzenleyici kurullar ve kamu bankaları sözlükte yoktu;
    bu makalelerde `varlik_ok` kısıtı uygulanamıyor, precision'ı yalnızca
    benzerlik taşıyordu.
    """
    cases = {
        "Ticaret Bakanlığı ihracat rakamlarını açıkladı": "Ticaret Bakanlığı",
        "VDK'nin risk analiz sistemi devrede": "Vergi Denetim Kurulu",
        "Rekabet Kurumu A101'e koşullu izin verdi": "Rekabet Kurumu",
        "Ziraat Bankası net kârını açıkladı": "Ziraat Bankası",
        "EPDK elektrik tarifesini güncelledi": "Enerji Piyasası Düzenleme Kurumu",
        "OECD Türkiye büyüme tahminini yükseltti": "Ekonomik İşbirliği ve Kalkınma Örgütü",
    }
    for text, expected in cases.items():
        names = {e.canonical_name for e in extract_institutions(text)}
        assert expected in names, f"{expected!r} bulunamadı: {text!r}"


def test_no_short_ambiguous_aliases() -> None:
    """Kapsam genişlerken precision'ı koruyan kural.

    `_ALIAS_RE` sözcük sınırıyla eşleşir; "tim", "kik" gibi kısa alias'lar
    sıradan Türkçe metinde yanlış-pozitif üretir. Sözlüğe yeni kurum eklerken
    bu sınırın gevşetilmesi bu testle engellenir.
    """
    too_short = {alias for aliases in INSTITUTIONS.values() for alias in aliases if len(alias) < 3}
    assert not too_short, f"3 karakterden kısa alias precision'ı düşürür: {too_short}"


def test_new_institutions_are_not_key_entities() -> None:
    """B-56 kapsamı Tier-1 kümesini büyütmez.

    `KEY_ENTITIES`, kümelemede benzerlik kısıtını gevşeten bir VEYA dalıdır
    (Spec §11.4) ve salience'ı besler. Sözlüğü genişletmek bu kümeyi
    büyütseydi false merge riski artardı — G2'nin pazarlıksız koşulu.
    """
    assert (
        frozenset(
            {
                "Türkiye Cumhuriyet Merkez Bankası",
                "Türkiye İstatistik Kurumu",
                "Hazine ve Maliye Bakanlığı",
                "Resmî Gazete",
                "Para Politikası Kurulu",
                "Cumhurbaşkanlığı",
            }
        )
        == KEY_ENTITIES
    )


# --------------------------------------------- kümeleme kısıtı girdileri
def test_jaccard_similarity_for_clustering_constraint() -> None:
    """Spec §11.4: jaccard(article.entities, aday.entity_set) >= 0.25"""
    a = frozenset({"TÜİK", "TCMB"})
    b = frozenset({"TÜİK", "Hazine"})
    assert jaccard(a, b) == pytest.approx(1 / 3)
    assert jaccard(a, a) == 1.0
    assert jaccard(a, frozenset()) == 0.0
    assert jaccard(frozenset(), frozenset()) == 0.0


def test_common_key_entity_check() -> None:
    """Spec §11.4: 'VEYA en az 1 ortak Tier-1 varlık'"""
    a = extract_institutions("TÜİK enflasyon verisi")
    b = extract_institutions("TÜİK işgücü istatistikleri")
    c = extract_institutions("Borsa İstanbul işlem hacmi")
    assert has_common_key_entity(a, b)
    assert not has_common_key_entity(a, c)


def test_entity_set_helper() -> None:
    found = extract_institutions("TCMB ve TÜİK")
    assert entity_set(found) == frozenset(
        {"Türkiye Cumhuriyet Merkez Bankası", "Türkiye İstatistik Kurumu"}
    )


# --------------------------------------------------------------------------
# F1-14 regresyonu — canlı kümeleme turunda bulundu (Faz 2)
# --------------------------------------------------------------------------
def test_ef_search_is_set_via_set_config_not_set_local() -> None:
    """`SET LOCAL hnsw.ef_search = %s` Postgres'te sozdizimi hatasi verir.

    `SET` bind parametresi kabul etmez; gonderilirse
    `syntax error at or near "$1"` doner. Bu hata Faz 1'de fark edilmedi
    cunku kod yolu canli veritabanina karsi hic kosmamisti. Kumelemenin ilk
    canli turunda 11 makalenin 11'i de bu yuzden hata verdi.
    """
    from politikdesk.nlp.search import set_ef_search

    class FakeCursor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[object, ...]]] = []

        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            self.calls.append((sql, params))

    cur = FakeCursor()
    set_ef_search(cur, 64)

    sql, params = cur.calls[0]
    assert "SET LOCAL" not in sql, "SET parametrelenemez"
    assert "set_config" in sql
    assert params == ("64",)


def test_ef_search_rejects_out_of_range_values() -> None:
    """Deger SQL'e gomulmuyor ama yine de dogrulanir (savunma katmani)."""
    from politikdesk.nlp.search import set_ef_search

    for bad in (0, 1001, "64", 3.5):
        with pytest.raises(ValueError, match="ef_search"):
            set_ef_search(object(), bad)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# D16 — secilen model: multilingual-e5-large (docs/embedding-benchmark.md)
# --------------------------------------------------------------------------
def test_e5_models_require_the_query_prefix() -> None:
    """Onek uygulanmazsa benchmark'ta olculen kalite uretimde alinmaz.

    D16 kosumu e5 icin `query: ` onegiyle yapildi; uretim ayni oneki
    uygulamak zorundadir (eval/embedding_benchmark.py Candidate.text_prefix
    ile ayni kural).
    """
    from politikdesk.nlp.embedder import text_prefix_for

    assert text_prefix_for("intfloat/multilingual-e5-large") == "query: "
    assert text_prefix_for("BAAI/bge-m3") == ""


def test_production_and_benchmark_prefixes_agree() -> None:
    """Iki tarafin onek tanimi ayrilirsa benchmark uretimi yansitmaz."""
    from eval.embedding_benchmark import CANDIDATES
    from politikdesk.nlp.embedder import text_prefix_for

    for candidate in CANDIDATES.values():
        if candidate.self_hosted:
            assert text_prefix_for(candidate.model) == candidate.text_prefix, (
                f"{candidate.key}: benchmark oneki {candidate.text_prefix!r}, "
                f"uretim oneki {text_prefix_for(candidate.model)!r}"
            )


def test_b63_source_entity_signal() -> None:
    """B-63 (Spec v3.5 §11.4): Tier 1 resmi kaynakların kaynak adı varlık sinyali sağlar."""
    from politikdesk.nlp.entities import extract

    # Metinde TÜİK veya Merkez Bankası açıkça yazmasa bile source_slug ile yakalanır
    res = extract(
        "Temmuz Ayı Sanayi Üretim Endeksi Sonuçları",
        "Aylık değişim yüzde 0,1 oldu.",
        source_slug="tuik",
    )
    names = {e.canonical_name for e in res}
    assert "Türkiye İstatistik Kurumu" in names
    assert any(e.canonical_name == "Türkiye İstatistik Kurumu" and e.is_key_entity for e in res)

    # TCMB kaynağı
    res_tcmb = extract("Faiz Kararı Basın Duyurusu", "Kurul faizi sabit tuttu.", source_slug="tcmb")
    names_tcmb = {e.canonical_name for e in res_tcmb}
    assert "Türkiye Cumhuriyet Merkez Bankası" in names_tcmb


def test_resolve_entity_with_titles_and_aliases() -> None:
    """Unvan, takma ad ve kısaltmaların kanonik aktör/kurumlara çözümlenmesi."""
    from politikdesk.nlp.entities import resolve_entity

    # 1. Bakan ve Unvan çözümlemesi
    e_simsek = resolve_entity("Bakan Şimşek")
    assert e_simsek is not None
    assert e_simsek.canonical_name == "Mehmet Şimşek"
    assert e_simsek.entity_type == "person"

    # 2. TCMB Başkanı
    e_karahan = resolve_entity("TCMB Başkanı")
    assert e_karahan is not None
    assert e_karahan.canonical_name == "Fatih Karahan"
    assert e_karahan.entity_type == "person"

    # 3. Parti Lideri
    e_ozel = resolve_entity("CHP Lideri")
    assert e_ozel is not None
    assert e_ozel.canonical_name == "Özgür Özel"
    assert e_ozel.entity_type == "person"

    # 4. Kurum Kısaltması
    e_tcmb = resolve_entity("TCMB")
    assert e_tcmb is not None
    assert e_tcmb.canonical_name == "Türkiye Cumhuriyet Merkez Bankası"
    assert e_tcmb.entity_type == "institution"

    # 5. Tanımsız metin
    assert resolve_entity("Rastgele Bir Metin") is None
    assert resolve_entity("") is None
