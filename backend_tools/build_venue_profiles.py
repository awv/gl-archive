import json
import re
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_JSON = os.path.join(PROJECT_DIR, "data.json")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "assets", "data", "venue_profiles.json")
OUTPUT_JS = os.path.join(PROJECT_DIR, "assets", "data", "venue_profiles.js")

def parse_time_sec(t):
    if not t or ":" not in t:
        return None
    try:
        parts = t.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        return None
    return None

CANONICAL_VENUES = {
    "blaise": "Blaise Castle, Bristol",
    "llandaff": "Llandaff Fields, Cardiff",
    "pembrey": "Pembrey Country Park",
    "newbridge": "Newbridge Fields, Bridgend",
    "penlan": "Brecon (Penlan)",
    "brecon leisure": "Brecon (Penlan)",
    "pontypool": "Pontypool Park",
    "pont-y-pwl": "Pontypool Park",
    "margam": "Margam Park, Port Talbot",
    "singleton": "Singleton Park, Swansea",
    "bath": "University of Bath",
    "parc bryn bach": "Parc Bryn Bach",
    "chepstow": "Chepstow Racecourse",
    "parc de pugh": "Parc de Pugh, Brecon",
    "glebelands": "Glebelands, Newport",
    "monmouth": "Monmouth Showground",
}

VENUE_DESCRIPTIONS = {
    "Blaise Castle, Bristol": {
        "region": "Bristol / West of England",
        "terrain": "Historic estate parkland, steep wooded inclines, heavy winter mud, and open meadow stretches.",
        "tagline": "The historic cornerstone of the English fixture calendar."
    },
    "Llandaff Fields, Cardiff": {
        "region": "Cardiff / Glamorgan",
        "terrain": "Flat, wide, high-speed grass parkland bordering the River Taff. Ideal for relentless tempo racing.",
        "tagline": "The league's premier pure speedway."
    },
    "Pembrey Country Park": {
        "region": "Carmarthenshire / West Wales",
        "terrain": "Coastal dunes, pine forest sandy tracks, undulating grassland, and exposed maritime winds.",
        "tagline": "The iconic West Wales coastal challenge."
    },
    "Newbridge Fields, Bridgend": {
        "region": "Bridgend / Glamorgan",
        "terrain": "Riverside parkland loops featuring traditional bog sections, sharp ditch crossings, and sprint finishes.",
        "tagline": "Classic South Wales winter cross-country."
    },
    "Brecon (Penlan)": {
        "region": "Powys / Brecon Beacons",
        "terrain": "Exposed high-altitude hill loops with severe climbs, biting winds, and sweeping mountain panoramas.",
        "tagline": "The unforgiving mountain amphitheatre."
    },
    "Pontypool Park": {
        "region": "Torfaen / Gwent Valleys",
        "terrain": "Chamber of slopes: steep valley banks, dense wooded singletrack, and technical descents.",
        "tagline": "The true hills and valley tests of Gwent."
    },
    "Margam Park, Port Talbot": {
        "region": "Neath Port Talbot",
        "terrain": "Scenic Gothic castle grounds, steep deer park inclines, rough grass, and historic tree-lined avenues.",
        "tagline": "Grand castle vistas meet punishing climbs."
    },
    "Singleton Park, Swansea": {
        "region": "Swansea / South West Wales",
        "terrain": "Rolling botanical parkland overlooking Swansea Bay with steep punchy ascents.",
        "tagline": "Sea-view undulations and fast grass descents."
    },
    "University of Bath": {
        "region": "Bath / Somerset",
        "terrain": "High Claverton Down plateau, open sports field circuits, and exposed crosswinds.",
        "tagline": "Collegiate speed on Somerset's plateau."
    },
    "Parc Bryn Bach": {
        "region": "Blaenau Gwent / Heads of the Valleys",
        "terrain": "High-elevation country park circuit encircling the lake, rugged terrain, cold mountain air, and exposed lakeside straights.",
        "tagline": "The high-altitude stronghold of the Green Army."
    },
    "Chepstow Racecourse": {
        "region": "Monmouthshire",
        "terrain": "Expansive thoroughbred turf, deceptive undulations, wide galloping straights, and deep ground.",
        "tagline": "Galloping turf built for sustained power."
    },
    "Parc de Pugh, Brecon": {
        "region": "Powys / Brecon",
        "terrain": "Traditional recreational riverside turf in historic Brecon town.",
        "tagline": "Historic rural turf fixture."
    },
    "Glebelands, Newport": {
        "region": "Newport / Gwent",
        "terrain": "Low-lying tidal riverbank meadows prone to extreme winter waterlogging.",
        "tagline": "The ultimate mud-bath."
    },
    "Monmouth Showground": {
        "region": "Monmouthshire / Wye Valley",
        "terrain": "River Wye floodplain meadow pasture, completely flat with heavy suction clay.",
        "tagline": "Classic river-basin trial."
    }
}

