"""Komuta paleti sözleşmesi (Roadmap Faz 8.2).

D-02'nin dersi: palet aktör aramasını **sessizce** hiç göstermiyordu.
JS, `{actors: [...]}` sözleşmesinde olmayan iki anahtarı okuyordu; ne
hata çıkıyordu ne sonuç. Bir özelliğin var olmadığını kimse şikâyet
etmez — bu yüzden sessiz arıza en pahalısıdır.

Buradaki testler o arızanın üç kaynağını kapatır:

    1. Sözleşme kaymasi  → sonuç nesnesinin anahtarları kilitli
    2. Kopya liste       → paletin sayfa listesi `NAV`'dan türemek zorunda
    3. Eksik tür         → roadmap'in saydığı altı tür aranabilir olmalı
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web import search
from politikdesk.web.ui.shell import _CMD_JS, NAV

client = TestClient(app)

# `SearchHit.as_dict()`'in ürettiği anahtarlar. JS bu adları okur; biri
# değişirse palet o türü sessizce göstermez.
CONTRACT_KEYS: frozenset[str] = frozenset({"kind", "group", "title", "subtitle", "href"})


# ═══════════════════════════════════════════════ sonuç sözleşmesi


def test_search_response_shape() -> None:
    response = client.get("/api/search", params={"q": "faiz"})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"query", "results"}
    assert isinstance(payload["results"], list)


def test_every_result_carries_the_full_contract() -> None:
    """Her sonuç AYNI anahtarları taşır — tür fark etmez.

    Türe göre değişen bir şekil, istemcide türe göre dallanma demektir;
    o dallanmanın bir dalı bir gün sessizce ölür (D-02).
    """
    payload = client.get("/api/search", params={"q": "faiz"}).json()
    assert payload["results"], "Örnek sorgu hiç sonuç döndürmedi; test anlamsız kalır."
    for hit in payload["results"]:
        assert set(hit) == CONTRACT_KEYS, f"Sözleşme dışı sonuç: {sorted(hit)}"
        assert all(isinstance(v, str) for v in hit.values())
        assert hit["title"].strip(), "Başlıksız sonuç seçilebilir değildir."
        assert hit["href"].startswith("/"), "Palet yalnızca uygulama içine gider."


def test_group_label_matches_kind() -> None:
    """`group`, `kind`'ın Türkçe karşılığıdır — istemci çeviri yapmaz."""
    payload = client.get("/api/search", params={"q": "faiz"}).json()
    for hit in payload["results"]:
        assert hit["group"] == search.KIND_LABELS[hit["kind"]]


def test_short_query_returns_nothing() -> None:
    """Tek harf, veritabanının yarısıyla eşleşir; sonuç değil gürültüdür."""
    for q in ("", " ", "a"):
        assert client.get("/api/search", params={"q": q}).json()["results"] == []


def test_limit_is_capped_server_side() -> None:
    """Tavan istemciye bırakılmaz — istemci 10.000 isteyebilir."""
    payload = client.get("/api/search", params={"q": "a" * 2, "limit": 99999}).json()
    assert len(payload["results"]) <= 60


# ═══════════════════════════════════════════════ kopya liste yok


def test_palette_page_list_comes_from_nav() -> None:
    """Paletin gezinme listesi `shell.NAV`'ın kendisidir."""
    nav_hrefs = {href for _group, items in NAV for href, _label, _icon in items}
    assert {hit.href for hit in search.page_hits()} == nav_hrefs


def test_palette_js_has_no_hardcoded_page_list() -> None:
    """JS içinde elle yazılmış sayfa listesi KALMADI.

    Kopya varken nav'a eklenen sayfa palette görünmüyor, nav'dan kalkan
    sayfa palette kırık bağlantı olarak duruyordu. İkisi de sessiz.
    """
    for _group, items in NAV:
        for href, label, _icon in items:
            assert href not in _CMD_JS, f"`_CMD_JS` içinde gömülü yol: {href}"
            assert label not in _CMD_JS, f"`_CMD_JS` içinde gömülü sayfa adı: {label}"


def test_rendered_page_ships_the_nav_items() -> None:
    """Liste sunucudan gelir ve tam olarak `NAV` kadardır."""
    html = client.get("/feed").text
    match = re.search(r"window\.pdNavItems = (\[.*?\]);", html, re.DOTALL)
    assert match is not None, "Sayfa `window.pdNavItems` taşımıyor."
    items = json.loads(match.group(1))
    assert [item["href"] for item in items] == [hit.href for hit in search.page_hits()]
    for item in items:
        assert set(item) == CONTRACT_KEYS


# ═══════════════════════════════════════════════ tür kapsamı


def test_roadmap_kinds_are_all_searchable() -> None:
    """Roadmap 8.2'nin saydığı altı tür + gezinme."""
    beklenen = {"actor", "event", "claim", "source", "indicator", "relation"}
    assert beklenen <= set(search.KIND_LABELS)
    assert "page" in search.KIND_LABELS


