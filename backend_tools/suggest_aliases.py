import json
import os
import re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "data.json")
CANDIDATES_PATH = os.path.join(SCRIPT_DIR, "alias_candidates.json")
CANDIDATES_JS_PATH = os.path.join(SCRIPT_DIR, "alias_candidates.js")
EXISTING_CORRECTIONS_PATH = os.path.join(SCRIPT_DIR, "corrections.json")

# 1. Load Existing Corrections
existing_approved = {}
if os.path.exists(EXISTING_CORRECTIONS_PATH):
    try:
        with open(EXISTING_CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            existing_approved = json.load(f)
    except Exception:
        pass

# 2. Load Master Finish Records
print(f"Loading master database from {DATA_JSON_PATH}...")
with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
    all_records = json.load(f)

# Helper: Compute rich statistics for a list of race finishes
def compute_stats(name, club, records):
    if not records:
        return {
            "name": name,
            "club": club or "Unknown",
            "finishes": 0,
            "seasons": [],
            "years_span": "None",
            "categories": [],
            "avg_pos": 0,
            "best_pos": 0,
            "avg_cat_pos": 0,
            "best_cat_pos": 0,
            "first_year": 9999,
            "last_year": 0
        }
    positions = [r["pos"] for r in records if r.get("pos", 0) > 0]
    cat_positions = [r["cat_pos"] for r in records if r.get("cat_pos", 0) > 0]
    seasons = sorted(list(set(r["season"] for r in records)))
    cats = sorted(list(set(r["age_cat"] for r in records)))
    first_yr = min(int(s.split("/")[0]) for s in seasons)
    last_yr = max(int(s.split("/")[0]) for s in seasons)
    
    return {
        "name": name,
        "club": club,
        "finishes": len(records),
        "seasons": seasons,
        "years_span": f"{first_yr}–{last_yr + 1} ({len(seasons)} {'season' if len(seasons) == 1 else 'seasons'})",
        "categories": cats,
        "avg_pos": round(sum(positions) / len(positions), 1) if positions else 0,
        "best_pos": min(positions) if positions else 0,
        "avg_cat_pos": round(sum(cat_positions) / len(cat_positions), 1) if cat_positions else 0,
        "best_cat_pos": min(cat_positions) if cat_positions else 0,
        "first_year": first_yr,
        "last_year": last_yr
    }

# Helper: Calculate match probability & forensic reasons
def calculate_match_probability(leg_stats, mod_stats, shared_club, gender_match):
    if not gender_match:
        return 0, ["Gender mismatch"]
    
    score = 50.0
    reasons = []

    # 1. Club match
    if shared_club:
        score += 35.0
        reasons.append(f"Direct club match: {shared_club}")
    else:
        score -= 25.0
        reasons.append("Different clubs")

    # 2. Finishing Position / Pace Similarity
    if leg_stats["avg_pos"] > 0 and mod_stats["avg_pos"] > 0:
        pos_diff = abs(leg_stats["avg_pos"] - mod_stats["avg_pos"])
        if pos_diff <= 25:
            score += 15.0
            reasons.append(f"Close pace match (Avg pos {leg_stats['avg_pos']} vs {mod_stats['avg_pos']})")
        elif pos_diff <= 60:
            score += 10.0
            reasons.append(f"Consistent standard (Avg pos {leg_stats['avg_pos']} vs {mod_stats['avg_pos']})")
        elif pos_diff <= 100:
            score += 5.0
        elif pos_diff > 160:
            score -= 20.0
            reasons.append(f"Significant pace divergence (Avg pos {leg_stats['avg_pos']} vs {mod_stats['avg_pos']})")

    # 3. Category Position Similarity
    if leg_stats["avg_cat_pos"] > 0 and mod_stats["avg_cat_pos"] > 0:
        cat_diff = abs(leg_stats["avg_cat_pos"] - mod_stats["avg_cat_pos"])
        if cat_diff <= 5:
            score += 8.0
            reasons.append(f"Category standard alignment (Avg #{leg_stats['avg_cat_pos']} vs #{mod_stats['avg_cat_pos']})")
        elif cat_diff <= 12:
            score += 4.0

    # 4. Age Progression & Category Coherence
    def parse_age(cat):
        if "U23" in cat: return 22
        if "Senior" in cat: return 28
        nums = re.findall(r'\d+', cat)
        return int(nums[0]) if nums else 28

    leg_ages = [parse_age(c) for c in leg_stats["categories"]]
    mod_ages = [parse_age(c) for c in mod_stats["categories"]]

    if leg_ages and mod_ages:
        max_leg_age = max(leg_ages)
        min_mod_age = min(mod_ages)
        if min_mod_age >= max_leg_age:
            score += 12.0
            reasons.append(f"Age trajectory verified ({'/'.join(leg_stats['categories'])} ➔ {'/'.join(mod_stats['categories'])})")
        elif min_mod_age < max_leg_age - 5:
            score -= 35.0
            reasons.append(f"Age regression flag ({'/'.join(leg_stats['categories'])} vs {'/'.join(mod_stats['categories'])})")

    # 5. Era Timeline Handover
    if leg_stats["last_year"] <= 2022 and mod_stats["first_year"] >= 2021:
        score += 8.0
        reasons.append(f"Era transition ({leg_stats['years_span'].split()[0]} ➔ {mod_stats['years_span'].split()[0]})")

    # 6. Sample Size
    if leg_stats["finishes"] >= 3 and mod_stats["finishes"] >= 3:
        score += 4.0
        reasons.append(f"Strong race record ({leg_stats['finishes']} legacy + {mod_stats['finishes']} modern finishes)")

    final_score = int(min(max(score, 5.0), 99.0))
    return final_score, reasons

# 3. Group records by runner entities
# Abbreviated entities: key = (raw_name, club, gender)
# Full name entities: key = (athlete_name, club, gender)
abbr_records_map = defaultdict(list)
full_records_map = defaultdict(list)

for r in all_records:
    raw = r.get("raw_name", "").strip()
    if not raw or "unknown" in raw.lower() or raw in ["-", "N/A"]:
        continue
    
    parts = raw.split()
    if len(parts) >= 2:
        first_token = parts[0].replace('.', '')
        is_initial = (len(first_token) == 1 and first_token.isalpha())
        
        club = r["club"]
        gender = r["gender"]
        
        if is_initial:
            abbr_records_map[(raw, club, gender)].append(r)
        else:
            full_records_map[(raw, club, gender)].append(r)

print(f"Abbreviated runner entities (club/gender scoped): {len(abbr_records_map)}")
print(f"Full-name runner entities (club/gender scoped): {len(full_records_map)}")

# Index full runners by (surname_lower, initial_upper, gender)
full_index = defaultdict(list)
for (full_name, club, gender), recs in full_records_map.items():
    parts = full_name.split()
    initial = parts[0][0].upper()
    surname = " ".join(parts[1:]).lower()
    full_stats = compute_stats(full_name, club, recs)
    full_index[(surname, initial, gender)].append(full_stats)

candidates = []
seen_candidates = set()

for (abbr_name, club, gender), recs in abbr_records_map.items():
    parts = abbr_name.split()
    initial = parts[0].replace('.', '').upper()
    surname = " ".join(parts[1:]).lower()
    
    key = (surname, initial, gender)
    potential_matches = full_index.get(key, [])
    if not potential_matches:
        continue
    
    leg_stats = compute_stats(abbr_name, club, recs)
    lookup_key = f"{abbr_name} [{club}]"
    
    for mod_stats in potential_matches:
        mod_name = mod_stats["name"]
        mod_club = mod_stats["club"]
        
        cand_pair_key = (lookup_key, mod_name)
        if cand_pair_key in seen_candidates:
            continue
        seen_candidates.add(cand_pair_key)
        
        shared_club = club if club == mod_club else None
        
        # If clubs differ and runner has low overlap, skip weak cross-club noise
        if not shared_club and len(recs) < 2:
            continue
        
        confidence, reasons = calculate_match_probability(leg_stats, mod_stats, shared_club, True)
        
        # Unique candidate ID
        cid = f"{lookup_key.lower().replace(' ', '_').replace('.', '').replace('[', '').replace(']', '')}__{mod_name.lower().replace(' ', '_')}"
        
        # Check approved status
        is_approved = (
            existing_approved.get(lookup_key) == mod_name or
            existing_approved.get(f"{abbr_name} [{gender}, {club}]") == mod_name or
            existing_approved.get(abbr_name) == mod_name
        )
        status = "approved" if is_approved else "pending"
        
        candidates.append({
            "id": cid,
            "lookup_key": lookup_key,
            "display_name": lookup_key,
            "legacy_name": abbr_name,
            "full_name": mod_name,
            "confidence": confidence,
            "confidence_reasons": reasons,
            "legacy": leg_stats,
            "modern": mod_stats,
            "gender": gender,
            "status": status
        })

# Sort candidates by confidence descending, then name
candidates.sort(key=lambda c: (-c["confidence"], c["display_name"]))

with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
    json.dump(candidates, f, indent=2)

with open(CANDIDATES_JS_PATH, "w", encoding="utf-8") as f:
    f.write(f"// Auto-generated alias candidates with rich comparison analytics for admin review\nwindow.glAliasCandidates = {json.dumps(candidates)};\n")

print(f"\nGenerated {len(candidates)} candidate alias matches in:")
print(f"  - {CANDIDATES_PATH}")
print(f"  - {CANDIDATES_JS_PATH}")

high_conf = [c for c in candidates if c["confidence"] >= 90]
print(f"High-confidence candidate matches (>= 90%): {len(high_conf)}")
print("\nSample top candidates with detailed metrics:")
for c in high_conf[:10]:
    leg = c["legacy"]
    mod = c["modern"]
    print(f"  {c['display_name']:<42} ➔ {c['full_name']:<22} [{c['confidence']}%]")
    print(f"    Legacy: {leg['finishes']} races | {leg['years_span']} | Avg Pos: {leg['avg_pos']} (Best {leg['best_pos']}) | Cats: {', '.join(leg['categories'])}")
    print(f"    Modern: {mod['finishes']} races | {mod['years_span']} | Avg Pos: {mod['avg_pos']} (Best {mod['best_pos']}) | Cats: {', '.join(mod['categories'])}")
