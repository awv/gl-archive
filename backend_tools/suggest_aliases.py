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

# ==========================================
# 1. Nickname & Diminutive Reference Tables
# ==========================================
FORMAL_ROOTS = {
    # Male Diminutive Families
    "andrew": ["andy", "drew"],
    "phillip": ["phil", "pip"],
    "philip": ["phil", "pip"],
    "michael": ["mike", "mikey", "mick"],
    "david": ["dave", "davy", "dai"],
    "stephen": ["steve", "stevie"],
    "steven": ["steve", "stevie"],
    "daniel": ["dan", "danny"],
    "christopher": ["chris", "christie"],
    "christian": ["chris"],
    "thomas": ["tom", "tommy"],
    "robert": ["rob", "robbie", "bob", "bobby"],
    "matthew": ["matt", "matty"],
    "william": ["will", "willy", "bill", "billy", "liam"],
    "james": ["jim", "jimmy", "jamie"],
    "alexander": ["alex", "alec", "sandy"],
    "anthony": ["antony", "tony"],
    "antony": ["anthony", "tony"],
    "richard": ["rich", "richie", "rick", "ricky", "dick"],
    "nicholas": ["nick", "nicky"],
    "benjamin": ["ben", "benji", "benny"],
    "edward": ["ed", "eddie", "ted", "teddy", "ned"],
    "jonathan": ["jon", "jonny", "john", "johnny"],
    "john": ["jonny", "johnny", "jon"],
    "joseph": ["joe", "joey"],
    "samuel": ["sam", "sammy"],
    "timothy": ["tim", "timmy"],
    "peter": ["pete"],
    "patrick": ["pat", "paddy"],
    "kenneth": ["ken", "kenny"],
    "raymond": ["ray"],
    "donald": ["don", "donnie"],
    "ronald": ["ron", "ronnie"],
    "leonard": ["len", "lenny"],
    "geoffrey": ["geoff", "jeff"],
    "jeffrey": ["jeff", "geoff"],
    "gregory": ["greg"],
    "russell": ["russ"],
    "douglas": ["doug"],
    "stuart": ["stu"],
    "stewart": ["stu"],
    "bradley": ["brad"],
    "lawrence": ["larry"],
    "laurence": ["larry"],
    "gareth": ["gary", "gaz"],
    "oliver": ["oli", "ollie"],
    "sebastian": ["seb"],
    "dominic": ["dom"],
    "joshua": ["josh"],
    "alan": ["alun"],
    "hugh": ["huw"],
    "owen": ["owain"],
    # Female Diminutive Families
    "charlotte": ["charlie", "lottie"],
    "elizabeth": ["liz", "lizzie", "beth", "betty", "eliza"],
    "rebecca": ["becky", "becca"],
    "catherine": ["cathy", "cat", "kate", "katie"],
    "katherine": ["cathy", "cat", "kate", "katie"],
    "kathryn": ["cathy", "cat", "kate", "katie"],
    "jennifer": ["jen", "jenny"],
    "samantha": ["sam", "sammy"],
    "victoria": ["vicky", "vicki", "tori"],
    "alexandra": ["alex", "alexa", "ali", "allie"],
    "patricia": ["pat", "trish", "tricia"],
    "margaret": ["maggie", "meg", "peggy", "mags"],
    "susan": ["suzanne", "sue", "susie", "suzi"],
    "suzanne": ["sue", "susie", "suzi"],
    "christine": ["chris", "chrissie", "tina"],
    "christina": ["chris", "chrissie", "tina"],
    "nicola": ["nic", "nicky"],
    "joanne": ["jo", "josie"],
    "joanna": ["jo", "josie"],
    "stephanie": ["steph"],
    "deborah": ["debra", "deb", "debbie"],
    "debra": ["deb", "debbie"],
    "jessica": ["jess", "jessie"],
    "frances": ["francesca", "fran", "frankie"],
    "francesca": ["fran", "frankie"],
    "eleanor": ["ellie", "ella"],
    "natasha": ["tash", "tasha"],
    "abigail": ["abby", "abbie"],
    "caroline": ["carolyn", "carol", "caz"],
    "jacqueline": ["jacqui", "jackie"],
}

NICKNAME_TO_FORMAL = {}
for formal, nicks in FORMAL_ROOTS.items():
    for nick in nicks:
        NICKNAME_TO_FORMAL[nick] = formal

