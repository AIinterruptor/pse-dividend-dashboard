#!/usr/bin/env python3
"""
PSE Dividend Dashboard Scraper
Fetches dividend data from PSE EDGE and updates data.json daily.
"""

import json
import re
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta

TODAY = date.today().isoformat()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
}

# ── PSE EDGE company list (dividend-relevant tickers) ────────────────────────
TICKERS = [
    "BDO","BPI","MBT","SECB","CHIB","EW","AUB","PNB","CBC",
    "SM","ALI","SMPH","RLC","FLI","MEG","VLL",
    "AREIT","MREIT","RCR","FILRT","CREIT","DDMPR","PREIT",
    "JFC","URC","CNPF","MONDE","RFM","EMI",
    "MER","AP","AEV",
    "TEL","GLO",
    "AC","AEV","AGI","JGS","GTCAP","LTG","SMC","DMC","ICT","MPI",
    "PGOLD","COSCO",
    "SGP","SBS","FNI","CEU","PSE",
]

SECTOR_MAP = {
    "BDO":"Banking","BPI":"Banking","MBT":"Banking","SECB":"Banking",
    "CHIB":"Banking","EW":"Banking","AUB":"Banking","PNB":"Banking","CBC":"Banking",
    "SM":"Holding","ALI":"Property","SMPH":"Property","RLC":"Property",
    "FLI":"Property","MEG":"Property","VLL":"Property",
    "AREIT":"REIT","MREIT":"REIT","RCR":"REIT","FILRT":"REIT",
    "CREIT":"REIT","DDMPR":"REIT","PREIT":"REIT",
    "JFC":"Food","URC":"Food","CNPF":"Food","MONDE":"Food","RFM":"Food","EMI":"Food",
    "MER":"Utilities","AP":"Utilities","AEV":"Utilities","SGP":"Utilities",
    "TEL":"Telco","GLO":"Telco",
    "AC":"Holding","AGI":"Holding","JGS":"Holding","GTCAP":"Holding",
    "LTG":"Holding","DMC":"Industrials","ICT":"Industrials","MPI":"Industrials",
    "SMC":"Diversified","PGOLD":"Retail","COSCO":"Retail",
    "SBS":"Industrials","FNI":"Mining","CEU":"Education","PSE":"Exchange",
}


def fetch_pse_edge_disclosures(company_id: str) -> list[dict]:
    """Query PSE EDGE for dividend-related disclosures for a company."""
    url = (
        f"https://edge.pse.com.ph/companyDisclosures/search.ax?"
        f"companyId={company_id}&keyword=cash+dividend&sortType=D&pageNo=1"
    )
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return []


def fetch_pse_company_list() -> list[dict]:
    """Fetch all listed companies from PSE EDGE."""
    url = "https://edge.pse.com.ph/companyPage/stockData.do?cmpy_id=&format=json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            return data if isinstance(data, list) else data.get("companies", [])
    except Exception:
        return []


def fetch_pse_dividends_page(ticker: str) -> str:
    """Scrape the PSE EDGE dividends page for a ticker symbol."""
    url = f"https://edge.pse.com.ph/companyPage/dividendHistory.do?cmpy_id={ticker}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_dividend_table(html: str, ticker: str) -> list[dict]:
    """Extract dividend rows from PSE EDGE HTML table."""
    records = []
    # Match table rows with dividend data
    row_pat = re.compile(
        r"<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>"
        r".*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>"
        r".*?<td[^>]*>(.*?)</td>.*?</tr>",
        re.DOTALL | re.IGNORECASE,
    )
    for m in row_pat.finditer(html):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in m.groups()]
        if len(cells) >= 4 and re.search(r"\d{4}", cells[0] or ""):
            try:
                records.append({
                    "ticker": ticker,
                    "exDate": cells[0].strip() if cells[0] else "",
                    "recordDate": cells[1].strip() if len(cells) > 1 else "",
                    "payDate": cells[2].strip() if len(cells) > 2 else "",
                    "dps": cells[3].strip() if len(cells) > 3 else "",
                    "type": cells[4].strip() if len(cells) > 4 else "Cash",
                })
            except (IndexError, ValueError):
                pass
    return records


