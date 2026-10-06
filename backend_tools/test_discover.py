import urllib.request
import re
import os
import json
import time

BASE_URL = "https://www.gwent-league.org.uk/"
ARCHIVE_INDEX_URL = "https://www.gwent-league.org.uk/rindxarc-2010-2020.htm"
RAW_DIR = os.path.join(os.path.dirname(__file__), "raw_html")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "scrape_manifest.json")

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
}

import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch_url(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def discover_fixtures():
    print(f"Fetching archive index: {ARCHIVE_INDEX_URL}")
    html = fetch_url(ARCHIVE_INDEX_URL)
    if not html:
        print("Failed to fetch archive index.")
        return []

    # Find season sections: <H3>(YYYY-YYYY) Season</H3>
    season_pattern = re.compile(r'<H3>\s*(\d{4})-(\d{4})\s*Season\s*</H3>(.*?)(?=<H3>|$)', re.IGNORECASE | re.DOTALL)
    match_pattern = re.compile(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', re.IGNORECASE)

    discovered = []
    
    for sm in season_pattern.finditer(html):
        start_year, end_year = sm.group(1), sm.group(2)
        season_str = f"{start_year}/{end_year}"
        season_key = f"{start_year}_{end_year}"
        section_html = sm.group(3)

        for mm in match_pattern.finditer(section_html):
            href = mm.group(1).strip()
            desc = mm.group(2).strip()

            # Filter out PDF awards
            if href.lower().endswith('.pdf'):
                continue

            # Determine match number from filename or description
            match_num_match = re.search(r'res\d+(\d)\.htm', href, re.IGNORECASE)
            if not match_num_match:
                # Try from description e.g. "1. 11 October..."
                match_num_match = re.search(r'^\s*(\d+)\s*\.', desc)
            
            match_num = int(match_num_match.group(1)) if match_num_match else len([d for d in discovered if d["season"] == season_str]) + 1

            discovered.append({
                "season": season_str,
                "season_key": season_key,
                "match": match_num,
                "hub_href": href,
                "description": desc
            })

    return discovered

if __name__ == "__main__":
    fixtures = discover_fixtures()
    print(f"Discovered {len(fixtures)} fixtures across seasons 2010-2026.")
    for f in fixtures[:10]:
        print(f"  {f['season']} Match {f['match']}: {f['description']} -> {f['hub_href']}")
    if len(fixtures) > 10:
        print(f"  ... and {len(fixtures) - 10} more.")
