"""20 Ağustos 2026 üretim denetiminin regresyon testleri.

Her test, denetimde ÖLÇÜLEREK doğrulanmış bir bulgunun geri gelmesini
engeller. Bulgular ve kanıtları `docs/AUDIT-2026-08-20.md` içindedir.

Kapsanan bulgular:
  A1  URL şema denetiminde C0 kontrol karakteri atlatması
      (gerçek Chromium'da doğrulandı; denetim `esc_url`e taşındı)
  A2  Makale bağlantısında şema doğrulaması yokluğu (`javascript:` DB'ye giriyordu)
  A3  Markdown dışa aktarımında bağlantı/sözdizimi enjeksiyonu
  A4  Tekilleştirme penceresinin kaynak başına yeniden yüklenmesi
  A5  HTTP yanıt gövdesinde boyut tavanı yokluğu
  A6  Celery küresel zaman sınırı ve beat süre sonu yokluğu
"""

from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════════ A1
# `esc_attr` / `esc_url` — C0 kontrol karakteri atlatması
#
# Tarayıcı, URL'i çözmeden önce BAŞTAKİ C0 kontrol karakterlerini (U+0000
# – U+001F) atar. Python'un `str.strip()`'i bunların bir kısmını boşluk
# saymaz, dolayısıyla eski şema denetimi `\x01javascript:` dizesini
# olduğu gibi geçiriyordu.
#
# 20 Ağustos 2026'da gerçek Chromium'da ölçüldü: `a.protocol` değeri
# `javascript:` dönüyordu, yani bağlantı tıklanınca kod çalışırdı.

# `str.strip()`in boşluk saymadığı, dolayısıyla eskiden elde kalan aralık.
_STRIP_KACIRAN_KONTROLLER = [chr(c) for c in range(0x00, 0x09)] + [
    chr(c) for c in range(0x0E, 0x1C)
]


@pytest.mark.parametrize("onek", _STRIP_KACIRAN_KONTROLLER)
def test_esc_url_c0_kontrol_onekli_javascript_semasini_engeller(onek: str) -> None:
    """Baştaki her C0 kontrol karakteri tarayıcıda soyulur; denetim de soymalı."""
    from politikdesk.web.ui.components import esc_url

    assert esc_url(f"{onek}javascript:alert(1)") == "#"


@pytest.mark.parametrize(
    "tehlikeli",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "  javascript:alert(1)",
        "java\tscript:alert(1)",
        "java\nscript:alert(1)",
        "java\rscript:alert(1)",
        "\x00javascript:alert(1)",
        "\x01java\tscript:alert(1)",
        "%6a%61%76%61script:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ],
)
def test_url_semasi_kara_listesi(tehlikeli: str) -> None:
    from politikdesk.web.ui.components import esc_url

    assert esc_url(tehlikeli) == "#"


def test_esc_url_izin_listesi_disini_reddeder() -> None:
    """İzin listesi: yeni bir tehlikeli şema çıktığında varsayılan KAPALI."""
    from politikdesk.web.ui.components import esc_url

    # Kara listede olmayan ama site içi de olmayan şemalar.
    assert esc_url("blob:https://evil.example/x") == "#"
    assert esc_url("filesystem:https://evil.example/x") == "#"
    assert esc_url("intent://evil#Intent;end") == "#"
    # Protokol-göreli adres MUTLAK bir adrestir; site içi sayılmaz.
    assert esc_url("//evil.example/x") == "#"


def test_esc_url_mesru_adresleri_gecirir() -> None:
    from politikdesk.web.ui.components import esc_url

    assert esc_url("https://anadolu.example/haber/1") == "https://anadolu.example/haber/1"
    assert esc_url("http://tuik.example/veri") == "http://tuik.example/veri"
    assert esc_url("/event/42") == "/event/42"
    assert esc_url("?sayfa=2") == "?sayfa=2"
    assert esc_url("#kanit") == "#kanit"
    assert esc_url("mailto:kurul@example.org") == "mailto:kurul@example.org"
    assert esc_url("") == ""


