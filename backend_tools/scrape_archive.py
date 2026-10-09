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
ARCHIVE_INDEX_URL = "https://www.gwent-league.org.uk/rindxarc-2010-2020.htm"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "raw_html")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "scrape_manifest.json")

os.makedirs(RAW_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
}

def fetch_url(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [ERROR] Fetching {url}: {e}")
        return None

def clean_url(href):
    # Strip any query parameters like ?ver2.5
    return href.split('?')[0].strip()

def run_scraper(force=False):
    print("=" * 60)
    print("GL Archive — Historical Scraper (2010 to 2026)")
    print("=" * 60)
    print(f"Fetching root archive index: {ARCHIVE_INDEX_URL}")
    
    root_html = fetch_url(ARCHIVE_INDEX_URL)
    if not root_html:
        print("Failed to fetch root archive index.")
        return

    season_pattern = re.compile(r'<H3>\s*(\d{4})-(\d{4})\s*Season\s*</H3>(.*?)(?=<H3>|$)', re.IGNORECASE | re.DOTALL)
    match_pattern = re.compile(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', re.IGNORECASE)

    manifest = []
    
    seasons = list(season_pattern.finditer(root_html))
    print(f"Found {len(seasons)} seasons in archive index.")

    for sm in seasons:
        start_year, end_year = sm.group(1), sm.group(2)
        season_str = f"{start_year}/{end_year}"
        season_key = f"{start_year}_{end_year}"
        section_html = sm.group(3)

        matches_in_season = list(match_pattern.finditer(section_html))
        
        for mm in matches_in_season:
            href = mm.group(1).strip()
            desc = mm.group(2).strip()

            if href.lower().endswith('.pdf'):
                continue

            match_num_match = re.search(r'res\d+(\d)\.htm', href, re.IGNORECASE)
            if not match_num_match:
                match_num_match = re.search(r'^\s*(\d+)\s*\.', desc)
            match_num = int(match_num_match.group(1)) if match_num_match else 1

            # Parse venue and date from description (e.g. "11 October 2025 - Margam Park, Port Talbot")
            desc_clean = re.sub(r'^\s*\d+\.\s*&nbsp;\s*', '', desc).strip()
            date_part, venue_part = "", ""
            if " - " in desc_clean or " – " in desc_clean or " — " in desc_clean:
                parts = re.split(r'\s+[-–—]\s+', desc_clean, 1)
                date_part, venue_part = parts[0].strip(), parts[1].strip()
            else:
                date_match = re.match(r'^(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\s*(?:[-–—]\s*)?(.*)$', desc_clean)
                if date_match:
                    date_part, venue_part = date_match.group(1).strip(), date_match.group(2).strip()
                else:
                    venue_part = desc_clean

            # Full URL to the match hub
            hub_url = urllib.parse.urljoin(BASE_URL, href)
            print(f"\n[Season {season_str} Match {match_num}] {venue_part} ({date_part})")
            print(f"  Hub: {hub_url}")

            hub_html = fetch_url(hub_url)
            if not hub_html:
                continue

            # In the hub page, find links to Senior Men (smYYXi.htm) and Senior Women (slYYXi.htm)
            all_links = re.findall(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', hub_html, re.I)
            
            men_href = None
            women_href = None

            for l_href, l_text in all_links:
                clean_h = clean_url(l_href)
                # Senior Men individual is strictly sm{YY}{match}i.htm
                # E.g. sm251i.htm, sm101i.htm (sm followed by 3 digits then i.htm)
                if re.search(r'sm\d{3}i\.htm$', clean_h, re.I):
                    men_href = l_href
                # Senior Women individual is strictly sl{YY}{match}i.htm or sw{YY}{match}i.htm
                elif re.search(r'(sl|sw)\d{3}i\.htm$', clean_h, re.I):
                    women_href = l_href

            fixture_entry = {
                "season": season_str,
                "season_key": season_key,
                "match": match_num,
                "date": date_part,
                "venue": venue_part,
                "hub_url": hub_url,
                "men": None,
                "women": None
            }

            # Download & Cache Men Results
            if men_href:
                men_url = urllib.parse.urljoin(hub_url, men_href)
                men_filename = f"{season_key}_m{match_num}_men.htm"
                men_filepath = os.path.join(RAW_DIR, men_filename)
                
                if not os.path.exists(men_filepath) or force:
                    men_html = fetch_url(men_url)
                    if men_html:
                        with open(men_filepath, "w", encoding="utf-8") as f:
                            f.write(men_html)
                        print(f"    ✔ Cached Men -> {men_filename} ({len(men_html)} bytes)")
                else:
                    print(f"    - Men already cached -> {men_filename}")

                fixture_entry["men"] = {
                    "source_url": men_url,
                    "filename": men_filename,
                    "cached": os.path.exists(men_filepath)
                }

            # Download & Cache Women Results
            if women_href:
                women_url = urllib.parse.urljoin(hub_url, women_href)
                women_filename = f"{season_key}_m{match_num}_women.htm"
                women_filepath = os.path.join(RAW_DIR, women_filename)
                
                if not os.path.exists(women_filepath) or force:
                    women_html = fetch_url(women_url)
                    if women_html:
                        with open(women_filepath, "w", encoding="utf-8") as f:
                            f.write(women_html)
                        print(f"    ✔ Cached Women -> {women_filename} ({len(women_html)} bytes)")
                else:
                    print(f"    - Women already cached -> {women_filename}")

                fixture_entry["women"] = {
                    "source_url": women_url,
                    "filename": women_filename,
                    "cached": os.path.exists(women_filepath)
                }

            manifest.append(fixture_entry)
            time.sleep(0.1)  # Polite crawling delay

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    total_men = sum(1 for m in manifest if m["men"] and m["men"]["cached"])
    total_women = sum(1 for m in manifest if m["women"] and m["women"]["cached"])
    print("\n" + "=" * 60)
    print(f"SCRAPE COMPLETE!")
    print(f"Total fixtures catalogued: {len(manifest)}")
    print(f"Senior Men results cached: {total_men}")
    print(f"Senior Women results cached: {total_women}")
    print(f"Manifest written to: {MANIFEST_PATH}")
    print("=" * 60)

if __name__ == "__main__":
    run_scraper()
