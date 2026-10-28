import json
import os
import re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "data.json")
CANDIDATES_JSON_PATH = os.path.join(SCRIPT_DIR, "name_change_candidates.json")
CANDIDATES_JS_PATH = os.path.join(SCRIPT_DIR, "name_change_candidates.js")
CONFIRMED_NAME_CHANGES_JSON_PATH = os.path.join(SCRIPT_DIR, "name_changes.json")
CONFIRMED_NAME_CHANGES_JS_PATH = os.path.join(SCRIPT_DIR, "name_changes.js")

def parse_age(cat):
    if not cat:
        return 28
    if "U23" in cat:
        return 22
    if "Senior" in cat:
        return 28
    nums = re.findall(r'\d+', cat)
    return int(nums[0]) if nums else 28

def lev_dist(s1, s2):
    if len(s1) < len(s2):
        return lev_dist(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            ins = prev[j + 1] + 1
            dele = curr[j] + 1
            sub = prev[j] + (0 if c1 == c2 else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]

def load_data():
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_confirmed():
    if os.path.exists(CONFIRMED_NAME_CHANGES_JSON_PATH):
        try:
            with open(CONFIRMED_NAME_CHANGES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "Alaw Beynon-Thomas": {
            "primary_name": "Alaw Evans",
            "maiden_name": "Alaw Beynon-Thomas",
            "club": "Les Croupiers Running Club",
            "effective_season": "2023/2024",
            "note": "Formerly competed as Alaw Beynon-Thomas",
            "confirmed": True
        },
        "Antoinette Dumayne": {
            "primary_name": "Antoinette Rose",
            "maiden_name": "Antoinette Dumayne",
            "club": "Lliswerry Runners",
            "effective_season": "2023/2024",
            "note": "Formerly competed as Antoinette Dumayne",
            "confirmed": True
        }
    }

def analyze_name_changes():
    records = load_data()
    confirmed = load_confirmed()
    
    # Group female finishes by (club, first_name)
    by_club_first = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r.get("gender") != "F":
            continue
        athlete = r.get("athlete", "").strip()
        if not athlete or len(athlete.split()) < 2:
            continue
        first_token = athlete.split()[0].replace(".", "")
        if len(first_token) <= 1:
            continue
        club = r.get("club", "")
        if "guest" in club.lower() or r.get("is_guest"):
            continue
        by_club_first[(club, first_token.lower())][athlete].append(r)

    candidates = []

    for (club, first), runners in by_club_first.items():
        if len(runners) < 2:
            continue
        runner_names = list(runners.keys())
        num_runners_with_first = len(runner_names)

        for i in range(len(runner_names)):
            for j in range(i + 1, len(runner_names)):
                na = runner_names[i]
                nb = runner_names[j]
                recs_a = runners[na]
                recs_b = runners[nb]

                sur_a = " ".join(na.split()[1:]).lower()
                sur_b = " ".join(nb.split()[1:]).lower()

                # Check if this pair is confirmed
                is_confirmed = False
                if (na in confirmed and confirmed[na].get("primary_name") == nb) or \
                   (nb in confirmed and confirmed[nb].get("primary_name") == na) or \
                   (na in confirmed and confirmed[na].get("maiden_name") == nb) or \
                   (nb in confirmed and confirmed[nb].get("maiden_name") == na):
                    is_confirmed = True

                # Gate 1: Levenshtein distance check (Spelling typos / aliases suppression)
                # If surnames differ by <= 2 edits (e.g. Pollack vs Pollak), it's a spelling typo, NOT a maiden-to-married transition!
                ld = lev_dist(sur_a, sur_b)
                if ld <= 2 and not is_confirmed:
                    continue

                # Gate 2: Compound / hyphenated surname relationship
                # e.g. Stephens -> Morgan-Stephens, Dew -> Harry Dew, Osborne -> Osborne-Nash, Gard -> Rose Gard
                is_compound = False
                if sur_a in sur_b or sur_b in sur_a:
                    tokens_a = set(re.split(r'[\s-]+', sur_a))
                    tokens_b = set(re.split(r'[\s-]+', sur_b))
                    if tokens_a.intersection(tokens_b):
                        is_compound = True

                # Gate 3: For non-compound, non-confirmed pairs:
                # Suppress student clubs (university / college) where high natural turnover creates spurious timeline pairs
                if not is_confirmed and not is_compound:
                    if any(u in club.lower() for u in ["university", "college", "polytechnic"]):
                        continue

                    # Multi-runner ambiguity suppression:
                    # If a club has 3 or more runners with the same first name (e.g. 5 Hannahs at Bristol & West),
                    # pairwise guessing is combinatorial noise. Only permit pairs when there are exactly 2 runners.
                    if num_runners_with_first >= 3:
                        continue

                    # Minimum race history:
                    # Both runners must have >= 2 races, and total races >= 6
                    if len(recs_a) < 2 or len(recs_b) < 2 or (len(recs_a) + len(recs_b) < 6):
                        continue

                seasons_a = sorted(list(set(r["season"] for r in recs_a)))
                seasons_b = sorted(list(set(r["season"] for r in recs_b)))
                yr_a = [int(s.split("/")[0]) for s in seasons_a]
                yr_b = [int(s.split("/")[0]) for s in seasons_b]

                # Order chronologically (earlier -> later)
                if min(yr_a) > min(yr_b):
                    na, nb = nb, na
                    recs_a, recs_b = recs_b, recs_a
                    seasons_a, seasons_b = seasons_b, seasons_a
                    yr_a, yr_b = yr_b, yr_a
                    sur_a, sur_b = sur_b, sur_a

                # Overlap check
                fix_a = set((r["season_key"], r["match"]) for r in recs_a)
                fix_b = set((r["season_key"], r["match"]) for r in recs_b)
                overlap_fixtures = fix_a.intersection(fix_b)
                overlap_count = len(overlap_fixtures)
                overlapping_seasons = sorted(list(set(seasons_a).intersection(set(seasons_b))))
                gap_years = min(yr_b) - max(yr_a)

                # Gate 4: Overlap & timeline rules for non-confirmed candidates
                if not is_confirmed:
                    # If they ran on the exact same fixture day, they are separate concurrent runners
                    if overlap_count > 0:
                        continue
                    # Cannot overlap across multiple seasons
                    if len(overlapping_seasons) > 1:
                        continue
                    # For non-compound speculative matches, gap must be clean: 0 to 3 seasons
                    if not is_compound:
                        if gap_years < 0 or gap_years > 3:
                            continue

                # Calculate comparative stats
                pos_a = [r["pos"] for r in recs_a if r.get("pos", 0) > 0]
                pos_b = [r["pos"] for r in recs_b if r.get("pos", 0) > 0]
                cat_a = sorted(list(set(r["age_cat"] for r in recs_a)))
                cat_b = sorted(list(set(r["age_cat"] for r in recs_b)))
                avg_pos_a = round(sum(pos_a) / len(pos_a), 1) if pos_a else 0
                avg_pos_b = round(sum(pos_b) / len(pos_b), 1) if pos_b else 0
                best_pos_a = min(pos_a) if pos_a else 0
                best_pos_b = min(pos_b) if pos_b else 0

                # Gate 5: Hard Disqualification on Biological Age Regression
                max_age_a = max(parse_age(c) for c in cat_a) if cat_a else 28
                min_age_b = min(parse_age(c) for c in cat_b) if cat_b else 28
                if not is_confirmed and min_age_b < max_age_a - 5 and not (max_age_a == 28 and min_age_b == 22 and yr_a[-1] >= yr_b[0]):
                    continue  # Biological impossibility: later identity is younger than earlier identity

                reasons = []
                flags = []

                if is_confirmed:
                    score = 100
                    reasons.append("Verified and confirmed in name changes registry")
                    reasons.append(f"Clean continuous membership at {club}")
                elif is_compound:
                    score = 88.0
                    reasons.append("Compound / hyphenated surname match (shared family name component)")
                    if overlap_count == 0:
                        score += 5.0
                        reasons.append(f"Clean timeline transition ({seasons_a[-1]} ➔ {seasons_b[0]})")
                    else:
                        flags.append(f"{overlap_count} overlapping fixture (verify mid-season change)")

                    # Age check
                    if min_age_b >= max_age_a:
                        score += 3.0
                        reasons.append(f"Age progression consistent: {', '.join(cat_a)} ➔ {', '.join(cat_b)}")
                    score = min(score, 95.0)
                else:
                    # Speculative timeline match
                    score = 52.0
                    reasons.append("Speculative Timeline Candidate • Verify with club records")
                    if overlap_count == 0 and len(overlapping_seasons) == 0:
                        score += 8.0
                        reasons.append(f"Sequential career handover with {gap_years}-year gap ({seasons_a[-1]} ➔ {seasons_b[0]})")
                    elif len(overlapping_seasons) == 1:
                        score += 4.0
                        reasons.append(f"Potential mid-season surname change during {overlapping_seasons[0]}")

                    if min_age_b >= max_age_a:
                        score += 4.0
                        reasons.append(f"Category consistency: {', '.join(cat_a)} ➔ {', '.join(cat_b)}")

                    if avg_pos_a > 0 and avg_pos_b > 0:
                        diff = abs(avg_pos_a - avg_pos_b)
                        if diff <= 25:
                            score += 4.0
                            reasons.append(f"Consistent pace profile (Avg #{avg_pos_a} vs #{avg_pos_b})")

                    reasons.append(f"Single pair with first name '{first.capitalize()}' at {club}")
                    score = min(score, 68.0)

                final_score = int(round(score))
                cand_id = f"name_change__{na.lower().replace(' ', '_')}__{nb.lower().replace(' ', '_')}"

                candidates.append({
                    "id": cand_id,
                    "club": club,
                    "gender": "F",
                    "earlier_name": na,
                    "later_name": nb,
                    "effective_season": seasons_b[0] if seasons_b else "Unknown",
                    "confidence": final_score,
                    "status": "confirmed" if is_confirmed else "pending",
                    "is_compound": is_compound,
                    "overlap_count": overlap_count,
                    "overlapping_seasons": overlapping_seasons,
                    "gap_years": gap_years,
                    "earlier_stats": {
                        "name": na,
                        "club": club,
                        "count": len(recs_a),
                        "seasons": seasons_a,
                        "years_span": f"{min(yr_a)}–{max(yr_a) + 1} ({len(seasons_a)} {'season' if len(seasons_a) == 1 else 'seasons'})",
                        "avg_pos": avg_pos_a,
                        "best_pos": best_pos_a,
                        "categories": cat_a
                    },
                    "later_stats": {
                        "name": nb,
                        "club": club,
                        "count": len(recs_b),
                        "seasons": seasons_b,
                        "years_span": f"{min(yr_b)}–{max(yr_b) + 1} ({len(seasons_b)} {'season' if len(seasons_b) == 1 else 'seasons'})",
                        "avg_pos": avg_pos_b,
                        "best_pos": best_pos_b,
                        "categories": cat_b
                    },
                    "reasons": reasons,
                    "flags": flags
                })

    candidates.sort(key=lambda c: (
        0 if c["status"] == "confirmed" else 1,
        0 if c.get("is_compound") else 1,
        -c["confidence"],
        c["earlier_name"]
    ))

    # Write output files
    with open(CANDIDATES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2)

    with open(CANDIDATES_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated name change candidates (e.g. marriage) for GL Archive review\nwindow.glNameChangeCandidates = {json.dumps(candidates, indent=2)};\n")

    with open(CONFIRMED_NAME_CHANGES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(confirmed, f, indent=2)

    with open(CONFIRMED_NAME_CHANGES_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated verified name changes for GL Archive\nwindow.glNameChanges = {json.dumps(confirmed, indent=2)};\n")

    print(f"Generated {len(candidates)} high-integrity name change candidate pairs:")
    print(f"  - {CANDIDATES_JSON_PATH}")
    print(f"  - {CANDIDATES_JS_PATH}")
    print(f"  - {CONFIRMED_NAME_CHANGES_JSON_PATH}")
    print(f"  - {CONFIRMED_NAME_CHANGES_JS_PATH}")
    high_conf = [c for c in candidates if c["confidence"] >= 80]
    print(f"High-confidence pairs (>=80% confirmed/compound): {len(high_conf)}")
    print(f"Speculative timeline pairs (50-68%): {len(candidates) - len(high_conf)}")
    print(f"Confirmed name changes: {len([c for c in candidates if c['status'] == 'confirmed'])}")

if __name__ == "__main__":
    analyze_name_changes()