def test_esc_attr_url_olmayan_oznitelikte_metni_bozmaz() -> None:
    """Bir başlıkta 'javascript:' geçmesi meşrudur; `title` URL değildir."""
    from politikdesk.web.ui.components import _attrs

    cikti = _attrs(title="javascript: dilinde yeni sürüm", href="/haber/1")
    assert "javascript: dilinde yeni sürüm" in cikti
    assert 'href="/haber/1"' in cikti


def test_attrs_href_izin_listesinden_gecer() -> None:
    from politikdesk.web.ui.components import _attrs

    assert 'href="#"' in _attrs(href="\x01javascript:alert(1)")
    assert 'src="#"' in _attrs(src="javascript:alert(1)")
    assert 'action="#"' in _attrs(action="data:text/html,x")


def test_source_pill_dusman_url_ile_calismaz() -> None:
    from politikdesk.web.ui.components import source_pill

    pill = source_pill("Kaynak", tier=1, url="\x02javascript:alert(1)")
    assert "javascript" not in pill.lower()
    assert 'href="#"' in pill


# ═══════════════════════════════════════════════════════════════════ A2
# Makale bağlantısında şema doğrulaması
#
# `articles.canonical_url` üzerinde şema `CHECK` kısıtı YOK ve adaptörler
# akışın verdiği `<link>` değerini doğrulamıyordu. Yani düşman/ele
# geçirilmiş bir akış `javascript:` bağlantısını veritabanına yazdırabilirdi.


@pytest.mark.parametrize(
    "kotu",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "\x01javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://arsiv.example/dosya",
    ],
)
def test_canonicalize_url_web_disi_semayi_reddeder(kotu: str) -> None:
    from politikdesk.ingestion.normalizer import UnsafeArticleUrlError, canonicalize_url

    with pytest.raises(UnsafeArticleUrlError):
        canonicalize_url(kotu)


def test_canonicalize_url_mesru_adresi_bozmaz() -> None:
    """Şema denetimi eklenirken mevcut kanonikleştirme davranışı korunmalı."""
    from politikdesk.ingestion.normalizer import canonicalize_url

    assert (
        canonicalize_url("https://WWW.Example.com/haber/1/?utm_source=x&b=2#bolum")
        == "https://example.com/haber/1?b=2"
    )
    assert canonicalize_url("http://example.com:80/yol") == "http://example.com/yol"


def test_boru_hatti_kotu_baglantiyi_atlar_kaynagi_dusurmez() -> None:
    """Tek bozuk `<link>` yüzünden kaynağın tamamı kaybedilmemeli."""
    from politikdesk.ingestion import guard
    from politikdesk.ingestion.models import IngestionStats, RawItem
    from politikdesk.ingestion.pipeline import Pipeline
    from politikdesk.ingestion.repository import DedupWindow, SourceRow

    kaynak = SourceRow(
        id=1,
        slug="deneme",
        name="Deneme",
        tier=2,
        kind="news",
        independence_group=None,
        access_method="rss",
        tos_status="allowed",
        adapter="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
        extra_feeds=[],
        keyword_filter=[],
        topics=[],
        is_active=True,
        is_wire_reference=False,
    )
    kalemler = [
        RawItem(
            source_slug="deneme",
            url="javascript:alert(1)",
            title="Merkez Bankası faiz kararını açıkladı",
            summary="Enflasyon ve faiz üzerine ekonomi haberi.",
        ),
    ]
    pencere = DedupWindow(hashes={}, simhashes=[], texts={})
    boru = Pipeline(enforce_topic_scope=False)

    sonuc = boru._store_items(
        kalemler,
        kaynak,
        guard.GuardDecision(allowed=True, store_excerpt=True),
        IngestionStats(),
        window=pencere,
    )

    assert sonuc.rejected_urls == 1, "Güvensiz bağlantı ayrı sayaçta görünmeli"
    assert sonuc.stored == 0, "Güvensiz bağlantı saklanmamalı"


# ═══════════════════════════════════════════════════════════════════ A3
# Markdown dışa aktarımında bağlantı ve sözdizimi enjeksiyonu


