import json
import os
from collections import Counter
from bs4 import BeautifulSoup
import re

RAW_DIR = "/Users/robgale/Documents/gl-archive/backend_tools/raw_html"
MANIFEST_PATH = "/Users/robgale/Documents/gl-archive/backend_tools/scrape_manifest.json"
OUTPUT_PATH = "/Users/robgale/Documents/gl-archive/backend_tools/club_aliases.json"

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

raw_clubs = Counter()

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
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 4 and tds[0].get_text().strip().replace('*', '').isdigit():
                    raw_clubs[tds[3].get_text().strip()] += 1
        else:
            pre = soup.find("pre")
            if pre:
                for line in pre.get_text().split("\n"):
                    l = line.strip()
                    m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s+(\d+|Guest|guest|Disq\.?|-)?$', l)
                    if m:
                        mid = m.group(2).strip()
                        age_m = re.search(r'\s+\((\d{2})\)\s+', mid)
                        ind_m = re.search(r'\s+\(ind\)\s+', mid, re.I)
                        if age_m:
                            club = mid.split(age_m.group(0), 1)[1].strip()
                        elif ind_m:
                            club = mid.split(ind_m.group(0), 1)[1].strip()
                        else:
                            club = mid[25:].strip() if len(mid) > 25 else "Unattached"
                        raw_clubs[club] += 1

# Master alias rules
def canonicalize(raw):
    c = raw.strip()
    if not c or c in ["-", "Unknown", "Ind", "ind", "None"]:
        return "Unattached"
    
    cl = c.lower()
    
    # Parc Bryn Bach
    if "parc bryn bach" in cl or "pbb" in cl:
        return "Parc Bryn Bach Running Club"
    
    # Les Croupiers
    if "les croupiers" in cl:
        return "Les Croupiers Running Club"
    
    # Westbury
    if "westbury" in cl:
        return "Westbury Harriers"
    
    # Bristol & West
    if "bristol and west" in cl or "bristol & west" in cl:
        return "Bristol and West Athletic Club"
    
    # Cardiff AAC
    if "cardiff amateur" in cl or "cardiff aac" in cl:
        return "Cardiff Amateur Athletic Club"
    
    # Cardiff Met / UWIC
    if "cardiff metropolitan" in cl or "uwic" in cl or "wales inst. cardiff" in cl:
        return "Cardiff Metropolitan University"
        
    # Cardiff University (Harriers / AC)
    if "cardiff univ" in cl:
        return "Cardiff University AC"
    
    # Swansea Harriers
    if "swansea harriers" in cl:
        return "Swansea Harriers Athletic Club"
    
    # Swansea University
    if "swansea univ" in cl or "wales - swansea" in cl or "university of swansea" in cl:
        return "University of Swansea"
        
    # Lliswerry
    if "lliswerry" in cl:
        return "Lliswerry Runners"
        
    # Penarth and Dinas
    if "penarth" in cl and "dinas" in cl:
        return "Penarth and Dinas Runners"
        
    # Chepstow
    if "chepstow" in cl:
        return "Chepstow Harriers"
        
    # San Domenico
    if "san domenico" in cl:
        return "San Domenico Road Runners Club"
        
    # Bridgend
    if "bridgend" in cl:
        return "Bridgend Athletic Club"
        
    # Aberdare Valley
    if "aberdare" in cl:
        return "Aberdare Valley AAC"
        
    # Brecon
    if "brecon" in cl:
        return "Brecon Athletic Club"
        
    # Neath
    if "neath" in cl:
        return "Neath Harriers"
        
    # Great Western Runners
    if "great western" in cl:
        return "Great Western Runners"
        
    # Pontypridd Roadents / Athletic Club
    if "pontypridd roadents" in cl:
        return "Pontypridd Roadents Athletic Club"
    if "pontypridd" in cl:
        return "Pontypridd Roadents Athletic Club"
        
    # Pontypool / Pont-y-Pwl
    if "pont-y-pwl" in cl or "pontypool" in cl:
        return "Pont-y-Pwl & District Runners"
        
    # Wells City / Wells and Yeovil
    if "wells" in cl:
        return "Wells City Harriers"
        
    # Taf Running & Orienteering
    if "taf running" in cl or "trots" in cl:
        return "Taf Running & Orienteering Teams"
        
    # Port Talbot Harriers
    if "port talbot" in cl:
        return "Port Talbot Harriers & AC"
        
    # Islwyn
    if "islwyn" in cl:
        return "Islwyn Running Club"
        
    # 3M Gorseinon
    if "gorseinon" in cl or "3m" in cl:
        return "3M Gorseinon Road Runners"
        
    # Caldicot
    if "caldicot" in cl:
        return "Caldicot Running Club"
        
    # Forest of Dean
    if "forest of dean" in cl:
        return "Forest of Dean Athletic Club"
        
    # Llanelli
    if "llanelli" in cl:
        return "Llanelli Amateur Athletic Club"
        
    # Fairwater
    if "fairwater" in cl:
        return "Fairwater Runners"
        
    # Carmarthen
    if "carmarthen" in cl:
        return "Carmarthen & District Harriers AC"
        
    # Griffithstown
    if "griffithstown" in cl:
        return "Griffithstown Harriers AAC"
        
    # Caerleon
    if "caerleon" in cl:
        return "Caerleon RC"
        
    # Spirit of Monmouth
    if "spirit of monmouth" in cl or "monmouth" in cl and not "showground" in cl:
        return "Spirit of Monmouth RC"
        
    # Clevedon
    if "clevedon" in cl:
        return "Clevedon AC"
        
    # CDF Runners
    if "cdf" in cl:
        return "CDF Runners"
        
    # Rhondda Valley Runners / Rhondda AC
    if "rhondda valley" in cl:
        return "Rhondda Valley Runners"
    if "rhondda" in cl:
        return "Rhondda AC"

    # Micky Morris
    if "micky morris" in cl:
        return "Micky Morris Racing Team"
        
    # Builth & District
    if "builth" in cl:
        return "Builth & District RC"
        
    # Amman Valley
    if "amman valley" in cl:
        return "Amman Valley Harriers"
        
    # Pembrokeshire
    if "pembrokeshire" in cl:
        return "Pembrokeshire Harriers"
        
    # Stroud
    if "stroud" in cl:
        return "Stroud & District Athletic Club"
        
    # North Somerset
    if "north somerset" in cl:
        return "North Somerset AC"
        
    # Pegasus
    if "pegasus" in cl:
        return "Pegasus Running Club Cardiff"
        
    # Pontyclun
    if "pontyclun" in cl:
        return "Pontyclun Road Runners"
        
    # Somer AC
    if "somer" in cl:
        return "Somer Athletic Club"
        
    # White Rock
    if "white rock" in cl:
        return "White Rock Runners"

    return c

aliases = {}
for raw, count in raw_clubs.most_common():
    aliases[raw] = canonicalize(raw)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(aliases, f, indent=2, sort_keys=True)

print(f"Generated {len(aliases)} club mappings in {OUTPUT_PATH}")
