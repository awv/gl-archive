import os
import json
import re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "data.json")
REPORT_JSON_PATH = os.path.join(SCRIPT_DIR, "integrity_report.json")
REPORT_JS_PATH = os.path.join(SCRIPT_DIR, "integrity_report.js")

def parse_age(cat):
    if not cat:
        return 28
    if "U23" in cat:
        return 22
    if "Senior" in cat:
        return 28
    nums = re.findall(r'\d+', cat)
    return int(nums[0]) if nums else 28

def run_integrity_audit():
    print(f"Loading database from {DATA_JSON_PATH}...")
    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loaded {len(records)} race finish records.")

    # Group by athlete identity
    by_athlete = defaultdict(list)
    for r in records:
        athlete = r.get("athlete", "").strip()
        if not athlete or "unknown" in athlete.lower() or athlete in ["-", "N/A"]:
            continue
        by_athlete[athlete].append(r)

    fixture_collisions = []
    age_regressions = []
    
    for athlete, recs in by_athlete.items():
        # 1. Check Fixture Collisions (Same runner competing twice in the same fixture)
        fixtures_map = defaultdict(list)
        for r in recs:
            fkey = (r["season_key"], r["match"])
            fixtures_map[fkey].append(r)

        for fkey, frecs in fixtures_map.items():
            if len(frecs) > 1:
                # Same person in the same race multiple times
                clubs = list(set(r["club"] for r in frecs))
                fixture_collisions.append({
                    "athlete": athlete,
                    "season": frecs[0]["season"],
                    "season_key": fkey[0],
                    "match": fkey[1],
                    "duplicate_count": len(frecs),
                    "clubs": clubs,
                    "finishes": [
                        {
                            "raw_name": r.get("raw_name"),
                            "club": r.get("club"),
                            "raw_club": r.get("raw_club"),
                            "pos": r.get("pos"),
                            "age_cat": r.get("age_cat"),
                            "time": r.get("time")
                        }
                        for r in frecs
                    ]
                })

        # 2. Check Biological Age Regressions
        if len(recs) >= 2:
            recs_sorted = sorted(recs, key=lambda x: (x["season_key"], x.get("match", 0)))
            max_age_seen = 0
            max_age_rec = None

            for r in recs_sorted:
                yr = int(r["season_key"].split("_")[0])
                age = parse_age(r.get("age_cat"))

                if max_age_seen >= 35 and age < max_age_seen - 5:
                    # Allow minor edge-case where Senior in same year or U23/Senior transition
                    prior_yr = int(max_age_rec["season_key"].split("_")[0])
                    if not (max_age_seen <= 35 and age == 28 and yr == prior_yr):
                        age_regressions.append({
                            "athlete": athlete,
                            "older_record": {
                                "season": max_age_rec["season"],
                                "match": max_age_rec.get("match"),
                                "club": max_age_rec.get("club"),
                                "raw_name": max_age_rec.get("raw_name"),
                                "age_cat": max_age_rec.get("age_cat"),
                                "pos": max_age_rec.get("pos")
                            },
                            "younger_record": {
                                "season": r["season"],
                                "match": r.get("match"),
                                "club": r.get("club"),
                                "raw_name": r.get("raw_name"),
                                "age_cat": r.get("age_cat"),
                                "pos": r.get("pos")
                            },
                            "age_drop": max_age_seen - age
                        })
                        break

                if age > max_age_seen:
                    max_age_seen = age
                    max_age_rec = r

    # Aggregate summaries
    athletes_with_collisions = sorted(list(set(c["athlete"] for c in fixture_collisions)))
    athletes_with_regressions = sorted(list(set(c["athlete"] for c in age_regressions)))
    both_anomalies = sorted(list(set(athletes_with_collisions).intersection(set(athletes_with_regressions))))

    report = {
        "summary": {
            "total_finishers": len(records),
            "total_athletes": len(by_athlete),
            "athletes_with_fixture_collisions": len(athletes_with_collisions),
            "total_fixture_collision_events": len(fixture_collisions),
            "athletes_with_age_regressions": len(athletes_with_regressions),
            "athletes_with_both_anomalies": len(both_anomalies)
        },
        "athletes_with_both_anomalies": both_anomalies,
        "fixture_collisions": fixture_collisions,
        "age_regressions": age_regressions
    }

    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(REPORT_JS_PATH, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated data integrity audit report\nwindow.glIntegrityReport = {json.dumps(report)};\n")

    print("\n" + "="*60)
    print("GWENT LEAGUE DATA INTEGRITY AUDIT REPORT")
    print("="*60)
    print(f"Total Finish Records: {len(records):,}")
    print(f"Total Athlete Identities: {len(by_athlete):,}")
    print(f"Athletes with Concurrent Fixture Collisions: {len(athletes_with_collisions)}")
    print(f"Total Concurrent Collision Events: {len(fixture_collisions)}")
    print(f"Athletes with Biological Age Regressions: {len(athletes_with_regressions)}")
    print(f"Athletes Suffering BOTH Anomalies (High Severity): {len(both_anomalies)}")
    print(f"\nReport written to:\n  - {REPORT_JSON_PATH}\n  - {REPORT_JS_PATH}")
    print("="*60)

    if both_anomalies:
        print("\nTop 15 Most Severely Compromised Identities (Both Collisions & Age Regressions):")
        for a in both_anomalies[:15]:
            cols = [c for c in fixture_collisions if c["athlete"] == a]
            regs = [r for r in age_regressions if r["athlete"] == a]
            first_c = cols[0]
            first_r = regs[0]
            print(f"\n  Athlete: {a}")
            print(f"    Collision: {first_c['season']} M{first_c['match']} across {', '.join(first_c['clubs'])}")
            print(f"    Regression: {first_r['older_record']['age_cat']} ({first_r['older_record']['club']}) ➔ {first_r['younger_record']['age_cat']} ({first_r['younger_record']['club']})")

if __name__ == "__main__":
    run_integrity_audit()
