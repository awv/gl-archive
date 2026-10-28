import json
import os
import re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "data.json")
CANDIDATES_JSON_PATH = os.path.join(SCRIPT_DIR, "transfer_candidates.json")
CANDIDATES_JS_PATH = os.path.join(SCRIPT_DIR, "transfer_candidates.js")
CONFIRMED_TRANSFERS_JSON_PATH = os.path.join(SCRIPT_DIR, "club_transfers.json")
CONFIRMED_TRANSFERS_JS_PATH = os.path.join(SCRIPT_DIR, "club_transfers.js")

def parse_age(cat):
    if not cat:
        return 28
    if "U23" in cat:
        return 22
    if "Senior" in cat:
        return 28
    nums = re.findall(r'\d+', cat)
    return int(nums[0]) if nums else 28

def load_data():
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_confirmed_transfers():
    if os.path.exists(CONFIRMED_TRANSFERS_JSON_PATH):
        try:
            with open(CONFIRMED_TRANSFERS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default initial confirmed transfer (Huw Evans confirmed by user)
    return {
        "Huw Evans": {
            "gender": "M",
            "clubs": ["Les Croupiers Running Club", "Parc Bryn Bach Running Club"],
            "primary_club": "Parc Bryn Bach Running Club",
            "from_club": "Les Croupiers Running Club",
            "to_club": "Parc Bryn Bach Running Club",
            "transfer_season": "2022/2023",
            "confirmed": True
        }
    }

def analyze_transfers():
    records = load_data()
    confirmed = load_confirmed_transfers()
    
    # Group records by (athlete_name, gender)
    by_runner = defaultdict(list)
    for r in records:
        name = r.get("athlete", "").strip()
        if not name or "unknown" in name.lower() or name in ["-", "N/A"]:
            continue
        first_token = name.split()[0].replace('.', '')
        # Only process full-name runners
        if len(first_token) <= 1:
            continue
        
        # Exclude guest appearances from club qualification
        club = r.get("club", "")
        if "guest" in club.lower() or r.get("is_guest"):
            continue
            
        by_runner[(name, r["gender"])].append(r)

    candidates = []

    for (name, gender), runner_recs in by_runner.items():
        # Group finishes by canonical club
        clubs_map = defaultdict(list)
        for r in runner_recs:
            clubs_map[r["club"]].append(r)
        
        if len(clubs_map) < 2:
            continue

        # Compute stats for each club
        club_summaries = []
        for c, crecs in clubs_map.items():
            seasons = sorted(list(set(r["season"] for r in crecs)))
            years = [int(s.split("/")[0]) for s in seasons]
            min_yr = min(years)
            max_yr = max(years)
            fixtures = set((r["season_key"], r["match"]) for r in crecs)
            pos_list = [r["pos"] for r in crecs if r.get("pos", 0) > 0]
            cat_pos_list = [r["cat_pos"] for r in crecs if r.get("cat_pos", 0) > 0]
            cats = sorted(list(set(r["age_cat"] for r in crecs)))
            avg_pos = round(sum(pos_list) / len(pos_list), 1) if pos_list else 0
            best_pos = min(pos_list) if pos_list else 0
            avg_cat_pos = round(sum(cat_pos_list) / len(cat_pos_list), 1) if cat_pos_list else 0
            best_cat_pos = min(cat_pos_list) if cat_pos_list else 0
            
            club_summaries.append({
                "club": c,
                "count": len(crecs),
                "seasons": seasons,
                "first_yr": min_yr,
                "last_yr": max_yr,
                "years_span": f"{min_yr}–{max_yr + 1} ({len(seasons)} {'season' if len(seasons) == 1 else 'seasons'})",
                "fixtures": fixtures,
                "avg_pos": avg_pos,
                "best_pos": best_pos,
                "avg_cat_pos": avg_cat_pos,
                "best_cat_pos": best_cat_pos,
                "categories": cats,
                "ages": [parse_age(ct) for ct in cats]
            })

        # Sort clubs chronologically by first appearance, then last appearance
        club_summaries.sort(key=lambda cs: (cs["first_yr"], cs["last_yr"]))

        # Compare pairs of clubs
        for i in range(len(club_summaries)):
            for j in range(i + 1, len(club_summaries)):
                ca = club_summaries[i]
                cb = club_summaries[j]

                # Check overlap in fixtures
                overlapping_fixtures = ca["fixtures"].intersection(cb["fixtures"])
                overlap_count = len(overlapping_fixtures)

                # Check overlap in seasons
                seasons_a = set(ca["seasons"])
                seasons_b = set(cb["seasons"])
                overlapping_seasons = seasons_a.intersection(seasons_b)

                # Category progression
                max_age_a = max(ca["ages"]) if ca["ages"] else 28
                min_age_b = min(cb["ages"]) if cb["ages"] else 28
                age_diff = min_age_b - max_age_a

                # Chronological handover
                gap_years = cb["first_yr"] - ca["last_yr"]

                score = 50.0
                reasons = []
                flags = []

                # 1. Timeline Handover
                if overlap_count == 0 and len(overlapping_seasons) == 0:
                    score += 25.0
                    if gap_years <= 1:
                        score += 10.0
                        reasons.append(f"Clean immediate handover ({ca['years_span'].split()[0]} ➔ {cb['years_span'].split()[0]}) with 0 overlap")
                    elif gap_years <= 3:
                        score += 5.0
                        reasons.append(f"Clean handover with {gap_years}-year break ({ca['years_span'].split()[0]} ➔ {cb['years_span'].split()[0]})")
                    else:
                        reasons.append(f"Break between clubs ({gap_years} seasons)")
                elif overlap_count == 0 and len(overlapping_seasons) == 1:
                    score += 15.0
                    reasons.append(f"Mid-season transfer during {list(overlapping_seasons)[0]} (0 fixture conflicts)")
                else:
                    score -= 40.0
                    flags.append(f"Conflicting active fixtures ({overlap_count} matches run concurrently: likely separate runners)")

                # 2. Age Progression
                is_severe_regression = False
                if age_diff >= 0:
                    score += 15.0
                    reasons.append(f"Valid age trajectory: {', '.join(ca['categories'])} ➔ {', '.join(cb['categories'])}")
                elif age_diff >= -5:
                    if "Senior" in ca["categories"] and "Senior" in cb["categories"]:
                        score += 10.0
                        reasons.append("Senior category maintained across transfer")
                    else:
                        score -= 10.0
                        flags.append(f"Minor age bracket regression ({', '.join(ca['categories'])} vs {', '.join(cb['categories'])})")
                else:
                    is_severe_regression = True
                    score = 0.0
                    flags.append(f"Impossible biological age regression: {', '.join(ca['categories'])} ➔ {', '.join(cb['categories'])} (cannot be same runner)")

                # 3. Pace & Category Position Similarity
                if ca["avg_pos"] > 0 and cb["avg_pos"] > 0:
                    pos_diff = abs(ca["avg_pos"] - cb["avg_pos"])
                    if pos_diff <= 20:
                        score += 15.0
                        reasons.append(f"Very consistent pace (Avg #{ca['avg_pos']} vs #{cb['avg_pos']}, Δ {pos_diff:.1f})")
                    elif pos_diff <= 50:
                        score += 8.0
                        reasons.append(f"Consistent standard (Avg #{ca['avg_pos']} vs #{cb['avg_pos']})")
                    elif pos_diff > 120:
                        score -= 20.0
                        flags.append(f"Significant pace divergence (Avg #{ca['avg_pos']} vs #{cb['avg_pos']})")

                # Category rank consistency
                if ca["avg_cat_pos"] > 0 and cb["avg_cat_pos"] > 0:
                    cat_diff = abs(ca["avg_cat_pos"] - cb["avg_cat_pos"])
                    if cat_diff <= 4:
                        score += 8.0
                        reasons.append(f"Category rank alignment (Avg #{ca['avg_cat_pos']} vs #{cb['avg_cat_pos']})")

                # 4. Sample Size
                if ca["count"] >= 3 and cb["count"] >= 3:
                    score += 5.0
                    reasons.append(f"Strong sample ({ca['count']} races at {ca['club']} + {cb['count']} at {cb['club']})")

                final_score = int(min(max(score, 0.0), 99.0)) if not is_severe_regression else 0

                candidate_id = f"transfer__{name.lower().replace(' ', '_')}__{ca['club'].lower()[:12].replace(' ', '_')}__{cb['club'].lower()[:12].replace(' ', '_')}"

                # Clean serializable versions of ca and cb (without set objects)
                stats_a = {k: v for k, v in ca.items() if k != "fixtures"}
                stats_b = {k: v for k, v in cb.items() if k != "fixtures"}

                # Check if this transfer is confirmed
                is_confirmed = False
                if name in confirmed:
                    c_info = confirmed[name]
                    if (c_info.get("from_club") == ca["club"] and c_info.get("to_club") == cb["club"]) or \
                       (ca["club"] in c_info.get("clubs", []) and cb["club"] in c_info.get("clubs", [])):
                        is_confirmed = True

                if is_confirmed and not is_severe_regression and overlap_count == 0:
                    status = "confirmed"
                elif overlap_count >= 1 or is_severe_regression:
                    status = "separate_runners"
                elif final_score >= 70:
                    status = "pending"
                else:
                    status = "unlikely"

                candidates.append({
                    "id": candidate_id,
                    "name": name,
                    "gender": gender,
                    "from_club": ca["club"],
                    "to_club": cb["club"],
                    "confidence": final_score,
                    "status": status,
                    "overlap_count": overlap_count,
                    "overlapping_seasons": sorted(list(overlapping_seasons)),
                    "handover_season": cb["seasons"][0] if cb["seasons"] else "Unknown",
                    "from_stats": stats_a,
                    "to_stats": stats_b,
                    "reasons": reasons,
                    "flags": flags
                })

    # Sort candidates: Confirmed first, then Pending high confidence first, then Separate Runners, then Unlikely
    candidates.sort(key=lambda c: (
        0 if c["status"] == "confirmed" else (1 if c["status"] == "pending" else (2 if c["status"] == "separate_runners" else 3)),
        c["overlap_count"],
        -c["confidence"],
        c["name"]
    ))

    # Write candidates JSON and JS
    with open(CANDIDATES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2)

    with open(CANDIDATES_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated club transfer candidate matches for admin review\nwindow.glTransferCandidates = {json.dumps(candidates)};\n")

    # Write confirmed transfers JSON and JS
    with open(CONFIRMED_TRANSFERS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(confirmed, f, indent=2)

    with open(CONFIRMED_TRANSFERS_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated confirmed club transfers for GL Archive\nwindow.glClubTransfers = {json.dumps(confirmed)};\n")

    print(f"Generated {len(candidates)} club transfer pairs:")
    print(f"  - {CANDIDATES_JSON_PATH}")
    print(f"  - {CANDIDATES_JS_PATH}")
    print(f"  - {CONFIRMED_TRANSFERS_JSON_PATH}")
    print(f"  - {CONFIRMED_TRANSFERS_JS_PATH}")
    
    clean_transfers = [c for c in candidates if c["overlap_count"] == 0 and c["confidence"] >= 80]
    conflicts = [c for c in candidates if c["overlap_count"] > 0]
    print(f"Clean transfers (>=80%): {len(clean_transfers)}")
    print(f"Conflicting / overlapping fixtures: {len(conflicts)}")
    print(f"Confirmed transfers: {len([c for c in candidates if c['status'] == 'confirmed'])}")

if __name__ == "__main__":
    analyze_transfers()
