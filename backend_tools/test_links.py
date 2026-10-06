import urllib.request
import re
import os
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_URL = "https://www.gwent-league.org.uk/"
headers = {"User-Agent": "Mozilla/5.0"}

def fetch(url):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='replace')

test_urls = [
    "2025/res251.htm",
    "2021/res211.htm",
    "2018/res181.htm",
    "2014/res141.htm",
    "2010/res101.htm"
]

for rel in test_urls:
    url = BASE_URL + rel
    html = fetch(url)
    print(f"\n--- Checking {rel} ---")
    
    # Look for links with 'Individuals' or sm/sl
    # In table: Novice, U13, ..., Senior Men, Senior Women, etc.
    links = re.findall(r'<A\s+HREF=["\']([^"\']+)["\']>([^<]+)</A>', html, re.I)
    
    sm_links = [l for l in links if re.search(r'sm\d+i\.htm', l[0], re.I) or 'senior men' in l[1].lower()]
    sl_links = [l for l in links if re.search(r'(sl|sw)\d+i\.htm', l[0], re.I) or 'senior' in l[1].lower() and 'women' in l[1].lower()]
    masters_m = [l for l in links if re.search(r'sm(35|40|45|50|55|60|65|70)\d+i\.htm', l[0], re.I)]
    masters_f = [l for l in links if re.search(r'(sl|sw|mw)(35|40|45|50|55|60|65|70)\d+i\.htm', l[0], re.I)]
    
    print(f"SM links: {sm_links}")
    print(f"SL links: {sl_links}")
    print(f"Masters M links: {[l[0] for l in masters_m]}")
    print(f"Masters F links: {[l[0] for l in masters_f]}")