def check_nickname_pair(name_a, name_b):
    """
    Checks if name_a and name_b share the same surname and have first names
    that form a known nickname/diminutive pair. Returns dict with 'nick' and 'formal',
    or None if they do not match.
    """
    parts_a = name_a.strip().split()
    parts_b = name_b.strip().split()
    if len(parts_a) < 2 or len(parts_b) < 2:
        return None
    sur_a = " ".join(parts_a[1:]).lower()
    sur_b = " ".join(parts_b[1:]).lower()
    if sur_a != sur_b:
        return None
    f_a = parts_a[0].lower()
    f_b = parts_b[0].lower()
    if f_a == f_b:
        return None
    
    # Check if f_a is known nickname of f_b
    if NICKNAME_TO_FORMAL.get(f_a) == f_b or (f_b in FORMAL_ROOTS and f_a in FORMAL_ROOTS[f_b]):
        return {"nick": name_a, "formal": name_b, "nick_first": parts_a[0], "formal_first": parts_b[0]}
    # Check if f_b is known nickname of f_a
    if NICKNAME_TO_FORMAL.get(f_b) == f_a or (f_a in FORMAL_ROOTS and f_b in FORMAL_ROOTS[f_a]):
        return {"nick": name_b, "formal": name_a, "nick_first": parts_b[0], "formal_first": parts_a[0]}
    # Check if both map to the same root (e.g. Vicki and Vicky)
    root_a = NICKNAME_TO_FORMAL.get(f_a)
    root_b = NICKNAME_TO_FORMAL.get(f_b)
    if root_a and root_a == root_b:
        if len(f_a) <= len(f_b):
            return {"nick": name_a, "formal": name_b, "nick_first": parts_a[0], "formal_first": parts_b[0]}
        else:
            return {"nick": name_b, "formal": name_a, "nick_first": parts_b[0], "formal_first": parts_a[0]}
    return None

# ==========================================
# 2. Load Existing Corrections & Database
# ==========================================
existing_approved = {}
if os.path.exists(EXISTING_CORRECTIONS_PATH):
    try:
        with open(EXISTING_CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            existing_approved = json.load(f)
    except Exception:
        pass

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
def calculate_match_probability(leg_stats, mod_stats, shared_club, gender_match, nickname_info=None):
    if not gender_match:
        return 0, ["Gender mismatch"]
    
    score = 50.0
    reasons = []

    # 0. Nickname / Diminutive match boost
    if nickname_info:
        score += 25.0
        reasons.append(f"✔ Known diminutive nickname ({nickname_info['nick_first']} ➔ {nickname_info['formal_first']})")

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
    if leg_stats["last_year"] <= 2024 and mod_stats["first_year"] >= 2021:
        score += 8.0
        reasons.append(f"Era transition ({leg_stats['years_span'].split()[0]} ➔ {mod_stats['years_span'].split()[0]})")

    # 6. Sample Size
    if leg_stats["finishes"] >= 3 and mod_stats["finishes"] >= 3:
        score += 4.0
        reasons.append(f"Strong race record ({leg_stats['finishes']} earlier + {mod_stats['finishes']} later finishes)")

    final_score = int(min(max(score, 5.0), 99.0))
    return final_score, reasons

# ==========================================
# 3. Group records by runner entities
# ==========================================
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

# ----------------------------------------------------
# Pass A: Abbreviated Name ➔ Full Name Candidates
# ----------------------------------------------------
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
        
        # Check if potential_matches contains members of the same nickname family
        # (e.g. Andrew Blair and Andy Blair both at Les Croupiers)
        family_variants = []
        for other in potential_matches:
            if other["name"] != mod_name and other["club"] == mod_club:
                pair_check = check_nickname_pair(mod_name, other["name"])
                if pair_check:
                    family_variants.append(other["name"])
        if family_variants:
            reasons.append(f"Name family candidate ({mod_name} / related: {', '.join(family_variants)})")
            # If mod_name is the formal root, give priority boost
            p_check = check_nickname_pair(mod_name, family_variants[0])
            if p_check and p_check["formal"] == mod_name:
                confidence = min(99, confidence + 5)
        
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
            "is_nickname_variant": False,
            "confidence": confidence,
            "confidence_reasons": reasons,
            "legacy": leg_stats,
            "modern": mod_stats,
            "gender": gender,
            "status": status
        })

