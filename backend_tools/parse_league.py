import os
import re
import json
from collections import defaultdict
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(SCRIPT_DIR, "raw_html")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "scrape_manifest.json")
CLUB_ALIASES_PATH = os.path.join(SCRIPT_DIR, "club_aliases.json")
CORRECTIONS_PATH = os.path.join(SCRIPT_DIR, "corrections.json")
DATA_JS_PATH = os.path.join(PROJECT_ROOT, "data.js")
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "data.json")
RUNNERS_SUMMARY_PATH = os.path.join(SCRIPT_DIR, "runners_summary.json")

# Load Club Aliases
club_aliases = {}
if os.path.exists(CLUB_ALIASES_PATH):
    with open(CLUB_ALIASES_PATH, "r", encoding="utf-8") as f:
        club_aliases = json.load(f)

# Load Athlete Corrections/Aliases if present
athlete_corrections = {}
if os.path.exists(CORRECTIONS_PATH):
    with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
        athlete_corrections = json.load(f)

def format_time(t_str):
    if not t_str:
        return ""
    clean = t_str.strip().replace('.', ':')
    parts = clean.split(':')
    if len(parts) == 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    elif len(parts) == 3:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    return clean

def normalize_age_category(raw_age_bracket):
    if not raw_age_bracket:
        return "Senior", "Senior"
    
    digits = re.findall(r'\d+', raw_age_bracket)
    if not digits:
        return "Senior", "Senior"
    
    age_num = int(digits[0])
    if age_num == 23:
        return "U23", "Senior"
    
    cat_code = f"V{age_num}"
    
    # Bucket into 35, 45, 55, 65 groups
    if age_num in [35, 40]:
        group = "35"
    elif age_num in [45, 50]:
        group = "45"
    elif age_num in [55, 60]:
        group = "55"
    elif age_num >= 65:
        group = "65"
    else:
        group = "Senior"
        
    return cat_code, group

def parse_modern_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tblIndividualPoints") or soup.find("table")
    if not table:
        return []

    results = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds or len(tds) < 4:
            continue
        
        cells = [td.get_text().strip() for td in tds]
        pos_raw = cells[0].replace('*', '').strip()
        if not pos_raw.isdigit():
            continue
        
        pos = int(pos_raw)
        raw_name = cells[1] if len(cells) > 1 else ""
        age_tag = cells[2] if len(cells) > 2 else ""
        raw_club = cells[3] if len(cells) > 3 else ""
        time_str = cells[4] if len(cells) > 4 else ""
        pts_str = cells[5] if len(cells) > 5 else "0"

        # Check guest/ind in name or club
        is_guest = False
        if "(ind)" in raw_name.lower() or "guest" in raw_club.lower() or "guest" in pts_str.lower():
            is_guest = True
            raw_name = re.sub(r'\(ind\)', '', raw_name, flags=re.I).strip()

        points = int(pts_str) if pts_str.isdigit() else 0

        cat_code, cat_group = normalize_age_category(age_tag)

        results.append({
            "pos": pos,
            "raw_name": raw_name.strip(),
            "age_tag": age_tag.strip(),
            "cat_code": cat_code,
            "cat_group": cat_group,
            "raw_club": raw_club.strip(),
            "time": format_time(time_str),
            "points": points,
            "is_guest": is_guest
        })

    return results

