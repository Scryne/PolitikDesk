import httpx

client = httpx.Client(
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    follow_redirects=True,
)
for path in [
    "/rss.xml",
    "/feed",
    "/feeds",
    "/atom.xml",
    "/rss/gundem.xml",
    "/rss/haber/gundem",
    "/rss/manset",
    "/rss/politika",
]:
    try:
        url = f"https://t24.com.tr{path}"
        r = client.get(url, timeout=5.0)
        print(f"{path:<20}: {r.status_code} {len(r.text)} {r.headers.get('content-type', '')[:30]}")
    except Exception as e:
        print(f"{path:<20}: {e}")
