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

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_DIV_DIR = os.path.join(SCRIPT_DIR, "raw_divisions")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "scrape_manifest.json")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "assets", "data", "team_standings.json")
OUTPUT_JS = os.path.join(PROJECT_DIR, "assets", "data", "team_standings.js")

os.makedirs(RAW_DIV_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

def fetch_file(url, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 200:
        with open(filepath, "r", encoding="latin-1", errors="replace") as f:
            return f.read()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            content = resp.read().decode("latin-1", errors="replace")
            with open(filepath, "w", encoding="latin-1", errors="replace") as f:
                f.write(content)
            return content
    except Exception as e:
        return None

def parse_division_html(html, gender, fixture_meta):
    results = []
    if not html:
        return results

    # Determine if HTML contains <table> or <pre>
    if "<table" in html.lower():
        # Table format
        # Split by division headers
        # Headers usually: <th>Senior Men Division X</th> or <h3>Senior Men Division X</h3>
        div_sections = re.split(r'(<(?:th|h[2-4])[^>]*>(?:Senior|Master|Vet|Reserve)[^<]*(?:Division|Teams)[^<]*</(?:th|h[2-4])>)', html, flags=re.I)
        
        current_div = "Division 1"
        for i in range(1, len(div_sections), 2):
            header_text = re.sub(r'<[^>]+>', '', div_sections[i]).strip()
            section_content = div_sections[i+1] if i+1 < len(div_sections) else ""
            
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', section_content, flags=re.I | re.DOTALL)
            standings = []
            for r in rows:
                cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.I | re.DOTALL)]
                if len(cols) >= 3 and (cols[0].isdigit() or re.match(r'^\d+=?$', cols[0])):
                    pos_str = cols[0].rstrip('=')
                    team_str = cols[1].replace('&nbsp;', ' ').strip()
                    pts_str = cols[2].replace('&nbsp;', '').strip()
                    
                    cum_pts = int(cols[3].replace('&nbsp;', '')) if len(cols) > 3 and cols[3].replace('&nbsp;', '').isdigit() else None
                    cum_pos = cols[4].replace('&nbsp;', ' ').strip() if len(cols) > 4 else None
                    
                    if pts_str.isdigit():
                        standings.append({
                            "pos": int(pos_str),
                            "team": team_str,
                            "pts": int(pts_str),
                            "cum_pts": cum_pts,
                            "cum_pos": cum_pos
                        })
            
            if standings:
                results.append({
                    "division": header_text,
                    "gender": gender,
                    "standings": standings
                })
    else:
        # Pre format
        sections = re.split(r'(<H[2-4]>[^<]+Division[^<]*</H[2-4]>)', html, flags=re.I)
        for i in range(1, len(sections), 2):
            header_text = re.sub(r'<[^>]+>', '', sections[i]).strip()
            section_content = sections[i+1] if i+1 < len(sections) else ""
            lines = section_content.split('\n')
            standings = []
            for line in lines:
                m = re.match(r'^\s*(\d+)=?\s+([A-Za-z0-9\s\.\'&/\-]+?)\s{2,}(\d+)(?:\s+(\d+))?(?:\s+([0-9=]+))?(?:\s+(.*))?$', line)
                if m:
                    pos = int(m.group(1))
                    team = m.group(2).strip()
                    pts = int(m.group(3))
                    cum_pts = int(m.group(4)) if m.group(4) else None
                    cum_pos = m.group(5) if m.group(5) else None
                    note = m.group(6).strip() if m.group(6) else None
                    standings.append({
                        "pos": pos,
                        "team": team,
                        "pts": pts,
                        "cum_pts": cum_pts,
                        "cum_pos": cum_pos,
                        "note": note
                    })
            if standings:
                results.append({
                    "division": header_text,
                    "gender": gender,
                    "standings": standings
                })

    return results

def run():
    print("=" * 60)
    print("Scraping and Parsing Gwent League Official Division Standings")
    print("=" * 60)
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    all_data = []

    for item in manifest:
        season = item["season"]
        season_key = item["season_key"]
        match_num = item["match"]
        venue = item["venue"]
        date = item["date"]
        hub_url = item["hub_url"]

        m = re.search(r'res(\d{2,3})(\d)\.htm', hub_url)
        if not m:
            continue
        yy, m_idx = m.group(1), m.group(2)
        base_url = hub_url.rsplit('/', 1)[0] + '/'

        fixture_res = {
            "season": season,
            "season_key": season_key,
            "match": match_num,
            "venue": venue,
            "date": date,
            "divisions": []
        }

        # Men division
        men_url = f"{base_url}sm{yy}{m_idx}d.htm"
        men_file = os.path.join(RAW_DIV_DIR, f"{season_key}_m{match_num}_men_div.htm")
        men_html = fetch_file(men_url, men_file)
        if men_html:
            men_divs = parse_division_html(men_html, "M", fixture_res)
            fixture_res["divisions"].extend(men_divs)

        # Women division (could be sl...d.htm or sw...d.htm)
        women_url = f"{base_url}sl{yy}{m_idx}d.htm"
        women_file = os.path.join(RAW_DIV_DIR, f"{season_key}_m{match_num}_women_div.htm")
        women_html = fetch_file(women_url, women_file)
        if not women_html:
            women_url = f"{base_url}sw{yy}{m_idx}d.htm"
            women_html = fetch_file(women_url, women_file)

        if women_html:
            women_divs = parse_division_html(women_html, "F", fixture_res)
            fixture_res["divisions"].extend(women_divs)

        div_count = len(fixture_res["divisions"])
        if div_count > 0:
            print(f"[{season} M{match_num}] {venue}: parsed {div_count} divisions")
            all_data.append(fixture_res)
        else:
            print(f"[{season} M{match_num}] {venue}: no division file found")
        time.sleep(0.05)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)

    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write("window.TEAM_STANDINGS = ")
        json.dump(all_data, f, indent=2)
        f.write(";\n")

    print(f"\nSaved {len(all_data)} fixtures with division data to:")
    print(f"  {OUTPUT_JSON}")
    print(f"  {OUTPUT_JS}")

if __name__ == "__main__":
    run()