def test_bulten_markdown_tehlikeli_baglantiyi_yazmaz() -> None:
    from politikdesk.web.export_formats import to_newsletter_markdown

    cikti = to_newsletter_markdown(
        {"title": "Olay", "salience_score": 10},
        [],
        [
            {
                "source_name": "Kaynak",
                "title": "Haber başlığı",
                "url": "javascript:alert(1)",
            }
        ],
    )
    assert "javascript:" not in cikti
    # Kaynak gösterimi DÜŞMEZ — yalnızca bağlantı ölür.
    assert "Kaynak" in cikti
    assert "Haber başlığı" in cikti


def test_bulten_markdown_baslik_baglanti_sozdizimini_kacamaz() -> None:
    """Başlıktaki `]` bağlantıyı erken kapatıp serbest Markdown yazdırmamalı."""
    from politikdesk.web.export_formats import to_newsletter_markdown

    cikti = to_newsletter_markdown(
        {"title": "Olay", "salience_score": 10},
        [],
        [
            {
                "source_name": "Kaynak",
                "title": "Başlık](https://evil.example) ve devamı [x",
                "url": "https://mesru.example/haber",
            }
        ],
    )
    # Saldırgan adresi düz METİN olarak görünebilir; olmaması gereken şey
    # onun BAĞLANTIYA dönüşmesidir. Bunun ölçüsü, başlıktaki `]`in
    # kaçırılmış olmasıdır: `\]` Markdown'da düz karakterdir, bağlantı
    # kapatmaz — dolayısıyla ardındaki `(...)` bir hedef adres olamaz.
    assert r"\](https://evil.example)" in cikti, (
        "Başlıktaki `]` kaçırılmamış — bağlantı sözdiziminden kaçılabiliyor"
    )
    # Kaçırılmamış (yani gerçekten bağlantı kuran) bir çıkış olmamalı.
    assert "Başlık](https://evil.example)" not in cikti
    assert "](https://mesru.example/haber)" in cikti, "Gerçek bağlantı korunmalı"


def test_bulten_markdown_url_parantezi_baglantiyi_kapatamaz() -> None:
    from politikdesk.web.export_formats import to_newsletter_markdown

    cikti = to_newsletter_markdown(
        {"title": "Olay", "salience_score": 10},
        [],
        [
            {
                "source_name": "Kaynak",
                "title": "Haber",
                "url": "https://mesru.example/a)cikis",
            }
        ],
    )
    assert "](https://mesru.example/a)cikis)" not in cikti
    assert "%29" in cikti


# ═══════════════════════════════════════════════════════════════════ A4
# Tekilleştirme penceresi tur başına BİR KEZ yüklenir


