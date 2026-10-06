import os
import re
from bs4 import BeautifulSoup

RAW_DIR = "/Users/robgale/Documents/gl-archive/backend_tools/raw_html"

def test_parse_modern(filename):
    filepath = os.path.join(RAW_DIR, filename)
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id='tblIndividualPoints') or soup.find('table')
    if not table:
        print(f"No table found in {filename}")
        return

    rows = table.find_all('tr')
    print(f"\n--- Testing Modern: {filename} ({len(rows)} table rows) ---")
    parsed = 0
    for tr in rows[:8]:
        tds = tr.find_all('td')
        if not tds:
            continue
        
        cells = [td.get_text().strip() for td in tds]
        # Clean pos
        pos_raw = cells[0].replace('*', '').strip()
        if not pos_raw.isdigit():
            continue
        pos = int(pos_raw)
        
        name = cells[1] if len(cells) > 1 else ""
        age_tag = cells[2] if len(cells) > 2 else ""
        club = cells[3] if len(cells) > 3 else ""
        time_str = cells[4] if len(cells) > 4 else ""
        pts = cells[5] if len(cells) > 5 else ""

        print(f"  Pos: {pos:<3} | Name: {name:<22} | Age: {age_tag:<5} | Club: {club:<30} | Time: {time_str:<7} | Pts: {pts}")
        parsed += 1

def test_parse_legacy(filename):
    filepath = os.path.join(RAW_DIR, filename)
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    pre = soup.find('pre')
    if not pre:
        print(f"No <pre> tag found in {filename}")
        return

    text = pre.get_text()
    lines = text.split('\n')
    print(f"\n--- Testing Legacy: {filename} ({len(lines)} lines) ---")
    
    # Legacy line pattern:
    # Optional '*', then digits (pos), then athlete name, optional (age), club, time (e.g. 31.38), pts
    # Let's inspect raw lines
    for line in lines[:18]:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('Pos') or 'Starters' in line_clean or '---' in line_clean:
            continue
        
        # Regex to extract pos, time, points from end
        # End has: Time (e.g. \d{1,2}\.\d{2}) and Pts (digits or 'Guest')
        m = re.match(r'^\*?\s*(\d+)\s+(.+?)\s+(\d{1,2}[\.:]\d{2}(?:[\.:]\d{2})?)\s+(\d+|Guest|guest|-)?$', line_clean)
        if m:
            pos = int(m.group(1))
            middle = m.group(2).strip()
            time_str = m.group(3).strip()
            pts = m.group(4) or ""

            # In middle, we have: Athlete Name, optional (age_bracket/flags), Club
            # Check for (23), (35), (40), (45), (50), etc., or (ind)
            age_m = re.search(r'\s+\((\d{2})\)\s+', middle)
            if age_m:
                age_tag = f"({age_m.group(1)})"
                parts = middle.split(age_m.group(0), 1)
                name = parts[0].strip()
                club = parts[1].strip()
            else:
                # Could be (ind) or no age
                ind_m = re.search(r'\s+\(ind\)\s+', middle, re.I)
                if ind_m:
                    age_tag = ""
                    parts = middle.split(ind_m.group(0), 1)
                    name = parts[0].strip()
                    club = parts[1].strip()
                else:
                    # Let's see: how to separate name and club when no bracket?
                    # In legacy, columns were fixed width!
                    name = middle[:25].strip()
                    club = middle[25:].strip()
                    age_tag = ""

            print(f"  Pos: {pos:<3} | Name: {name:<20} | Age: {age_tag:<5} | Club: {club:<30} | Time: {time_str:<7} | Pts: {pts}")
        else:
            print(f"  [RAW LINE]: {line_clean}")

if __name__ == "__main__":
    test_parse_modern("2024_2025_m1_men.htm")
    test_parse_modern("2021_2022_m1_women.htm")
    test_parse_legacy("2018_2019_m1_men.htm")
    test_parse_legacy("2010_2011_m1_men.htm")