def parse_legacy_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    if not pre:
        return []

    lines = pre.get_text().split("\n")
    results = []

    for line in lines:
        l = line.strip()
        if not l or l.startswith("Pos") or "Starters" in l or "---" in l or "Senior" in l or "League" in l or "==" in l or "Final Results" in l:
            continue

        m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s+(\d+|Guest|guest|Disq\.?|-)?$', l)
        if not m:
            continue

        pos = int(m.group(1))
        middle = m.group(2).strip()
        time_str = m.group(3).strip()
        pts_str = m.group(4) or "0"

        is_guest = False
        if "(ind)" in middle.lower() or "guest" in pts_str.lower() or "guest" in middle.lower():
            is_guest = True

        age_m = re.search(r'\s+\((\d{2})\)\s+', middle)
        ind_m = re.search(r'\s+\(ind\)\s+', middle, re.I)

        age_tag = ""
        if age_m:
            age_tag = f"({age_m.group(1)})"
            parts = middle.split(age_m.group(0), 1)
            raw_name = parts[0].strip()
            raw_club = parts[1].strip()
        elif ind_m:
            parts = middle.split(ind_m.group(0), 1)
            raw_name = parts[0].strip()
            raw_club = parts[1].strip()
        else:
            raw_name = middle[:25].strip()
            raw_club = middle[25:].strip() if len(middle) > 25 else "Unattached"

        raw_name = re.sub(r'\(ind\)', '', raw_name, flags=re.I).strip()
        points = int(pts_str) if pts_str.isdigit() else 0
        cat_code, cat_group = normalize_age_category(age_tag)

        results.append({
            "pos": pos,
            "raw_name": raw_name.strip(),
            "age_tag": age_tag.strip(),
            "cat_code": cat_code,
            "cat_group": cat_group,
            "raw_club": raw_club.strip(),
            "time": format_time(time_str),
            "points": points,
            "is_guest": is_guest
        })

    return results