# ----------------------------------------------------
# Pass B: Full-Name Nickname & Variant Pairs (Modern)
# ----------------------------------------------------
# Group full-name runners by (club, surname_lower, gender)
full_by_club_surname = defaultdict(list)
for (full_name, club, gender), recs in full_records_map.items():
    parts = full_name.split()
    surname = " ".join(parts[1:]).lower()
    full_by_club_surname[(club, surname, gender)].append((full_name, compute_stats(full_name, club, recs)))

nickname_pairs_count = 0
for (club, surname, gender), runner_list in full_by_club_surname.items():
    if len(runner_list) < 2:
        continue
    
    # Compare each pair of runners within the same club and surname
    for i in range(len(runner_list)):
        for j in range(i + 1, len(runner_list)):
            name_a, stats_a = runner_list[i]
            name_b, stats_b = runner_list[j]
            
            pair_match = check_nickname_pair(name_a, name_b)
            if not pair_match:
                continue
            
            # Map nickname ➔ formal canonical name
            nick_name = pair_match["nick"]
            formal_name = pair_match["formal"]
            nick_stats = stats_a if name_a == nick_name else stats_b
            formal_stats = stats_b if name_b == formal_name else stats_a
            
            lookup_key = f"{nick_name} [{club}]"
            cand_pair_key = (lookup_key, formal_name)
            if cand_pair_key in seen_candidates:
                continue
            seen_candidates.add(cand_pair_key)
            
            confidence, reasons = calculate_match_probability(
                nick_stats, formal_stats, shared_club=club, gender_match=True, nickname_info=pair_match
            )
            
            cid = f"nick__{lookup_key.lower().replace(' ', '_').replace('.', '').replace('[', '').replace(']', '')}__{formal_name.lower().replace(' ', '_')}"
            
            is_approved = (
                existing_approved.get(lookup_key) == formal_name or
                existing_approved.get(f"{nick_name} [{gender}, {club}]") == formal_name or
                existing_approved.get(nick_name) == formal_name
            )
            status = "approved" if is_approved else "pending"
            
            candidates.append({
                "id": cid,
                "lookup_key": lookup_key,
                "display_name": lookup_key,
                "legacy_name": nick_name,
                "full_name": formal_name,
                "is_nickname_variant": True,
                "nickname_detail": f"{pair_match['nick_first']} ➔ {pair_match['formal_first']}",
                "confidence": confidence,
                "confidence_reasons": reasons,
                "legacy": nick_stats,
                "modern": formal_stats,
                "gender": gender,
                "status": status
            })
            nickname_pairs_count += 1

print(f"Generated {nickname_pairs_count} same-club diminutive/nickname variant pairs for review.")

# Sort candidates: pending nickname variants & high confidence prioritized
candidates.sort(key=lambda c: (
    0 if c["status"] == "pending" else 1,
    -1 if c.get("is_nickname_variant") else 0,
    -c["confidence"],
    c["display_name"]
))

with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
    json.dump(candidates, f, indent=2)

with open(CANDIDATES_JS_PATH, "w", encoding="utf-8") as f:
    f.write(f"// Auto-generated alias candidates with rich comparison analytics for admin review\nwindow.glAliasCandidates = {json.dumps(candidates)};\n")

print(f"\nGenerated {len(candidates)} total candidate alias matches in:")
print(f"  - {CANDIDATES_PATH}")
print(f"  - {CANDIDATES_JS_PATH}")

high_conf = [c for c in candidates if c["confidence"] >= 90]
nick_cands = [c for c in candidates if c.get("is_nickname_variant")]
print(f"High-confidence candidate matches (>= 90%): {len(high_conf)}")
print(f"Diminutive/Nickname candidate matches: {len(nick_cands)}")
print("\nSample top candidates with detailed metrics:")
for c in candidates[:12]:
    leg = c["legacy"]
    mod = c["modern"]
    variant_tag = f" [NICKNAME: {c.get('nickname_detail')}]" if c.get("is_nickname_variant") else ""
    print(f"  {c['display_name']:<42} ➔ {c['full_name']:<22} [{c['confidence']}%]{variant_tag}")
    print(f"    Legacy: {leg['finishes']} races | {leg['years_span']} | Avg Pos: {leg['avg_pos']} (Best {leg['best_pos']}) | Cats: {', '.join(leg['categories'])}")
    print(f"    Modern: {mod['finishes']} races | {mod['years_span']} | Avg Pos: {mod['avg_pos']} (Best {mod['best_pos']}) | Cats: {', '.join(mod['categories'])}")