@pytest.mark.parametrize(
    ("query", "kind"),
    [
        ("gündem", "page"),
        ("faiz", "event"),
        ("faiz", "claim"),
        ("faiz", "indicator"),
        ("anadolu", "source"),
        ("şimşek", "actor"),
    ],
)
def test_each_kind_is_reachable_on_live_data(query: str, kind: str) -> None:
    """Tür TANIMLI değil, ULAŞILABİLİR olmalı.

    Bir türün `KINDS` içinde yazması onu aranabilir yapmaz; sorgunun
    gerçekten o türden sonuç döndürdüğü ölçülür. `relation` bu listede
    yok: yayın kapısı kapalı (ADR-010) ve kapalıyken sonuç üretmemesi
    doğru davranıştır — `test_relations_respect_the_publication_gate`.
    """
    kinds = {hit.kind for hit in search.search(query, limit=60)}
    assert kind in kinds, f"'{query}' sorgusu '{kind}' türünden sonuç vermedi: {kinds}"


# ═══════════════════════════════════════════════ kırmızı çizgiler


def test_relations_respect_the_publication_gate() -> None:
    """ADR-010: kapı kapalıyken ilişki sonucu ÜRETİLMEZ.

    `search.py` `stance_shifts` tablosuna kendi sorgusunu atıyor, yani
    `shift_store`'un okuma kapısını atlayabilirdi. Bu test o yolu kapatır.
    """
    from politikdesk.political_memory import shift_store

    if shift_store.PUBLISH_GATE_OPEN:
        pytest.skip("Yayın kapısı açık — bu test kapalı kapı davranışını ölçer.")

    for query in ("erdoğan", "bahçeli", "faiz", "enflasyon", "özel"):
        kinds = {hit.kind for hit in search.search(query, limit=60)}
        assert "relation" not in kinds, f"Kapı kapalıyken ilişki sonucu sızdı: {query}"


def test_source_results_carry_no_political_label() -> None:
    """Spec §8.5: kaynak yalnızca ad + katman + yayın grubu ile anılır.

    Alt satırın YAPISI ölçülür, sözcük listesi değil: izin verilen
    parçalar `TIER_LABELS` değerleri, "yayın grubu: …" ve "pasif".
    Sözcük kara listesi yapılsaydı listede olmayan bir sıfat geçebilirdi.
    """
    from politikdesk.web.ui.components import TIER_LABELS

    izinli = set(TIER_LABELS.values())
    bulundu = 0
    for query in ("anadolu", "gazete", "haber", "resmi"):
        for hit in search.search(query, limit=60):
            if hit.kind != "source":
                continue
            bulundu += 1
            for parca in hit.subtitle.split(" · "):
                assert parca in izinli or parca.startswith("yayın grubu: ") or parca == "pasif", (
                    f"Kaynak alt satırında beklenmeyen parça: {parca!r}"
                )
    assert bulundu, "Hiç kaynak sonucu bulunamadı; test anlamsız kalır."


def test_event_results_never_call_salience_a_truth_score() -> None:
    """Spec §15/13: salience bir DOĞRULUK skoru değildir.

    Doğru sözcük "önem". "güven", "doğruluk", "puan" ve "skor" bu alanda
    geçemez — kullanıcı sayıyı marka değil ölçek sanar.
    """
    yasak = ("güven", "doğruluk", "puan", "skor", "güvenilir")
    for hit in search.search("faiz", limit=60):
        if hit.kind != "event":
            continue
        assert hit.subtitle.startswith("önem "), hit.subtitle
        assert not any(s in hit.subtitle.casefold() for s in yasak), hit.subtitle


# ═══════════════════════════════════════════════ güvenlik


def test_palette_renders_results_as_text_not_html() -> None:
    """Sonuç metinleri DOM'a `textContent` ile basılır.

    Aktör adları NER ile, iddia metinleri LLM ile DIŞ KAYNAKLI makale
    gövdesinden çıkarılıyor. Böyle bir dizeyi `innerHTML`'e vermek saklı
    XSS'tir ve CSP nonce'u (Faz 7) bunu engellemez — enjekte edilen kod
    sunucunun kendi script bloğunda çalışırdı.
    """
    # Yorum satırlarında "innerHTML" sözcüğü geçebilir (neden
    # kullanılmadığını anlatan not orada); ölçülen şey ATAMA'dır.
    assert re.search(r"\.innerHTML\s*=", _CMD_JS) is None
    assert "textContent" in _CMD_JS
    assert "replaceChildren" in _CMD_JS


def test_embedded_json_cannot_close_the_script_tag() -> None:
    """`</script>` içeren bir veri, script bloğunu erkenden kapatamaz."""
    from politikdesk.web.ui.components import script_json

    tehlike = script_json({"x": "</script><img src=x onerror=alert(1)>"})
    assert "</script>" not in tehlike
    assert json.loads(tehlike)["x"].startswith("</script>")


# ═══════════════════════════════════════════════ D-02 kilidi


def test_memory_actors_contract_is_unchanged() -> None:
    """`/api/memory/actors` sözleşmesi yerinde duruyor.

    Palet artık bu ucu kullanmıyor ama siyasi hafıza ekranı kullanıyor.
    D-02 sözleşmesi (`{actors: [{name, entity_type}]}`) kilitli kalır.
    """
    payload = client.get("/api/memory/actors", params={"q": "a", "limit": 3}).json()
    assert "actors" in payload
    for actor in payload["actors"]:
        assert "name" in actor
        assert "entity_type" in actor