def compile_database():
    print("=" * 60)
    print("Compiling Master Gwent League Database (2010 to 2026)")
    print("=" * 60)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_records = []
    runners_summary = defaultdict(lambda: {
        "canonical_name": "",
        "raw_names": set(),
        "clubs": set(),
        "seasons": set(),
        "gender": set(),
        "categories": set(),
        "finishes": 0,
        "first_year": 9999,
        "last_year": 0
    })

    for fixture in manifest:
        season = fixture["season"]
        season_key = fixture["season_key"]
        match_num = fixture["match"]
        venue = fixture["venue"]
        date = fixture["date"]

        # Ensure date and venue are clean if fused together
        if not date and venue:
            date_match = re.match(r'^(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4})\s*(?:[-–—]\s*)?(.*)$', venue)
            if date_match:
                date = date_match.group(1).strip()
                venue = date_match.group(2).strip() or "Chepstow Racecourse"

        yr_start = int(season.split('/')[0])

        for gender_key, sex_label in [("men", "M"), ("women", "F")]:
            info = fixture.get(gender_key)
            if not info or not info.get("filename"):
                continue

            filepath = os.path.join(RAW_DIR, info["filename"])
            if not os.path.exists(filepath):
                continue

            # Auto-detect era
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                head_chunk = f.read(1500)

            is_table = "<table" in head_chunk.lower()
            if is_table:
                parsed_rows = parse_modern_file(filepath)
            else:
                parsed_rows = parse_legacy_file(filepath)

            # Compute category positions within this race
            cat_counters = defaultdict(int)

            for row in parsed_rows:
                raw_name = row["raw_name"]
                canonical_club = club_aliases.get(row["raw_club"], row["raw_club"])

                # Check alias mapping: gender-and-club first, then club-only, then global
                # Try exact, with-dot, and without-dot forms
                raw_variants = [raw_name]
                parts = raw_name.split()
                if len(parts) >= 2 and len(parts[0].replace('.', '')) == 1:
                    init = parts[0].replace('.', '').upper()
                    rest = " ".join(parts[1:])
                    raw_variants.append(f"{init}. {rest}")
                    raw_variants.append(f"{init} {rest}")

                canonical_name = raw_name
                for variant in raw_variants:
                    gender_club_key = f"{variant} [{sex_label}, {canonical_club}]"
                    club_key = f"{variant} [{canonical_club}]"
                    if gender_club_key in athlete_corrections:
                        canonical_name = athlete_corrections[gender_club_key]
                        break
                    elif club_key in athlete_corrections:
                        canonical_name = athlete_corrections[club_key]
                        break
                    elif variant in athlete_corrections:
                        canonical_name = athlete_corrections[variant]
                        break

                # Transitive alias resolution (e.g. A. Blair -> Andy Blair -> Andrew Blair)
                for _ in range(3):
                    next_name = None
                    for key in [f"{canonical_name} [{sex_label}, {canonical_club}]", f"{canonical_name} [{canonical_club}]", canonical_name]:
                        if key in athlete_corrections and athlete_corrections[key] != canonical_name:
                            next_name = athlete_corrections[key]
                            break
                    if next_name:
                        canonical_name = next_name
                    else:
                        break

                cat_code = row["cat_code"]
                cat_counters[cat_code] += 1
                cat_pos = cat_counters[cat_code]

                record_id = f"{season_key}_m{match_num}_{sex_label.lower()}_{row['pos']}"

                record = {
                    "id": record_id,
                    "season": season,
                    "season_key": season_key,
                    "match": match_num,
                    "venue": venue,
                    "date": date,
                    "gender": sex_label,
                    "pos": row["pos"],
                    "athlete": canonical_name,
                    "raw_name": raw_name,
                    "age_cat": cat_code,
                    "cat_group": row["cat_group"],
                    "cat_pos": cat_pos,
                    "club": canonical_club,
                    "raw_club": row["raw_club"],
                    "time": row["time"],
                    "pts": row["points"],
                    "is_guest": row["is_guest"]
                }
                all_records.append(record)

                # Track in runner summary
                r_key = canonical_name.lower()
                r_sum = runners_summary[r_key]
                r_sum["canonical_name"] = canonical_name
                r_sum["raw_names"].add(raw_name)
                r_sum["clubs"].add(canonical_club)
                r_sum["seasons"].add(season)
                r_sum["gender"].add(sex_label)
                r_sum["categories"].add(cat_code)
                r_sum["finishes"] += 1
                if yr_start < r_sum["first_year"]:
                    r_sum["first_year"] = yr_start
                if yr_start > r_sum["last_year"]:
                    r_sum["last_year"] = yr_start

    # Sort all records: Season descending, Match ascending, Gender M then F, Pos ascending
    all_records.sort(key=lambda r: (
        -int(r["season_key"].split('_')[0]),
        r["match"],
        0 if r["gender"] == "M" else 1,
        r["pos"]
    ))

    # Convert sets to sorted lists in runners_summary
    serializable_summary = {}
    for k, v in runners_summary.items():
        serializable_summary[k] = {
            "canonical_name": v["canonical_name"],
            "raw_names": sorted(list(v["raw_names"])),
            "clubs": sorted(list(v["clubs"])),
            "seasons": sorted(list(v["seasons"])),
            "gender": list(v["gender"])[0] if v["gender"] else "M",
            "categories": sorted(list(v["categories"])),
            "finishes": v["finishes"],
            "first_year": v["first_year"],
            "last_year": v["last_year"]
        }

    # Write data.js (for frontend static site)
    print(f"Writing {len(all_records)} records to {DATA_JS_PATH}...")
    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated master dataset for Gwent League Archive\n")
        f.write(f"window.glResults = {json.dumps(all_records)};\n")

    # Write data.json
    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f)

    # Write runners summary for alias generation tool
    with open(RUNNERS_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(serializable_summary, f, indent=2)

    # Trigger club transfer detection
    try:
        from detect_transfers import analyze_transfers
        analyze_transfers()
    except Exception as e:
        print(f"Transfer detection hook note: {e}")

    print("\n" + "=" * 60)
    print("BUILD SUCCESSFUL!")
    print(f"Total Finish Records: {len(all_records)}")
    print(f"Total Unique Runners: {len(serializable_summary)}")
    print(f"Generated: data.js ({round(os.path.getsize(DATA_JS_PATH) / 1024 / 1024, 2)} MB)")
    print(f"Generated: data.json ({round(os.path.getsize(DATA_JSON_PATH) / 1024 / 1024, 2)} MB)")
    print(f"Generated: runners_summary.json")
    print("=" * 60)

if __name__ == "__main__":
    compile_database()