def normalize_date(raw: str) -> str:
    """Parse various PH date formats to YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw


def days_from_today(d: str) -> int:
    try:
        dt = datetime.strptime(d, "%Y-%m-%d").date()
        return (dt - date.today()).days
    except ValueError:
        return 9999


def status_for(ex_date: str) -> str:
    d = days_from_today(ex_date)
    if d < 0:
        return "past"
    if d <= 30:
        return "urgent"
    if d <= 90:
        return "upcoming"
    return "future"


def scrape_all() -> list[dict]:
    """Main scrape loop across all tracked tickers."""
    results = []
    for ticker in TICKERS:
        print(f"  Fetching {ticker}...")
        html = fetch_pse_dividends_page(ticker)
        if not html:
            time.sleep(0.5)
            continue
        rows = parse_dividend_table(html, ticker)
        for row in rows[:6]:  # latest 6 declarations per ticker
            ex_raw = row.get("exDate", "")
            pay_raw = row.get("payDate", "")
            ex_norm = normalize_date(ex_raw) if ex_raw else ""
            pay_norm = normalize_date(pay_raw) if pay_raw else ""

            dps_raw = row.get("dps", "0").replace(",", "").replace("₱", "").strip()
            try:
                dps = float(dps_raw)
            except ValueError:
                dps = 0.0

            results.append({
                "ticker": ticker,
                "sector": SECTOR_MAP.get(ticker, "Other"),
                "dps": dps,
                "exDate": ex_norm,
                "payDate": pay_norm,
                "freq": "Quarterly",  # refined below by history pattern
                "status": status_for(ex_norm),
                "type": row.get("type", "Cash"),
            })
        time.sleep(0.3)
    return results


def infer_frequency(records: list[dict]) -> str:
    """Infer payment frequency from historical ex-dates."""
    dates = sorted(
        [r["exDate"] for r in records if r["exDate"]],
        reverse=True,
    )[:4]
    if len(dates) < 2:
        return "Annual"
    gaps = []
    for i in range(len(dates) - 1):
        try:
            d1 = datetime.strptime(dates[i], "%Y-%m-%d")
            d2 = datetime.strptime(dates[i + 1], "%Y-%m-%d")
            gaps.append(abs((d1 - d2).days))
        except ValueError:
            pass
    if not gaps:
        return "Annual"
    avg = sum(gaps) / len(gaps)
    if avg < 100:
        return "Quarterly"
    if avg < 200:
        return "Semi-Annual"
    return "Annual"


def build_output(raw: list[dict]) -> dict:
    """Group by ticker, pick most recent + upcoming, compute frequency."""
    by_ticker: dict[str, list[dict]] = {}
    for r in raw:
        by_ticker.setdefault(r["ticker"], []).append(r)

    output = []
    for ticker, records in by_ticker.items():
        freq = infer_frequency(records)
        for rec in records:
            rec["freq"] = freq
        # Most recent upcoming or latest past
        upcoming = [r for r in records if r["status"] in ("urgent", "upcoming", "future")]
        past = [r for r in records if r["status"] == "past"]
        for r in (upcoming or past[:1]):
            output.append(r)

    return {
        "generated": TODAY,
        "count": len(output),
        "dividends": sorted(output, key=lambda x: x.get("exDate") or "zzzz"),
    }


if __name__ == "__main__":
    print(f"PSE Dividend Scraper — {TODAY}")
    print("Scraping PSE EDGE...")
    raw = scrape_all()
    print(f"  Got {len(raw)} raw records")
    data = build_output(raw)
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written data.json ({data['count']} entries)")
