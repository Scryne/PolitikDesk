"""Klavye kısayolu sözleşmesi (Roadmap Faz 8.3).

Bu dosya tek bir şeyi ölçer ve o şey bu depoda bir kez gerçekten kırıldı:

    beyan  ↔  uygulama  ↔  ekranda görünen

`war_room.py` bir dönem J/K/X kısayollarını listeliyordu; o tuşlar
`feed.py`'nin dinleyicisine bağlıydı ve kumanda odasında hiçbir şey
yapmıyordu. Elle düzeltildi — ama elle yapılan düzeltme tekrarı
engellemez. Buradaki testler engeller.

⛔ Bu testler "kısayol çalışıyor mu" demez; ÇALIŞMASI BEYAN EDİLENLE
UYGULANANIN AYNI OLDUĞUNU söyler. Davranışın kendisi tarayıcı turunda
(`pd ui-check`) ve elle doğrulanır.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.ui import keys

client = TestClient(app)

# Sözleşmesi olan her rota. Yeni bir rota kısayol kazandığında buraya da
# eklenir; eklenmezse `test_every_declared_route_is_covered` uyarır.
ROUTES: tuple[str, ...] = ("/feed", "/war-room")


def _page(route: str) -> str:
    response = client.get(route)
    assert response.status_code == 200, f"{route} → HTTP {response.status_code}"
    return response.text


def _keymap(html: str) -> list[dict[str, object]]:
    """Sayfaya gömülen `window.pdKeymap` tablosunu ayrıştırır."""
    match = re.search(r"window\.pdKeymap = (\[.*?\]);", html, re.DOTALL)
    assert match is not None, "Sayfa `window.pdKeymap` tablosunu taşımıyor."
    parsed = json.loads(match.group(1))
    assert isinstance(parsed, list)
    return parsed


def _registered(html: str) -> set[str]:
    """Sayfada `window.pdKey('ad', …)` ile kaydedilmiş eylem adları."""
    return set(re.findall(r"window\.pdKey\(\s*'([^']+)'", html))


# ═══════════════════════════════════════════════ beyan ↔ tablo


@pytest.mark.parametrize("route", ROUTES)
def test_keymap_matches_declaration(route: str) -> None:
    """Sayfaya gömülen tuş tablosu, sözleşmenin birebir kendisidir."""
    beyan = [
        {"keys": list(item.keys), "action": item.action}
        for item in keys.for_route(route)
        if item.action
    ]
    assert _keymap(_page(route)) == beyan


def test_global_shortcuts_are_not_in_keymap() -> None:
    """Ctrl+K ve Esc tabloya girmez — onları kabuk kendi yönetir.

    Girseydi iki dinleyici aynı tuşa basardı: dağıtıcı Ctrl'lü olayları
    zaten atlıyor, yani kayıt sessizce ölü olurdu. Ölü kayıt, sözleşmeyi
    yalancı yapar.
    """
    for route in ROUTES:
        aksiyonlar = {entry["action"] for entry in _keymap(_page(route))}
        for genel in keys.GLOBAL:
            assert genel.action is None
            assert genel.display not in aksiyonlar


# ═══════════════════════════════════════════════ beyan ↔ uygulama


@pytest.mark.parametrize("route", ROUTES)
def test_declared_shortcuts_have_handlers(route: str) -> None:
    """Beyan edilen her kısayolun sayfada bir gövdesi vardır.

    Bu testin yakaladığı arıza: kullanıcı tuşa basar, hiçbir şey olmaz.
    """
    html = _page(route)
    kayitli = _registered(html)
    for item in keys.for_route(route):
        if item.action:
            assert item.action in kayitli, (
                f"{route}: '{item.action}' beyan edilmiş ama `pdKey` ile "
                f"kaydedilmemiş — tuş çalışmaz."
            )


@pytest.mark.parametrize("route", ROUTES)
def test_handlers_are_all_declared(route: str) -> None:
    """Kaydedilmiş her eylemin bir beyanı vardır.

    Ters yön de arızadır: beyansız bir kısayol ekranda GÖRÜNMEZ ve
    tabloda olmadığı için hiç tetiklenmez — yazan kişi çalıştığını
    sanır, kullanıcı hiç bilmez.
    """
    beyan = {item.action for item in keys.for_route(route) if item.action}
    for action in _registered(_page(route)):
        assert action in beyan, (
            f"{route}: '{action}' kaydedilmiş ama `keys.PAGE` içinde "
            f"beyan edilmemiş — ekranda görünmez."
        )


# ═══════════════════════════════════════════════ beyan ↔ görünen


@pytest.mark.parametrize("route", ROUTES)
def test_shortcuts_are_visible_on_their_page(route: str) -> None:
    """Rotanın her kısayolu o ekranda yazılı olarak görünür."""
    html = _page(route)
    for item in keys.all_for_route(route):
        assert item.display in html, (
            f"{route}: '{item.display}' kısayolu çalışıyor ama ekranda yazmıyor."
        )
        assert item.label in html, f"{route}: '{item.label}' açıklaması ekranda yok."


def test_other_pages_do_not_advertise_feed_shortcuts() -> None:
    """Roadmap 8.3'ün asıl şartı: kısayol yalnızca aktif olduğu yerde.

    Kumanda odası bir dönem J/K/X listeliyordu ve o tuşlar orada ölüydü.
    """
    html = _page("/war-room")
    for item in keys.for_route("/feed"):
        assert item.action not in _registered(html), (
            f"/war-room, /feed kısayolu '{item.action}' kaydını taşıyor."
        )

    # J ve K tuşlarının kumanda odasında kısayol olarak REKLAMI yapılamaz.
    # (Metin içinde "Gündem Masası ekranındadır" gibi bir YÖNLENDİRME
    # serbesttir; ölçülen şey `shortcut-key` rozetiyle sunulmalarıdır.)
    rozetler = set(re.findall(r'<kbd class="shortcut-key">([^<]*)</kbd>', html))
    calisanlar = {item.display for item in keys.all_for_route("/war-room")}
    assert rozetler <= calisanlar, (
        f"/war-room ekranında çalışmayan kısayol rozeti var: {rozetler - calisanlar}"
    )


# ═══════════════════════════════════════════════ sözleşmenin kendisi


def test_every_declared_route_is_covered() -> None:
    """`keys.PAGE`'e satır ekleyen, bu dosyadaki `ROUTES`'a da ekler."""
    assert set(keys.PAGE) <= set(ROUTES), (
        f"Test edilmeyen kısayol rotası: {set(keys.PAGE) - set(ROUTES)}"
    )


def test_no_key_is_bound_twice_on_a_route() -> None:
    """Aynı tuş bir rotada iki eyleme bağlanamaz — hangisinin kazandığı
    dağıtıcının satır sırasına kalırdı ve bu görünmez bir kural olurdu."""
    for route in keys.PAGE:
        gorulen: dict[str, str] = {}
        for item in keys.for_route(route):
            for key in item.keys:
                assert key not in gorulen, (
                    f"{route}: '{key}' tuşu hem '{gorulen[key]}' hem "
                    f"'{item.action}' eylemine bağlı."
                )
                gorulen[key] = item.action or "?"


def test_letter_shortcuts_declare_both_cases() -> None:
    """Caps Lock açıkken tarayıcı 'J' gönderir, 'j' değil.

    Yalnız küçük harfi dinleyen bir kısayol, Caps Lock'lu kullanıcıda
    sessizce ölür — kimsenin aklına gelmeyen ve şikâyet edilmeyen bir
    arıza türü.
    """
    for route in keys.PAGE:
        for item in keys.for_route(route):
            for key in item.keys:
                if len(key) == 1 and key.isalpha():
                    esi = key.upper() if key.islower() else key.lower()
                    assert esi in item.keys, (
                        f"{route}/{item.action}: '{key}' var ama '{esi}' yok."
                    )
