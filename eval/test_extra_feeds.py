import httpx

client = httpx.Client(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, follow_redirects=True)
candidates = [
    ("anka_rss", "https://ankahaber.net/rss"),
    ("anka_feed", "https://ankahaber.net/feed"),
    ("birgun_rss", "https://www.birgun.net/xml/rss.xml"),
    ("birgun_feed", "https://www.birgun.net/feed"),
    ("cumhuriyet_rss", "https://www.cumhuriyet.com.tr/rss"),
    ("cumhuriyet_siyaset", "https://www.cumhuriyet.com.tr/rss/siyaset.xml"),
    ("evrensel_rss", "https://www.evrensel.net/rss/haber.xml"),
]

for name, url in candidates:
    try:
        r = client.get(url, timeout=5.0)
        is_xml = "<rss" in r.text[:300] or "<feed" in r.text[:300] or "<?xml" in r.text[:300]
        print(f"{name:<20}: {r.status_code} len={len(r.text)} is_xml={is_xml}")
    except Exception as e:
        print(f"{name:<20}: ERROR {e}")
