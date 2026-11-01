import json
import os
import re
from collections import defaultdict
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_HTML_DIR = os.path.join(SCRIPT_DIR, "raw_html")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "scrape_manifest.json")
OUTPUT_AUDIT_JSON = os.path.join(SCRIPT_DIR, "athlete_similarity_audit.json")
OUTPUT_AUDIT_JS = os.path.join(SCRIPT_DIR, "athlete_similarity_audit.js")

def parse_time_to_seconds(t_str):
    if not t_str:
        return None
    t_clean = t_str.strip().replace(':', '.')
    parts = t_clean.split('.')
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        return None
    return None

def parse_age_numeric(cat, year):
    if not cat:
        return 28 # Default senior age estimate
    if "U23" in cat or "23" in cat:
        return 22
    if "Senior" in cat:
        return 28
    nums = re.findall(r'\d+', cat)
    if nums:
        return int(nums[0])
    return 28

def parse_raw_file(filepath, gender, season, match, season_key):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    if not pre:
        return []

    lines = pre.get_text().split("\n")
    records = []

    # Count total starters in pre
    total_starters = 0
    for l in lines:
        if re.match(r'^\*?\s*(\d+)\s+', l.strip()):
            total_starters += 1

    total_starters = max(total_starters, 50)

    for line in lines:
        l = line.strip()
        if not l or l.startswith("Pos") or "Starters" in l or "Senior" in l or "League" in l or "---" in l:
            continue
        m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s*(\d+|Guest|guest|Disq\.?|-)?$', l)
        if not m:
            continue

        pos = int(m.group(1))
        mid = m.group(2).strip()
        time_str = m.group(3).strip()

        # Age category in parentheses (e.g. (40), (23))
        cat = "Senior"
        cat_match = re.search(r'\(([^)]+)\)', mid)
        if cat_match:
            cat_tag = cat_match.group(1).strip()
            cat = f"V{cat_tag}" if cat_tag.isdigit() and int(cat_tag) >= 35 else ("U23" if cat_tag == "23" else cat_tag)
            mid = re.sub(r'\([^)]+\)', '', mid).strip()

        # Split name and club
        mid_parts = re.split(r'\s{2,}', mid, maxsplit=1)
        raw_name = mid_parts[0].strip() if len(mid_parts) > 0 else mid
        raw_club = mid_parts[1].strip() if len(mid_parts) > 1 else ""

        # Remove (ind) or guest notes
        raw_name = re.sub(r'\(ind\)', '', raw_name, flags=re.I).strip()

        percentile = round((pos / total_starters) * 100, 1)

        year = int(season_key.split('_')[0])
        est_age = parse_age_numeric(cat, year)

        records.append({
            "season": season,
            "season_key": season_key,
            "match": match,
            "year": year,
            "gender": gender,
            "pos": pos,
            "athlete": raw_name,
            "age_cat": cat,
            "est_age": est_age,
            "club": raw_club,
            "time": time_str,
            "time_sec": parse_time_to_seconds(time_str),
            "percentile": percentile
        })

    return records

