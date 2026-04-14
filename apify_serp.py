#!/usr/bin/env python3
"""Apify Google SERP Scraper — Fallback wenn WebSearch fehlschlägt.

Usage: python3 apify_serp.py "<query>" [results_per_page]
"""
import os
import sys
import requests
from dotenv import load_dotenv


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 apify_serp.py \"<query>\" [results_per_page]", file=sys.stderr)
        return 2

    query = sys.argv[1]
    results_per_page = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    load_dotenv()
    token = os.getenv("apify_api_key")
    if not token:
        print("Fehler: apify_api_key fehlt in .env", file=sys.stderr)
        return 1

    resp = requests.post(
        "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items",
        params={"token": token},
        json={
            "queries": query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": results_per_page,
            "languageCode": "de",
            "countryCode": "de",
        },
        timeout=120,
    )

    if resp.status_code not in (200, 201):
        print(f"Fehler: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    for item in resp.json():
        for r in item.get("organicResults", [])[:results_per_page]:
            print(r.get("title", "?"))
            print(r.get("url", "?"))
            print(r.get("description", "")[:200])
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
