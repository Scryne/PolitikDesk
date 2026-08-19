"""Dağıtım kapısının LLM uç erişilebilirlik adımı (ADR-009 §7).

⛔ Bu adımın var olma sebebi ölçülmüş bir arızadır. 19 Ağustos 2026'da
`.env`, iddia çıkarımını yerel bir uca (`127.0.0.1:11434`) yönlendirmişti.
O uç hiçbir zaman çalışamazdı: ortamda Ollama yoktu ve olsaydı bile
`127.0.0.1` **konteynerin kendisidir**, host değil.

Sistem hata vermedi. Her çağrı önce orada 180 saniye asıldı, sonra yedeğe
düştü ve çıkarım 6,5 kat yavaş koştu. Ne bir test, ne bir kapı, ne bir
alarm bunu yakaladı — çünkü `.env` git'te değildir ve sapma yalnızca
**çalışma zamanında**, worker'ın kendi ağ görüntüsünden görülebilir.

Buradaki testler kapının biçim ve sınıflandırma mantığını kilitler. Ağ
çağrısı yapılmaz: `_docker_exec` sahteleştirilir.
"""

from __future__ import annotations

import json

import pytest

from scripts import check_deployment as gate


@pytest.fixture
def sahte_exec(monkeypatch):  # noqa: ANN001, ANN201
    """`_docker_exec`'i verilen JSON'u döndürecek şekilde değiştirir."""

    def _kur(payload: object) -> None:
        ham = None if payload is None else json.dumps(payload)
        monkeypatch.setattr(gate, "_docker_exec", lambda *_a, **_k: ham)

    return _kur


def test_reachable_endpoints_pass(sahte_exec) -> None:  # noqa: ANN001
    sahte_exec(
        {
            "extraction": {"url": "https://integrate.api.nvidia.com/v1", "durum": "ok"},
            "generation": {"url": "https://integrate.api.nvidia.com/v1", "durum": "ok"},
        }
    )
    satirlar = gate.check_llm_endpoints()
    assert all("[OK]" in s for s in satirlar)
    assert not any("[ULASILAMIYOR]" in s for s in satirlar)


def test_dead_local_endpoint_is_caught(sahte_exec) -> None:  # noqa: ANN001
    """19 Ağustos'taki arızanın birebir kendisi.

    Çıkarım ölü, üretim sağlam — kapı ikisini AYIRT ETMELİ. Tek bir
    "LLM erişilebilir mi" bayrağı olsaydı, üretim ucu ayakta olduğu için
    kapı yeşil kalırdı ve arıza yine görünmezdi.
    """
    sahte_exec(
        {
            "extraction": {"url": "http://127.0.0.1:11434/v1", "durum": "ConnectionRefusedError"},
            "generation": {"url": "https://integrate.api.nvidia.com/v1", "durum": "ok"},
        }
    )
    satirlar = gate.check_llm_endpoints()

    cikarim = next(s for s in satirlar if "extraction" in s)
    uretim = next(s for s in satirlar if "generation" in s)
    assert "[ULASILAMIYOR]" in cikarim
    assert "127.0.0.1:11434" in cikarim, "Bulgu hangi ucu suçladığını yazmalı."
    assert "[OK]" in uretim, "Sağlam uç yanlışlıkla suçlanmamalı."


def test_timeout_is_also_a_failure(sahte_exec) -> None:
    """Reddedilme değil, ASILMA da arızadır — 180 sn'lik hâli tam buydu."""
    sahte_exec(
        {
            "extraction": {"url": "http://10.0.0.9:11434/v1", "durum": "timeout"},
            "generation": {"url": "https://integrate.api.nvidia.com/v1", "durum": "ok"},
        }
    )
    assert any("[ULASILAMIYOR]" in s for s in gate.check_llm_endpoints())


def test_unset_endpoint_falls_back_and_does_not_fail(sahte_exec) -> None:
    """Boş uç, genel yapılandırmaya düşmek demektir; arıza değildir.

    `anthropic` sağlayıcısında ayrı uç tanımlanmaz ve kapı orada da
    yeşil kalmalıdır — aksi hâlde sağlayıcı değiştiren herkes sahte
    bir alarmla karşılaşırdı.
    """
    sahte_exec(
        {
            "extraction": {"url": "", "durum": "tanimsiz"},
            "generation": {"url": "", "durum": "tanimsiz"},
        }
    )
    satirlar = gate.check_llm_endpoints()
    assert all("[OK]" in s for s in satirlar)


def test_missing_container_does_not_crash_the_gate(sahte_exec) -> None:
    """Worker kapalıysa adım ATLANIR, kapıyı düşürmez.

    Konteyner yokluğu zaten [1/7]'de raporlanıyor; aynı arızayı ikinci
    kez kırmızı yazmak bulguyu çoğaltır, bilgiyi artırmaz.
    """
    sahte_exec(None)
    satirlar = gate.check_llm_endpoints()
    assert len(satirlar) == 1
    assert "[ATLANDI]" in satirlar[0]
    assert "[ULASILAMIYOR]" not in satirlar[0]


def test_gate_step_is_wired_into_main() -> None:
    """Adım `main()` içinde çağrılıyor ve hataya bağlanıyor.

    Fonksiyonun var olması yetmez; çağrılmayan bir denetim, olmayan bir
    denetimdir.
    """
    import inspect

    kaynak = inspect.getsource(gate.main)
    assert "check_llm_endpoints()" in kaynak
    assert "[ULASILAMIYOR]" in kaynak
    assert "has_error = True" in kaynak.split("check_llm_endpoints()")[1][:400]