def compute_similarity(cand_a, cand_b):
    # Returns score between 0 and 100, and explanation factors
    # cand_a and cand_b are profile dicts of runner careers
    
    # 1. Gender gatekeeper
    if cand_a["gender"] != cand_b["gender"]:
        return 0, "Gender mismatch (0% match)"

    # 2. Race Concurrency check: Did they ever run in the exact same fixture under different identities?
    fixtures_a = set(cand_a["fixtures"])
    fixtures_b = set(cand_b["fixtures"])
    overlap_fixtures = fixtures_a.intersection(fixtures_b)
    if len(overlap_fixtures) > 0:
        return 0, f"Disqualified: Competed concurrently in the same fixture ({len(overlap_fixtures)} overlaps)"

    score = 0
    reasons = []

    # 3. Name Similarity (max 35 pts)
    name_a = cand_a["name"].lower().strip()
    name_b = cand_b["name"].lower().strip()
    
    surname_a = name_a.split()[-1] if name_a else ""
    surname_b = name_b.split()[-1] if name_b else ""
    first_a = name_a.split()[0].replace('.', '') if name_a else ""
    first_b = name_b.split()[0].replace('.', '') if name_b else ""

    if surname_a == surname_b:
        if name_a == name_b:
            score += 35
            reasons.append("Identical name match (+35)")
        elif first_a == first_b:
            score += 33
            reasons.append("Identical first token & surname (+33)")
        elif (len(first_a) == 1 and first_b.startswith(first_a)) or (len(first_b) == 1 and first_a.startswith(first_b)):
            score += 30
            reasons.append(f"Initial-to-full name match ({first_a} <-> {first_b}) (+30)")
        else:
            # Surnames match but completely different first names (e.g., David Evans vs Huw Evans)
            return 0, f"Different first names ({first_a} vs {first_b}) despite common surname"
    else:
        # Check maiden name / typo
        return 0, f"Different surnames ({surname_a} vs {surname_b})"

    # 4. Age Trajectory Consistency (max 25 pts)
    # Check if age progression makes biological sense across calendar years
    min_yr_a, max_yr_a = cand_a["min_year"], cand_a["max_year"]
    min_yr_b, max_yr_b = cand_b["min_year"], cand_b["max_year"]
    age_a = cand_a["median_est_age"]
    age_b = cand_b["median_est_age"]
    yr_diff = (cand_b["median_year"] - cand_a["median_year"])
    expected_age_b = age_a + yr_diff

    age_delta = abs(expected_age_b - age_b)

    if age_delta <= 3:
        score += 25
        reasons.append(f"Flawless biological age trajectory (delta: {age_delta} yrs) (+25)")
    elif age_delta <= 6:
        score += 15
        reasons.append(f"Consistent age trajectory (delta: {age_delta} yrs) (+15)")
    elif age_delta > 10:
        return 0, f"Biologically impossible age difference (expected age: {expected_age_b}, observed: {age_b})"

    # 5. Performance / Percentile Signature Correlation (max 20 pts)
    pct_a = cand_a["avg_percentile"]
    pct_b = cand_b["avg_percentile"]
    pct_diff = abs(pct_a - pct_b)

    if pct_diff <= 5:
        score += 20
        reasons.append(f"Nearly identical race finishing percentile ({pct_a}% vs {pct_b}%) (+20)")
    elif pct_diff <= 12:
        score += 15
        reasons.append(f"Strong speed profile correlation ({pct_a}% vs {pct_b}%) (+15)")
    elif pct_diff <= 25:
        score += 8
        reasons.append(f"Moderate pace similarity ({pct_a}% vs {pct_b}%) (+8)")
    else:
        reasons.append(f"Divergent pace signature ({pct_a}% vs {pct_b}%) (+0)")

    # 6. Temporal Career Continuity / Transfer Gap (max 20 pts)
    # Check if careers sequence naturally (e.g. Club A runs until 2007, Club B starts 2008)
    career_gap = min_yr_b - max_yr_a if min_yr_b >= max_yr_a else min_yr_a - max_yr_b
    if 0 <= career_gap <= 2:
        score += 20
        reasons.append(f"Seamless club career handover (gap: {career_gap} yrs) (+20)")
    elif career_gap <= 5:
        score += 12
        reasons.append(f"Plausible club transfer window (gap: {career_gap} yrs) (+12)")
    else:
        score += 5
        reasons.append(f"Extended multi-year gap ({career_gap} yrs) (+5)")

    return min(score, 100), "; ".join(reasons)

