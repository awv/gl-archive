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
# For abbreviated runners, explode by club if they have multiple clubs,
# so that e.g. A. Lewis at Aberdare and A. Lewis at PBB are evaluated independently!
abbr_runners = []
full_runners = []

for key, data in summary.items():
    name = data["canonical_name"].strip()
    if not name or "unknown" in name.lower() or name in ["-", "N/A"]:
        continue
    
    parts = name.split()
    if len(parts) >= 2:
        first_token = parts[0].replace('.', '')
        is_initial = len(first_token) == 1 and first_token.isalpha()
        
        if is_initial:
            # If runner has multiple clubs, create club-scoped entries
            if len(data["clubs"]) > 1:
                for club in data["clubs"]:
                    scoped_data = dict(data)
                    scoped_data["scoped_club"] = club
                    scoped_data["lookup_key"] = f"{name} [{club}]"
                    abbr_runners.append(scoped_data)
            else:
                scoped_data = dict(data)
                scoped_data["scoped_club"] = data["clubs"][0] if data["clubs"] else "Unattached"
                scoped_data["lookup_key"] = name  # unambiguous 1 club
                abbr_runners.append(scoped_data)
        else:
            full_runners.append(data)

print(f"Total Abbreviated Runner Entities (club-scoped): {len(abbr_runners)}")
print(f"Total Full Names: {len(full_runners)}")

# Index full runners by surname and initial
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
    lookup_key = ar["lookup_key"]
    scoped_club = ar["scoped_club"]
    parts = name.split()
    initial = parts[0].replace('.', '').upper()
    surname = " ".join(parts[1:]).lower()
    
    key = (surname, initial)
    potential_matches = full_by_surname_initial.get(key, [])
    if not potential_matches:
        continue
    
    ar_gender = ar["gender"]
    
    for fm in potential_matches:
        if fm["gender"] != ar_gender:
            continue
        
        full_name = fm["canonical_name"]
        fm_clubs = set(fm["clubs"])
        
        # Check club match
        has_club_match = scoped_club in fm_clubs
        
        confidence = 50
        confidence_reasons = []
        
        if has_club_match:
            confidence += 45
            confidence_reasons.append(f"Direct club match: {scoped_club}")
        else:
            # If this initial only has 1 club or different club
            if len(ar["clubs"]) > 1:
                # Abbreviated runner was seen at multiple clubs, and this isn't one of them -> skip
                continue
            confidence -= 15
            confidence_reasons.append(f"Different clubs ({scoped_club} vs {', '.join(fm_clubs)})")
        
        if ar["first_year"] <= 2022 and fm["last_year"] >= 2023:
            confidence += 4
            confidence_reasons.append("Historical progression (Legacy ➔ Modern era)")

        confidence = min(max(confidence, 10), 99)

        cid = f"{lookup_key.lower().replace(' ', '_').replace('.', '').replace('[', '').replace(']', '')}__{full_name.lower().replace(' ', '_')}"
        status = "approved" if existing_approved.get(lookup_key) == full_name or existing_approved.get(name) == full_name else "pending"

        candidates.append({
            "id": cid,
            "lookup_key": lookup_key,
            "legacy_name": name,
            "display_name": lookup_key if "[" in lookup_key else name,
            "full_name": full_name,
            "confidence": confidence,
            "confidence_reasons": confidence_reasons,
            "shared_clubs": [scoped_club] if has_club_match else [],
            "legacy_clubs": [scoped_club],
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

# Sort candidates by confidence descending, then name
candidates.sort(key=lambda c: (-c["confidence"], c["display_name"]))

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
    print(f"  {c['display_name']:<42} ➔ {c['full_name']:<22} [{c['confidence']}%]")
