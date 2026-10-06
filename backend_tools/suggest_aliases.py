import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_PATH = os.path.join(SCRIPT_DIR, "runners_summary.json")
CANDIDATES_PATH = os.path.join(SCRIPT_DIR, "alias_candidates.json")
CANDIDATES_JS_PATH = os.path.join(SCRIPT_DIR, "alias_candidates.js")
EXISTING_CORRECTIONS_PATH = os.path.join(SCRIPT_DIR, "corrections.json")

# Load existing corrections if present
existing_approved = {}
if os.path.exists(EXISTING_CORRECTIONS_PATH):
    try:
        with open(EXISTING_CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            existing_approved = json.load(f)
    except Exception:
        pass

with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
    summary = json.load(f)

# Classify into abbreviated vs full names
abbr_runners = []
full_runners = []

for key, data in summary.items():
    name = data["canonical_name"].strip()
    if not name or "unknown" in name.lower() or name in ["-", "N/A"]:
        continue
    
    parts = name.split()
    if len(parts) >= 2:
        first_token = parts[0].replace('.', '')
        # Check if first token is 1 letter (initial)
        if len(first_token) == 1 and first_token.isalpha():
            abbr_runners.append(data)
        else:
            full_runners.append(data)

print(f"Total Abbreviated Names (e.g. 'R. Gale'): {len(abbr_runners)}")
print(f"Total Full Names (e.g. 'Robert Gale'): {len(full_runners)}")

# Index full runners by surname and initial
# surname -> initial -> list of runners
full_by_surname_initial = {}
for fr in full_runners:
    name = fr["canonical_name"]
    parts = name.split()
    first_name = parts[0]
    surname = " ".join(parts[1:]).lower()
    initial = first_name[0].upper()
    
    key = (surname, initial)
    if key not in full_by_surname_initial:
        full_by_surname_initial[key] = []
    full_by_surname_initial[key].append(fr)

candidates = []

for ar in abbr_runners:
    name = ar["canonical_name"]
    parts = name.split()
    initial = parts[0].replace('.', '').upper()
    surname = " ".join(parts[1:]).lower()
    
    key = (surname, initial)
    potential_matches = full_by_surname_initial.get(key, [])
    if not potential_matches:
        continue
    
    ar_clubs = set(ar["clubs"])
    ar_gender = ar["gender"]
    
    for fm in potential_matches:
        # Must match gender
        if fm["gender"] != ar_gender:
            continue
        
        full_name = fm["canonical_name"]
        fm_clubs = set(fm["clubs"])
        
        # Calculate shared clubs
        shared = ar_clubs.intersection(fm_clubs)
        shared_clubs_list = sorted(list(shared))
        
        # Confidence scoring
        confidence = 50
        confidence_reasons = []
        
        if shared:
            confidence += 40
            confidence_reasons.append(f"Shared club(s): {', '.join(shared_clubs_list)}")
        
        # Chronology check: Abbreviated active before/up to 2023, Full name active 2023 onwards
        if ar["first_year"] <= 2022 and fm["last_year"] >= 2023:
            confidence += 5
            confidence_reasons.append("Historical chronological link (Legacy era -> Modern era)")
            
        # Unique surname bonus
        if len(potential_matches) == 1:
            confidence += 4
            confidence_reasons.append("Unique match for this surname & initial")
        elif len(potential_matches) > 1:
            confidence -= 10
            confidence_reasons.append(f"Multiple full names match this initial ({len(potential_matches)})")

        confidence = min(max(confidence, 10), 99)

        cid = f"{name.lower().replace(' ', '_').replace('.', '')}__{full_name.lower().replace(' ', '_')}"
        status = "approved" if existing_approved.get(name) == full_name else "pending"

        candidates.append({
            "id": cid,
            "legacy_name": name,
            "full_name": full_name,
            "confidence": confidence,
            "confidence_reasons": confidence_reasons,
            "shared_clubs": shared_clubs_list,
            "legacy_clubs": ar["clubs"],
            "full_clubs": fm["clubs"],
            "legacy_seasons": ar["seasons"],
            "full_seasons": fm["seasons"],
            "legacy_categories": ar["categories"],
            "full_categories": fm["categories"],
            "legacy_finishes": ar["finishes"],
            "full_finishes": fm["finishes"],
            "gender": ar_gender,
            "status": status
        })

# Sort candidates by confidence descending, then surname
candidates.sort(key=lambda c: (-c["confidence"], c["legacy_name"]))

with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
    json.dump(candidates, f, indent=2)

with open(CANDIDATES_JS_PATH, "w", encoding="utf-8") as f:
    f.write(f"// Auto-generated alias candidates for admin review\nwindow.glAliasCandidates = {json.dumps(candidates)};\n")

print(f"\nGenerated {len(candidates)} candidate alias matches in:")
print(f"  - {CANDIDATES_PATH}")
print(f"  - {CANDIDATES_JS_PATH}")

high_conf = [c for c in candidates if c["confidence"] >= 90]
print(f"High-confidence candidate matches (>= 90%): {len(high_conf)}")
print("\nSample top candidates:")
for c in high_conf[:15]:
    clubs_str = ", ".join(c["shared_clubs"]) if c["shared_clubs"] else "No direct club overlap"
    print(f"  {c['legacy_name']:<18} ➔ {c['full_name']:<22} [{c['confidence']}%] ({clubs_str})")
