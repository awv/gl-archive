import json
import re
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_JSON = os.path.join(PROJECT_DIR, "data.json")
TEAM_STANDINGS_JSON = os.path.join(PROJECT_DIR, "assets", "data", "team_standings.json")
CLUB_ALIASES_JSON = os.path.join(SCRIPT_DIR, "club_aliases.json")

HONOURS_JSON = os.path.join(PROJECT_DIR, "assets", "data", "club_team_honours.json")
HONOURS_JS = os.path.join(PROJECT_DIR, "assets", "data", "club_team_honours.js")
FIXTURE_DIV_JSON = os.path.join(PROJECT_DIR, "assets", "data", "fixture_team_standings.json")
FIXTURE_DIV_JS = os.path.join(PROJECT_DIR, "assets", "data", "fixture_team_standings.js")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_club_name(name, aliases):
    # Strip standalone B, C, D tags for canonical club mapping
    base = re.sub(r"\s+['\"‘’]?[B-Z]['\"‘’]?\s*$", "", name.strip(), flags=re.I).strip()
    return aliases.get(base, aliases.get(name, base))

def get_team_tier(name):
    # Match standalone letter or quoted letter like 'B' or 'C' at the end of the name
    m = re.search(r"\s+['\"‘’]?([B-Z])['\"‘’]?\s*$", name.strip(), flags=re.I)
    if m:
        return f"{m.group(1).upper()} Team"
    return "First Team"

def main():
    print("Building team summaries & honours...")
    runners = load_json(DATA_JSON)
    fixtures = load_json(TEAM_STANDINGS_JSON)
    aliases = load_json(CLUB_ALIASES_JSON)

    # Index runners by (season_key, match, gender, canonical_club)
    runners_by_fixture = defaultdict(list)
    for r in runners:
        c_club = r.get("club")
        if c_club:
            key = (r["season_key"], r["match"], r["gender"], c_club)
            runners_by_fixture[key].append(r)

    # Club honours structure
    # canonical_club -> { division_titles: [], match_wins: [] }
    club_honours = defaultdict(lambda: {
        "division_titles": [],
        "match_wins": []
    })

    # Fixture standings map
    fixture_standings_map = {}

    for fix in fixtures:
        season = fix["season"]
        season_key = fix["season_key"]
        match_num = fix["match"]
        venue = fix["venue"]
        date = fix["date"]
        fix_key = f"{season_key}_m{match_num}"

        fixture_standings_map[fix_key] = {
            "season": season,
            "season_key": season_key,
            "match": match_num,
            "venue": venue,
            "date": date,
            "divisions": fix["divisions"]
        }

        for div in fix["divisions"]:
            div_name = div["division"]
            gender = div["gender"]
            standings = div["standings"]
            if not standings:
                continue

            # Check for cumulative title (e.g. Champions on final match)
            for entry in standings:
                cum_pos_str = str(entry.get("cum_pos") or "")
                note_str = str(entry.get("note") or "")
                raw_team = entry["team"]
                c_club = clean_club_name(raw_team, aliases)
                tier = get_team_tier(raw_team)

                if "champion" in cum_pos_str.lower() or "champion" in note_str.lower():
                    club_honours[c_club]["division_titles"].append({
                        "season": season,
                        "division": div_name,
                        "gender": gender,
                        "tier": tier,
                        "title": "League Champions",
                        "pts": entry.get("cum_pts")
                    })
                elif "runner-up" in cum_pos_str.lower() or "runner-up" in note_str.lower() or "runners-up" in note_str.lower():
                    club_honours[c_club]["division_titles"].append({
                        "season": season,
                        "division": div_name,
                        "gender": gender,
                        "tier": tier,
                        "title": "Runners-Up",
                        "pts": entry.get("cum_pts")
                    })

            # Check match winner (pos == 1)
            first = standings[0]
            if first["pos"] == 1:
                # Handle ties: all entries with pos == 1
                winners = [s for s in standings if s["pos"] == 1]
                runner_up = next((s for s in standings if s["pos"] > 1), None)

                for winner in winners:
                    raw_team = winner["team"]
                    c_club = clean_club_name(raw_team, aliases)
                    tier = get_team_tier(raw_team)
                    win_pts = winner["pts"]

                    ru_name = clean_club_name(runner_up["team"], aliases) if runner_up else None
                    ru_pts = runner_up["pts"] if runner_up else None
                    margin = (win_pts - ru_pts) if runner_up else 0

                    # Find scoring runners for this club in this fixture
                    runner_key = (season_key, match_num, gender, c_club)
                    team_runners = runners_by_fixture.get(runner_key, [])
                    
                    # Sort by individual points descending
                    sorted_runners = sorted(team_runners, key=lambda x: x.get("pts", 0), reverse=True)
                    
                    # For Senior Men: top 5; Senior Women: top 4
                    num_scorers = 5 if gender == "M" else 4
                    scorers = []
                    if tier == "First Team":
                        scoring_slice = sorted_runners[:num_scorers]
                    elif tier == "B Team":
                        scoring_slice = sorted_runners[num_scorers:num_scorers*2]
                    elif tier == "C Team":
                        scoring_slice = sorted_runners[num_scorers*2:num_scorers*3]
                    else:
                        scoring_slice = sorted_runners[:num_scorers]

                    for r in scoring_slice:
                        scorers.append({
                            "athlete": r["athlete"],
                            "pos": r["pos"],
                            "time": r.get("time", ""),
                            "pts": r.get("pts", 0)
                        })

                    club_honours[c_club]["match_wins"].append({
                        "season": season,
                        "season_key": season_key,
                        "match": match_num,
                        "venue": venue,
                        "date": date,
                        "division": div_name,
                        "gender": gender,
                        "tier": tier,
                        "pts": win_pts,
                        "runner_up": ru_name,
                        "runner_up_pts": ru_pts,
                        "margin": margin,
                        "is_tied": len(winners) > 1,
                        "scorers": scorers
                    })

    # Save outputs
    with open(HONOURS_JSON, "w", encoding="utf-8") as f:
        json.dump(club_honours, f, indent=2)

    with open(HONOURS_JS, "w", encoding="utf-8") as f:
        f.write("window.CLUB_TEAM_HONOURS = ")
        json.dump(club_honours, f, indent=2)
        f.write(";\n")

    with open(FIXTURE_DIV_JSON, "w", encoding="utf-8") as f:
        json.dump(fixture_standings_map, f, indent=2)

    with open(FIXTURE_DIV_JS, "w", encoding="utf-8") as f:
        f.write("window.FIXTURE_TEAM_STANDINGS = ")
        json.dump(fixture_standings_map, f, indent=2)
        f.write(";\n")

    print(f"Generated honours for {len(club_honours)} clubs.")
    print(f"Generated fixture standings for {len(fixture_standings_map)} fixtures.")

if __name__ == "__main__":
    main()