def get_canonical_venue(raw):
    if not raw:
        return "Unknown Venue"
    lower = raw.lower()
    for key, canon in CANONICAL_VENUES.items():
        if key in lower:
            return canon
    return raw.strip()

def main():
    print("Building Venue Profiles and Course Records...")
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    venues = defaultdict(lambda: {
        "name": "",
        "region": "",
        "terrain": "",
        "tagline": "",
        "total_finishes": 0,
        "fixtures": {},
        "men_records": [],
        "women_records": [],
        "men_winners": defaultdict(int),
        "women_winners": defaultdict(int)
    })

    for r in records:
        raw_v = r.get("venue")
        if not raw_v:
            continue
        c_venue = get_canonical_venue(raw_v)
        v_obj = venues[c_venue]
        v_obj["name"] = c_venue
        v_obj["total_finishes"] += 1

        # Track fixture
        fix_key = f"{r['season_key']}_m{r['match']}"
        if fix_key not in v_obj["fixtures"]:
            v_obj["fixtures"][fix_key] = {
                "season": r["season"],
                "season_key": r["season_key"],
                "match": r["match"],
                "date": r.get("date", ""),
                "starters": 0,
                "men_starters": 0,
                "women_starters": 0,
                "men_winner": None,
                "women_winner": None
            }
        
        fix = v_obj["fixtures"][fix_key]
        fix["starters"] += 1
        if r["gender"] == "M":
            fix["men_starters"] += 1
            if r["pos"] == 1:
                fix["men_winner"] = {"athlete": r["athlete"], "club": r["club"], "time": r.get("time", "")}
                v_obj["men_winners"][r["athlete"]] += 1
        else:
            fix["women_starters"] += 1
            if r["pos"] == 1:
                fix["women_winner"] = {"athlete": r["athlete"], "club": r["club"], "time": r.get("time", "")}
                v_obj["women_winners"][r["athlete"]] += 1

        # Track times for course records
        t_sec = parse_time_sec(r.get("time"))
        if t_sec and 900 <= t_sec <= 4200:
            item = {
                "athlete": r["athlete"],
                "club": r["club"],
                "time": r["time"],
                "sec": t_sec,
                "season": r["season"],
                "season_key": r["season_key"],
                "match": r["match"],
                "pos": r["pos"]
            }
            if r["gender"] == "M":
                v_obj["men_records"].append(item)
            else:
                v_obj["women_records"].append(item)

    # Format output
    result = []
    for c_venue, v_obj in sorted(venues.items(), key=lambda x: len(x[1]["fixtures"]), reverse=True):
        desc = VENUE_DESCRIPTIONS.get(c_venue, {
            "region": "South Wales / West",
            "terrain": "Classic cross-country parkland.",
            "tagline": "Traditional Gwent League racing."
        })

        # Top 10 fastest times
        m_top10 = sorted(v_obj["men_records"], key=lambda x: x["sec"])[:10]
        w_top10 = sorted(v_obj["women_records"], key=lambda x: x["sec"])[:10]

        # Best course record
        m_cr = m_top10[0] if m_top10 else None
        w_cr = w_top10[0] if w_top10 else None

        # Most successful winners
        m_top_winners = sorted(v_obj["men_winners"].items(), key=lambda x: x[1], reverse=True)[:5]
        w_top_winners = sorted(v_obj["women_winners"].items(), key=lambda x: x[1], reverse=True)[:5]

        # Fixture list sorted chronologically descending
        fix_list = sorted(v_obj["fixtures"].values(), key=lambda x: (x["season_key"], x["match"]), reverse=True)

        result.append({
            "name": c_venue,
            "region": desc["region"],
            "terrain": desc["terrain"],
            "tagline": desc["tagline"],
            "fixture_count": len(fix_list),
            "total_finishes": v_obj["total_finishes"],
            "men_course_record": m_cr,
            "women_course_record": w_cr,
            "men_top10": m_top10,
            "women_top10": w_top10,
            "men_most_wins": [{"athlete": name, "wins": count} for name, count in m_top_winners],
            "women_most_wins": [{"athlete": name, "wins": count} for name, count in w_top_winners],
            "fixtures": fix_list
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write("window.VENUE_PROFILES = ")
        json.dump(result, f, indent=2)
        f.write(";\n")

    print(f"Generated profiles for {len(result)} canonical venues.")
    print(f"Saved to {OUTPUT_JSON} and {OUTPUT_JS}")

if __name__ == "__main__":
    main()
