import urllib.request
import urllib.parse
import re
import os
import json
import time
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www.gwent-league.org.uk/"
ARCHIVE_INDEX_URL = "https://www.gwent-league.org.uk/rindxarc-2000-2010.htm"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_HTML_DIR = os.path.join(SCRIPT_DIR, "raw_html")
RAW_DIV_DIR = os.path.join(SCRIPT_DIR, "raw_divisions")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "scrape_manifest.json")

os.makedirs(RAW_HTML_DIR, exist_ok=True)
os.makedirs(RAW_DIV_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
}

def fetch_url(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if i == retries - 1:
                print(f"  [ERROR] Failed to fetch {url}: {e}")
                return None
            time.sleep(1)

def run_scraper():
    print("=" * 60)
    print("GL Archive — Historical Scraper (2000 to 2010)")
    print("=" * 60)
    
    root_html = fetch_url(ARCHIVE_INDEX_URL)
    if not root_html:
        print("Failed to fetch root index.")
        return

    season_pattern = re.compile(r'<H3>\s*(\d{4})-(\d{4})\s*Season\s*</H3>(.*?)(?=<H3>|$)', re.IGNORECASE | re.DOTALL)
    match_pattern = re.compile(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', re.IGNORECASE)

    # Load existing manifest if present
    existing_manifest = []
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r") as f:
                existing_manifest = json.load(f)
        except Exception:
            existing_manifest = []

    existing_keys = {f"{m.get('season_key')}_m{m.get('match')}" for m in existing_manifest}
    new_entries = []

    seasons = list(season_pattern.finditer(root_html))
    print(f"Found {len(seasons)} seasons in 2000-2010 archive index.")

    for sm in seasons:
        start_year, end_year = sm.group(1), sm.group(2)
        season_str = f"{start_year}/{end_year}"
        season_key = f"{start_year}_{end_year}"
        section_html = sm.group(3)

        matches_in_season = list(match_pattern.finditer(section_html))
        print(f"\nProcessing Season {season_str} ({len(matches_in_season)} fixtures)...")

        for match_idx, mm in enumerate(matches_in_season, 1):
            href = mm.group(1).strip()
            desc = mm.group(2).strip()

            if href.lower().endswith('.pdf'):
                continue

            match_num_match = re.search(r'res\d+(\d)\.htm', href, re.IGNORECASE)
            if not match_num_match:
                match_num_match = re.search(r'^\s*(\d+)\s*\.', desc)
            match_num = int(match_num_match.group(1)) if match_num_match else match_idx

            fixture_id = f"{season_key}_m{match_num}"

            # Parse venue and date
            desc_clean = re.sub(r'^\s*\d+\.\s*&nbsp;\s*', '', desc).strip()
            date_part, venue_part = "", ""
            if " - " in desc_clean or " – " in desc_clean or " — " in desc_clean:
                parts = re.split(r'\s+[-–—]\s+', desc_clean, 1)
                date_part, venue_part = parts[0].strip(), parts[1].strip()
            else:
                date_part, venue_part = "", desc_clean

            hub_url = urllib.parse.urljoin(BASE_URL, href)
            print(f"  Match {match_num}: {venue_part} ({date_part})")

            hub_html = fetch_url(hub_url)
            if not hub_html:
                continue

            # Look for Senior Men (sm*.htm) and Senior Women (sl*.htm)
            all_links = re.findall(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', hub_html, re.I)

            men_file, women_file = None, None
            men_div_file, women_div_file = None, None

            for l_href, l_text in all_links:
                clean_href = os.path.basename(l_href.strip())
                # Exact match: sm + 2-digit year + 1-digit match + i.htm (e.g. sm061i.htm)
                if re.match(r'^sm\d{3}i\.htm$', clean_href, re.I):
                    men_file = urllib.parse.urljoin(hub_url, l_href)
                # Exact match: sl + 2-digit year + 1-digit match + i.htm (e.g. sl061i.htm)
                elif re.match(r'^sl\d{3}i\.htm$', clean_href, re.I):
                    women_file = urllib.parse.urljoin(hub_url, l_href)
                # Men Divisions: sm + 2-digit year + 1-digit match + d.htm
                elif re.match(r'^sm\d{3}d\.htm$', clean_href, re.I):
                    men_div_file = urllib.parse.urljoin(hub_url, l_href)
                # Women Divisions: sl + 2-digit year + 1-digit match + d.htm
                elif re.match(r'^sl\d{3}d\.htm$', clean_href, re.I):
                    women_div_file = urllib.parse.urljoin(hub_url, l_href)
                # Fallback to team standings if division file does not exist (2000-2003)
                elif not men_div_file and re.match(r'^sm\d{3}t\.htm$', clean_href, re.I):
                    men_div_file = urllib.parse.urljoin(hub_url, l_href)
                elif not women_div_file and re.match(r'^sl\d{3}t\.htm$', clean_href, re.I):
                    women_div_file = urllib.parse.urljoin(hub_url, l_href)

            # Download race files
            men_local_name = f"{season_key}_m{match_num}_men.htm"
            women_local_name = f"{season_key}_m{match_num}_women.htm"

            if men_file:
                content = fetch_url(men_file)
                if content:
                    with open(os.path.join(RAW_HTML_DIR, men_local_name), "w", encoding="utf-8") as f:
                        f.write(content)

            if women_file:
                content = fetch_url(women_file)
                if content:
                    with open(os.path.join(RAW_HTML_DIR, women_local_name), "w", encoding="utf-8") as f:
                        f.write(content)

            # Download divisions if available
            if men_div_file:
                content = fetch_url(men_div_file)
                if content:
                    with open(os.path.join(RAW_DIV_DIR, f"{season_key}_m{match_num}_men_div.htm"), "w", encoding="utf-8") as f:
                        f.write(content)

            if women_div_file:
                content = fetch_url(women_div_file)
                if content:
                    with open(os.path.join(RAW_DIV_DIR, f"{season_key}_m{match_num}_women_div.htm"), "w", encoding="utf-8") as f:
                        f.write(content)

            manifest_entry = {
                "season": season_str,
                "season_key": season_key,
                "match": match_num,
                "date": date_part,
                "venue": venue_part,
                "hub_url": hub_url,
                "men": {
                    "source_url": men_file,
                    "filename": men_local_name,
                    "cached": bool(men_file)
                },
                "women": {
                    "source_url": women_file,
                    "filename": women_local_name,
                    "cached": bool(women_file)
                }
            }
            new_entries.append(manifest_entry)
            time.sleep(0.3)

    # Merge manifest
    merged_manifest = [m for m in existing_manifest if m.get("season_key") not in {e["season_key"] for e in new_entries}] + new_entries
    merged_manifest.sort(key=lambda x: (x["season_key"], x["match"]))

    with open(MANIFEST_PATH, "w") as f:
        json.dump(merged_manifest, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Scraped {len(new_entries)} fixtures from 2000-2010. Total manifest count: {len(merged_manifest)}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