def main():
    print("=" * 60)
    print("Athlete Disambiguation & Probabilistic Similarity Audit")
    print("=" * 60)

    # 1. Load 2000-2010 raw HTML files
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    all_records = []
    print(f"Loading manifest of {len(manifest)} fixtures...")

    for fix in manifest:
        season = fix["season"]
        season_key = fix["season_key"]
        match = fix["match"]

        # Men
        men_file = os.path.join(RAW_HTML_DIR, fix["men"]["filename"])
        all_records.extend(parse_raw_file(men_file, "M", season, match, season_key))

        # Women
        women_file = os.path.join(RAW_HTML_DIR, fix["women"]["filename"])
        all_records.extend(parse_raw_file(women_file, "F", season, match, season_key))

    print(f"Total finishes parsed across all fixtures: {len(all_records):,}")

    # Group into athlete profiles by (name, club, gender)
    profiles = {}
    grouped = defaultdict(list)
    for r in all_records:
        name = r["athlete"].strip()
        club = r["club"].strip()
        gender = r["gender"]
        if not name or len(name) < 2 or not club:
            continue
        grouped[(name, club, gender)].append(r)

    print(f"Generated {len(grouped):,} unique (Athlete, Club, Gender) entities.")

    entity_list = []
    for (name, club, gender), recs in grouped.items():
        years = [r["year"] for r in recs]
        percentiles = [r["percentile"] for r in recs]
        est_ages = [r["est_age"] for r in recs]
        fixtures = [f"{r['season_key']}_m{r['match']}" for r in recs]

        entity_list.append({
            "name": name,
            "club": club,
            "gender": gender,
            "count": len(recs),
            "min_year": min(years),
            "max_year": max(years),
            "median_year": round(sum(years) / len(years)),
            "avg_percentile": round(sum(percentiles) / len(percentiles), 1),
            "median_est_age": round(sum(est_ages) / len(est_ages)),
            "fixtures": fixtures,
            "categories": sorted(list(set(r["age_cat"] for r in recs)))
        })

    # Group entities by surname & gender for pairwise candidate analysis
    by_surname = defaultdict(list)
    for ent in entity_list:
        surname = ent["name"].split()[-1].lower()
        by_surname[(surname, ent["gender"])].append(ent)

    candidate_comparisons = []

    for (surname, gender), ents in by_surname.items():
        if len(ents) < 2:
            continue
        
        # Compare all pairs within this surname
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                ent_a, ent_b = ents[i], ents[j]

                # If same club and exact same name, it's the same record
                if ent_a["name"] == ent_b["name"] and ent_a["club"] == ent_b["club"]:
                    continue

                # Ensure chronological order (A earlier than B)
                if ent_a["median_year"] > ent_b["median_year"]:
                    ent_a, ent_b = ent_b, ent_a

                prob, explanation = compute_similarity(ent_a, ent_b)

                if prob >= 40:
                    candidate_comparisons.append({
                        "athlete_a": ent_a["name"],
                        "club_a": ent_a["club"],
                        "years_a": f"{ent_a['min_year']}–{ent_a['max_year']} ({ent_a['count']} races)",
                        "cats_a": ent_a["categories"],
                        "pct_a": ent_a["avg_percentile"],
                        "athlete_b": ent_b["name"],
                        "club_b": ent_b["club"],
                        "years_b": f"{ent_b['min_year']}–{ent_b['max_year']} ({ent_b['count']} races)",
                        "cats_b": ent_b["categories"],
                        "pct_b": ent_b["avg_percentile"],
                        "gender": gender,
                        "confidence_percentage": prob,
                        "confidence_tier": "Very High" if prob >= 90 else ("High" if prob >= 80 else ("Moderate" if prob >= 65 else "Low")),
                        "analysis": explanation
                    })

    candidate_comparisons.sort(key=lambda x: -x["confidence_percentage"])
    print(f"Identified {len(candidate_comparisons)} pairwise candidate comparisons (&ge;40%).")

    # Output top candidates
    print("\n" + "=" * 60)
    print("SAMPLE HIGH-CONFIDENCE MATCHES:")
    print("=" * 60)
    for c in candidate_comparisons[:15]:
        print(f"[{c['confidence_percentage']}%] {c['athlete_a']} ({c['club_a']}) <-> {c['athlete_b']} ({c['club_b']})")
        print(f"      Factors: {c['analysis']}")

    with open(OUTPUT_AUDIT_JSON, "w") as f:
        json.dump(candidate_comparisons, f, indent=2)

    with open(OUTPUT_AUDIT_JS, "w") as f:
        f.write("window.glAthleteSimilarityAudit = " + json.dumps(candidate_comparisons, indent=2) + ";\n")

    print(f"\nSaved audit report to {OUTPUT_AUDIT_JSON}")

if __name__ == "__main__":
    main()
