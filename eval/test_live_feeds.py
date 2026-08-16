import httpx

client = httpx.Client(
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    follow_redirects=True,
)
candidates = [
    ("t24_rss", "https://t24.com.tr/rss"),
    ("t24_pol", "https://t24.com.tr/rss/haber/politika"),
    ("duvar_cat", "https://www.gazeteduvar.com.tr/rss/kategori/politika"),
    ("duvar_root", "https://www.gazeteduvar.com.tr/rss"),
    ("diken_cat", "https://www.diken.com.tr/kategori/siyaset/feed/"),
    ("diken_root", "https://www.diken.com.tr/feed/"),
    ("sozcu_pol", "https://www.sozcu.com.tr/rss/politika.xml"),
    ("sozcu_son", "https://www.sozcu.com.tr/feeds-son-dakika"),
    ("sozcu_rss", "https://www.sozcu.com.tr/rss/tum-haberler.xml"),
    ("bbc", "https://feeds.bbci.co.uk/turkce/rss.xml"),
    ("aa", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    ("trt", "https://www.trthaber.com/gundem_articles.rss"),
    ("haberturk", "https://www.haberturk.com/rss/manset.xml"),
]
for name, url in candidates:
    try:
        r = client.get(url, timeout=6.0)
        is_xml = "<rss" in r.text[:300] or "<feed" in r.text[:300] or "<?xml" in r.text[:300]
        print(f"{name:<12}: {r.status_code} len={len(r.text)} is_xml={is_xml}")
    except Exception as e:
        print(f"{name:<12}: ERROR {e}")
