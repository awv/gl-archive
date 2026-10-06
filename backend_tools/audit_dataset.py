import os
import re
import json
from collections import Counter
from bs4 import BeautifulSoup

RAW_DIR = "/Users/robgale/Documents/gl-archive/backend_tools/raw_html"
MANIFEST_PATH = "/Users/robgale/Documents/gl-archive/backend_tools/scrape_manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

raw_clubs = Counter()
total_finishers = 0
unparsed_lines = 0

for fixture in manifest:
    for gender_key in ["men", "women"]:
        info = fixture.get(gender_key)
        if not info or not info.get("filename"):
            continue
        
        filepath = os.path.join(RAW_DIR, info["filename"])
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="tblIndividualPoints") or soup.find("table")
        
        if table:
            # Table parser
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if not tds or len(tds) < 4:
                    continue
                cells = [td.get_text().strip() for td in tds]
                pos_raw = cells[0].replace('*', '').strip()
                if not pos_raw.isdigit():
                    continue
                
                club = cells[3]
                raw_clubs[club] += 1
                total_finishers += 1
        else:
            # Pre parser
            pre = soup.find("pre")
            if pre:
                lines = pre.get_text().split("\n")
                for line in lines:
                    line_clean = line.strip()
                    if not line_clean or line_clean.startswith("Pos") or "Starters" in line_clean or "---" in line_clean:
                        continue
                    m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s+(\d+|Guest|guest|-)?$', line_clean)
                    if m:
                        middle = m.group(2).strip()
                        age_m = re.search(r'\s+\((\d{2})\)\s+', middle)
                        ind_m = re.search(r'\s+\(ind\)\s+', middle, re.I)
                        if age_m:
                            club = middle.split(age_m.group(0), 1)[1].strip()
                        elif ind_m:
                            club = middle.split(ind_m.group(0), 1)[1].strip()
                        else:
                            club = middle[25:].strip() if len(middle) > 25 else "Unattached"
                        raw_clubs[club] += 1
                        total_finishers += 1
                    else:
                        unparsed_lines += 1

print(f"Total Finishers parsed across 2010-2026: {total_finishers}")
print(f"Total Unique Raw Club strings: {len(raw_clubs)}")
print(f"Unparsed lines: {unparsed_lines}")
print("\nTop 30 Clubs by participation:")
for club, count in raw_clubs.most_common(30):
    print(f"  {club:<45} : {count} finishes")