def test_dedup_penceresi_tur_basina_bir_kez_yuklenir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ölçüm: pencere 6.239 satır / 78 ms; saatte 970 kez yükleniyordu."""
    from politikdesk.ingestion import pipeline as pipeline_mod
    from politikdesk.ingestion import repository as repo_mod
    from politikdesk.ingestion.models import IngestionStats
    from politikdesk.ingestion.repository import DedupWindow, SourceRow

    yukleme_sayisi = 0

    def sahte_yukle(*args: object, **kwargs: object) -> DedupWindow:
        nonlocal yukleme_sayisi
        yukleme_sayisi += 1
        return DedupWindow(hashes={}, simhashes=[], texts={})

    def kaynak(i: int) -> SourceRow:
        return SourceRow(
            id=i,
            slug=f"kaynak-{i}",
            name=f"Kaynak {i}",
            tier=2,
            kind="news",
            independence_group=None,
            access_method="rss",
            tos_status="allowed",
            adapter="rss",
            base_url="https://example.com",
            feed_url="https://example.com/rss",
            extra_feeds=[],
            keyword_filter=[],
            topics=[],
            is_active=True,
            is_wire_reference=False,
        )

    kaynaklar = [kaynak(i) for i in range(1, 26)]

    monkeypatch.setattr(repo_mod, "load_dedup_window", sahte_yukle)
    monkeypatch.setattr(pipeline_mod.repository, "load_dedup_window", sahte_yukle)
    monkeypatch.setattr(pipeline_mod.repository, "list_sources", lambda **_: kaynaklar)

    cagrilan_pencereler: list[object] = []

    def sahte_run_source(self: object, source: SourceRow, *, window: object = None):  # noqa: ANN202
        cagrilan_pencereler.append(window)
        return IngestionStats()

    monkeypatch.setattr(pipeline_mod.Pipeline, "run_source", sahte_run_source)

    pipeline_mod.Pipeline().run_all(select="all")

    assert yukleme_sayisi == 1, (
        f"25 kaynak için pencere {yukleme_sayisi} kez yüklendi; tur başına 1 olmalı"
    )
    assert len(cagrilan_pencereler) == 25
    assert all(w is cagrilan_pencereler[0] for w in cagrilan_pencereler), (
        "Tüm kaynaklar AYNI pencere nesnesini paylaşmalı — paylaşım, tur içinde "
        "farklı kaynaklardan gelen aynı haberin de yakalanmasını sağlar"
    )


def test_run_source_pencere_verilmezse_kendi_yukler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tek kaynak elle koşturulduğunda (scripts.ingest) davranış bozulmamalı."""
    from politikdesk.ingestion import guard
    from politikdesk.ingestion import pipeline as pipeline_mod
    from politikdesk.ingestion.models import IngestionStats, RawItem
    from politikdesk.ingestion.repository import DedupWindow, SourceRow

    cagrildi = False

    def sahte_yukle(*args: object, **kwargs: object) -> DedupWindow:
        nonlocal cagrildi
        cagrildi = True
        return DedupWindow(hashes={}, simhashes=[], texts={})

    monkeypatch.setattr(pipeline_mod.repository, "load_dedup_window", sahte_yukle)
    monkeypatch.setattr(pipeline_mod.repository, "insert_article", lambda *a, **k: 1)

    kaynak = SourceRow(
        id=1,
        slug="k",
        name="K",
        tier=2,
        kind="news",
        independence_group=None,
        access_method="rss",
        tos_status="allowed",
        adapter="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
        extra_feeds=[],
        keyword_filter=[],
        topics=[],
        is_active=True,
        is_wire_reference=False,
    )
    kalemler = [
        RawItem(
            source_slug="k",
            url="https://example.com/haber/1",
            title="Enflasyon verisi açıklandı",
            summary="TÜFE aylık bazda arttı.",
        )
    ]

    pipeline_mod.Pipeline(enforce_topic_scope=False)._store_items(
        kalemler,
        kaynak,
        guard.GuardDecision(allowed=True, store_excerpt=True),
        IngestionStats(),
    )
    assert cagrildi, "Pencere verilmediğinde `_store_items` kendi penceresini yüklemeli"


# ═══════════════════════════════════════════════════════════════════ A5
# HTTP yanıt gövdesi tavanı


def test_yanit_boyut_tavani_tanimli_ve_makul() -> None:
    from politikdesk.ingestion.http import MAX_RESPONSE_BYTES

    # En büyük meşru gövde ölçülen ~3 MB (Resmî Gazete fihristi).
    assert 4 * 1024 * 1024 <= MAX_RESPONSE_BYTES <= 64 * 1024 * 1024


def test_bildirilen_buyuk_content_length_reddedilir() -> None:
    """Gövde OKUNMADAN, bildirilen uzunlukla reddedilmeli."""
    import httpx

    from politikdesk.ingestion.http import (
        MAX_RESPONSE_BYTES,
        HttpClient,
        ResponseTooLargeError,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": str(MAX_RESPONSE_BYTES + 1)},
            content=b"x" * 10,
        )

    istemci = HttpClient(respect_robots=False, enforce_ssrf=False, max_retries=1)
    istemci._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ResponseTooLargeError):
        istemci.get("https://example.com/dev")


def test_tavani_asan_govde_akista_kesilir() -> None:
    """Content-Length YOKSA (chunked/sıkıştırılmış) akış sırasında kesilmeli."""
    import httpx

    from politikdesk.ingestion.http import (
        MAX_RESPONSE_BYTES,
        HttpClient,
        ResponseTooLargeError,
    )

    def govde():  # noqa: ANN202
        # Tavanın iki katı; Content-Length bildirilmez.
        parca = b"x" * (1024 * 1024)
        for _ in range((MAX_RESPONSE_BYTES // len(parca)) * 2):
            yield parca

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=govde())

    istemci = HttpClient(respect_robots=False, enforce_ssrf=False, max_retries=1)
    istemci._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ResponseTooLargeError):
        istemci.get("https://example.com/bomba")


