import os
import re
import json
from bs4 import BeautifulSoup

RAW_DIR = "/Users/robgale/Documents/gl-archive/backend_tools/raw_html"
MANIFEST_PATH = "/Users/robgale/Documents/gl-archive/backend_tools/scrape_manifest.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

unparsed_samples = []

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
        if not table:
            pre = soup.find("pre")
            if pre:
                for line in pre.get_text().split("\n"):
                    l = line.strip()
                    if not l or l.startswith("Pos") or "Starters" in l or "---" in l or "Final Results" in l or "Senior" in l or "October" in l or "November" in l or "December" in l or "January" in l or "February" in l or "March" in l or "League" in l or "==" in l:
                        continue
                    m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s+(\d+|Guest|guest|-)?$', l)
                    if not m:
                        unparsed_samples.append((info["filename"], l))

print(f"Total unparsed lines found: {len(unparsed_samples)}")
for fn, l in unparsed_samples[:25]:
    print(f"  [{fn}] {l}")
