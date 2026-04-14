#!/usr/bin/env python3
"""Apify Website Content Crawler — Fallback wenn Playwright blockiert.

Usage: python3 apify_crawl.py "<url>" [max_pages]
"""
import os
import sys
import requests
from dotenv import load_dotenv


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 apify_crawl.py \"<url>\" [max_pages]", file=sys.stderr)
        return 2

    url = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    load_dotenv()
    token = os.getenv("apify_api_key")
    if not token:
        print("Fehler: apify_api_key fehlt in .env", file=sys.stderr)
        return 1

    resp = requests.post(
        "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items",
        params={"token": token},
        json={
            "startUrls": [{"url": url}],
            "maxCrawlPages": max_pages,
            "crawlerType": "cheerio",
        },
        timeout=120,
    )

    if resp.status_code not in (200, 201):
        print(f"Fehler: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    for item in resp.json():
        print("URL:", item.get("url", "?"))
        print("Text:", item.get("text", "")[:5000])
        print("---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