def test_tavan_altindaki_govde_normal_calisir() -> None:
    """Tavan eklenirken olağan yanıt davranışı bozulmamalı."""
    import httpx

    from politikdesk.ingestion.http import HttpClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<rss>merhaba</rss>")

    istemci = HttpClient(respect_robots=False, enforce_ssrf=False, max_retries=1)
    istemci._client = httpx.Client(transport=httpx.MockTransport(handler))
    yanit = istemci.get("https://example.com/rss")
    assert yanit.text == "<rss>merhaba</rss>"
    assert yanit.content == b"<rss>merhaba</rss>"
    assert yanit.status_code == 200


def test_cok_buyuk_govde_yeniden_denenmez() -> None:
    """Bombayı yeniden istemek saldırıyı çoğaltır."""
    from politikdesk.ingestion.http import NON_RETRYABLE_ERRORS, ResponseTooLargeError

    assert ResponseTooLargeError in NON_RETRYABLE_ERRORS


# ═══════════════════════════════════════════════════════════════════ A6
# Celery zaman sınırı ve beat süre sonu


def test_celery_kuresel_zaman_siniri_tanimli() -> None:
    """Sınırsız görev, `--concurrency 2` worker'ı süresiz kilitleyebilirdi."""
    from politikdesk.worker import app

    soft = app.conf.task_soft_time_limit
    hard = app.conf.task_time_limit
    assert soft is not None and soft > 0, "task_soft_time_limit tanımlı olmalı"
    assert hard is not None and hard > soft, "Sert sınır yumuşak sınırdan büyük olmalı"


def test_worker_kaybinda_gorev_geri_verilir() -> None:
    from politikdesk.worker import app

    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True


def test_sabit_arali_beat_gorevleri_bayatlayinca_duser() -> None:
    """Worker bir saat kapalı kalırsa 12 `ingest_all` birikmemeli."""
    from politikdesk.worker import app

    sabit_arali = {
        ad: girdi
        for ad, girdi in app.conf.beat_schedule.items()
        if isinstance(girdi.get("schedule"), int | float)
    }
    assert sabit_arali, "Sabit aralıklı görev bulunamadı — test anlamını yitirmiş"

    for ad, girdi in sabit_arali.items():
        expires = girdi.get("options", {}).get("expires")
        assert expires is not None, f"{ad}: `expires` tanımlı değil"
        assert 0 < expires <= girdi["schedule"], (
            f"{ad}: `expires` ({expires}) bir sonraki turdan ({girdi['schedule']}) "
            "sonra dolmalı, yoksa birikme sürer"
        )


def test_llm_bagimli_gorev_kuresel_siniri_ezer() -> None:
    """İddia çıkarımı ölçülen iş yüküne göre KENDİ sınırını taşımalı.

    Ölçüm (20 Ağu 2026, 3.928 çağrı): tek LLM çağrısı p95 80,8 sn,
    azami 335,3 sn. Görev 5 olay işler. Küresel 600 sn'lik varsayılan
    bırakılırsa parti düzenli kesilir ve her kesilme ücretsiz katman
    kotasını boşa harcar.
    """
    from politikdesk.tasks import CLAIM_BATCH_EVENTS, extract_claims_pending

    soft = extract_claims_pending.soft_time_limit
    hard = extract_claims_pending.time_limit
    assert soft is not None and hard is not None

    olculen_azami_cagri_sn = 335
    assert soft >= CLAIM_BATCH_EVENTS * olculen_azami_cagri_sn, (
        f"Yumuşak sınır ({soft} sn) ölçülen en kötü partiden "
        f"({CLAIM_BATCH_EVENTS} × {olculen_azami_cagri_sn} sn) küçük"
    )
    assert hard > soft


def test_crontab_gorevleri_sure_sonu_almaz() -> None:
    """Brifing gecikmeli de olsa koşmalı; hiç koşmaması daha kötüdür."""
    from celery.schedules import crontab

    from politikdesk.worker import app

    for ad, girdi in app.conf.beat_schedule.items():
        if isinstance(girdi.get("schedule"), crontab):
            assert "expires" not in girdi.get("options", {}), (
                f"{ad}: günün belirli anına ait görev süre sonu almamalı"
            )
