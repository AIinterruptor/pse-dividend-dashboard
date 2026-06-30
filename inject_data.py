#!/usr/bin/env python3
"""
Reads data.json produced by scraper.py and injects it into index.html,
replacing the DATA array so the dashboard always reflects live scraped data.
"""
import json
import re

with open("data.json") as f:
    payload = json.load(f)

divs = payload.get("dividends", [])
generated = payload.get("generated", "")

# Build JS array
lines = ["const DATA = ["]
for d in divs:
    company = d.get("company", d.get("ticker", ""))
    notes = d.get("notes", "")
    lines.append(
        f'  {{ ticker:{json.dumps(d["ticker"])}, company:{json.dumps(company)}, '
        f'sector:{json.dumps(d.get("sector","Other"))}, dps:{d.get("dps",0)}, '
        f'annual:{d.get("annual", d.get("dps",0))}, yield:{d.get("yield","null")}, '
        f'exDate:{json.dumps(d.get("exDate",""))}, payDate:{json.dumps(d.get("payDate",""))}, '
        f'freq:{json.dumps(d.get("freq","Annual"))}, status:{json.dumps(d.get("status","past"))}, '
        f'notes:{json.dumps(notes)} }},'
    )
lines.append("];")
new_data_block = "\n".join(lines)

with open("index.html") as f:
    html = f.read()

# Replace DATA array in script block
html = re.sub(r"const DATA = \[[\s\S]*?\];", new_data_block, html, count=1)

# Update generated date in header meta
html = re.sub(
    r'Reference Date: <span>[^<]*</span>',
    f'Reference Date: <span>{generated}</span>',
    html
)

with open("index.html", "w") as f:
    f.write(html)

print(f"Injected {len(divs)} dividend records into index.html (as of {generated})")
