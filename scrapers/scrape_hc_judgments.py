"""
High Court Important Judgment Scraper
=======================================
Scrapes IMPORTANT cases only from 5 High Courts using topic-based search.
"Important" = cited by many other courts (high "cited by" count on Indian Kanoon)
                + substantive judgment (not a routine order)
                + minimum length threshold

Outputs as PDF files structured by court.

Usage:
    pip install httpx beautifulsoup4 fpdf2
    python scrape_hc_judgments.py --output corpus/raw/cases/hc/
"""

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from fpdf import FPDF

# Ensure Windows terminal prints utf-8 without crashing
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Disable httpx internal logging
logging.getLogger("httpx").setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hc_scraper")

BASE = "https://indiankanoon.org"
RATE = 3.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://indiankanoon.org/",
}

COURTS = {
    "delhi": {
        "name": "Delhi High Court",
        "doctype": "delhihighcourt",
        "verify_phrases": ["high court of delhi", "in the high court of delhi"],
        "target": 50,
        "min_cited_by": 5,
        "min_chars": 5000,
        "topics": [
            "trademark infringement passing off doctypes:delhihighcourt",
            "patent infringement validity doctypes:delhihighcourt",
            "copyright infringement fair use doctypes:delhihighcourt",
            "dynamic injunction piracy website blocking doctypes:delhihighcourt",
            "section 34 arbitration award set aside doctypes:delhihighcourt",
            "section 11 arbitration appointment arbitrator doctypes:delhihighcourt",
            "enforcement foreign arbitral award doctypes:delhihighcourt",
            "section 138 negotiable instruments cheque dishonour doctypes:delhihighcourt",
            "specific performance contract injunction doctypes:delhihighcourt",
            "commercial suit interim injunction doctypes:delhihighcourt",
            "insolvency bankruptcy code section 7 financial creditor doctypes:delhihighcourt",
            "article 226 writ mandamus natural justice doctypes:delhihighcourt",
            "right to information RTI section 8 exemption doctypes:delhihighcourt",
        ],
    },
    "bombay": {
        "name": "Bombay High Court",
        "doctype": "bombayHighCourt",
        "verify_phrases": ["high court", "bombay", "in the high court at bombay"],
        "target": 50,
        "min_cited_by": 5,
        "min_chars": 5000,
        "topics": [
            "companies act oppression mismanagement section 241 doctypes:bombayHighCourt",
            "NCLT appeal company winding up doctypes:bombayHighCourt",
            "SEBI securities market fraud insider trading doctypes:bombayHighCourt",
            "insolvency resolution plan liquidation doctypes:bombayHighCourt",
            "section 7 section 9 IBC financial operational creditor doctypes:bombayHighCourt",
            "specific performance injunction contract breach doctypes:bombayHighCourt",
            "force majeure frustration contract doctypes:bombayHighCourt",
            "section 34 arbitration commercial doctypes:bombayHighCourt",
            "enforcement arbitration award foreign seated doctypes:bombayHighCourt",
            "section 138 cheque bounce negotiable instruments doctypes:bombayHighCourt",
            "copyright film music infringement doctypes:bombayHighCourt",
            "RERA real estate developer homebuyer possession doctypes:bombayHighCourt",
        ],
    },
    "karnataka": {
        "name": "Karnataka High Court",
        "doctype": "karnatakahighcourt",
        "verify_phrases": ["high court of karnataka", "karnataka high court"],
        "target": 50,
        "min_cited_by": 3,
        "min_chars": 4000,
        "topics": [
            "information technology act cyber crime doctypes:karnatakahighcourt",
            "digital personal data privacy doctypes:karnatakahighcourt",
            "software copyright IT services doctypes:karnatakahighcourt",
            "industrial disputes labour termination workman doctypes:karnatakahighcourt",
            "Karnataka Shops Establishments Act employment doctypes:karnatakahighcourt",
            "land acquisition compensation doctypes:karnatakahighcourt",
            "RERA real estate possession refund doctypes:karnatakahighcourt",
            "registration stamp duty property transfer doctypes:karnatakahighcourt",
            "article 226 writ mandamus Karnataka doctypes:karnatakahighcourt",
            "right to education article 21A doctypes:karnatakahighcourt",
            "section 138 cheque dishonour NI Act doctypes:karnatakahighcourt",
            "MSME arbitration dispute doctypes:karnatakahighcourt",
            "bail anticipatory bail section 438 doctypes:karnatakahighcourt",
            "FIR quashing section 482 CrPC doctypes:karnatakahighcourt",
        ],
    },
    "madras": {
        "name": "Madras High Court",
        "doctype": "madrasHighCourt",
        "verify_phrases": ["high court", "madras", "madurai bench"],
        "target": 50,
        "min_cited_by": 3,
        "min_chars": 4000,
        "topics": [
            "trademark passing off geographical indication doctypes:madrasHighCourt",
            "copyright film music sound recording doctypes:madrasHighCourt",
            "patent revocation invalidity doctypes:madrasHighCourt",
            "consumer protection deficiency service compensation doctypes:madrasHighCourt",
            "medical negligence consumer forum doctypes:madrasHighCourt",
            "section 138 cheque dishonour territorial jurisdiction doctypes:madrasHighCourt",
            "workman reinstatement industrial tribunal doctypes:madrasHighCourt",
            "contract labour abolition doctypes:madrasHighCourt",
            "land acquisition LARR compensation doctypes:madrasHighCourt",
            "registration act fraudulent transfer doctypes:madrasHighCourt",
            "article 226 government employment reservation doctypes:madrasHighCourt",
            "right to information appeal doctypes:madrasHighCourt",
            "section 34 arbitration Madras doctypes:madrasHighCourt",
        ],
    },
    "calcutta": {
        "name": "Calcutta High Court",
        "doctype": "calcuttaHighCourt",
        "verify_phrases": ["high court", "calcutta", "calcutta high court"],
        "target": 50,
        "min_cited_by": 3,
        "min_chars": 4000,
        "topics": [
            "arbitration commercial dispute section 34 doctypes:calcuttaHighCourt",
            "enforcement foreign award New York Convention doctypes:calcuttaHighCourt",
            "companies act winding up oppression mismanagement doctypes:calcuttaHighCourt",
            "NCLT IBC insolvency resolution doctypes:calcuttaHighCourt",
            "industrial disputes workman retrenchment closure doctypes:calcuttaHighCourt",
            "Employees Provident Fund ESI contribution doctypes:calcuttaHighCourt",
            "section 138 cheque dishonour negotiable instruments doctypes:calcuttaHighCourt",
            "tenancy rent control eviction West Bengal doctypes:calcuttaHighCourt",
            "land acquisition compensation Kolkata doctypes:calcuttaHighCourt",
            "article 226 writ natural justice Calcutta doctypes:calcuttaHighCourt",
            "contract specific performance damages doctypes:calcuttaHighCourt",
            "insurance claim repudiation doctypes:calcuttaHighCourt",
        ],
    },
}


class HCImportantScraper:
    def __init__(self, output_dir: str, verbose: bool = False):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out / "manifest.json"
        self.manifest: dict = (
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest_path.exists() else {}
        )
        self.downloaded_ids: set = {
            v.get("kanoon_id", "") for v in self.manifest.values()
        }
        if verbose:
            log.setLevel(logging.DEBUG)

    def _save(self):
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")

    def _parse_cited_by(self, snippet_html: str) -> int:
        m = re.search(r"Cited by\s+(\d+)", snippet_html, re.I)
        return int(m.group(1)) if m else 0

    def _extract(self, html: str) -> tuple[str, str, str]:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        case_name = re.sub(r"\s*-\s*Indian Kanoon.*$", "", page_title, flags=re.I).strip()
        date_m = re.search(r"\bon (\d+ \w+ \d{4})$", case_name)
        date_str = date_m.group(1) if date_m else ""
        if date_str:
            case_name = case_name[:date_m.start()].strip()
        div = (
            soup.find("div", {"id": "judgments"})
            or soup.find("div", class_="judgments")
            or soup.find("div", {"id": "main"})
        )
        if not div:
            return "", case_name, date_str
        return div.get_text(separator="\n", strip=True), case_name, date_str

    def _verify(self, text: str, court_meta: dict) -> tuple[bool, str]:
        min_chars = court_meta["min_chars"]
        if len(text) < min_chars:
            return False, f"too short ({len(text):,} < {min_chars:,})"

        head = text[:3000].lower()
        if not any(p in head for p in court_meta["verify_phrases"]):
            return False, "court name not found"

        if len(text) < 8000:
            substantive_signals = ["held", "it is held", "we hold", "judgment", 
                                   "the court holds", "disposed of", "accordingly"]
            if not any(s in head for s in substantive_signals):
                return False, "appears to be procedural order"
        return True, f"ok ({len(text):,} chars)"

    async def _search_topic(self, client: httpx.AsyncClient, query: str, max_pages: int = 3) -> list[tuple[str, int]]:
        results = []
        seen = set()

        for page in range(max_pages):
            url = f"{BASE}/search/?formInput={quote(query)}&pagenum={page}"
            try:
                r = await client.get(url, timeout=30)
                await asyncio.sleep(RATE)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")

                found_any = False
                for a in soup.select("a[href^='/doc/']"):
                    m = re.search(r"/doc/(\d+)/", a.get("href", ""))
                    if not m or m.group(1) in seen:
                        continue
                    doc_id = m.group(1)
                    seen.add(doc_id)
                    found_any = True

                    parent = a.find_parent()
                    cited_by = 0
                    for _ in range(5):
                        if parent:
                            cited_by = self._parse_cited_by(str(parent))
                            if cited_by > 0:
                                break
                            parent = parent.find_parent()
                    results.append((doc_id, cited_by))
                if not found_any:
                    break
            except Exception as e:
                log.debug(f"  search error: {e}")
                break
        results.sort(key=lambda x: -x[1])
        return results

    async def _fetch_doc(self, client: httpx.AsyncClient, doc_id: str) -> tuple[str, str, str]:
        try:
            r = await client.get(f"{BASE}/doc/{doc_id}/", timeout=30)
            await asyncio.sleep(RATE)
            if r.status_code != 200:
                return "", "", ""
            return self._extract(r.text)
        except Exception as e:
            log.debug(f"  doc {doc_id}: {e}")
            return "", "", ""

    async def scrape_court(self, court_key: str) -> int:
        if court_key not in COURTS:
            return 0

        meta = COURTS[court_key]
        target = meta["target"]
        min_cited = meta["min_cited_by"]

        already = sum(1 for v in self.manifest.values() if v.get("court_key") == court_key and v.get("verified"))
        if already >= target:
            log.info(f"[{court_key}] Already have {already}/{target}")
            return already

        needed = target - already
        log.info(f"\n[{court_key.upper()}] {meta['name']}")
        log.info(f"  Target: {target} | Have: {already} | Need: {needed}")

        saved = 0
        folder = self.out / court_key
        folder.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            for topic_query in meta["topics"]:
                if saved >= needed:
                    break

                log.info(f"  Topic: {topic_query.split('doctypes')[0].strip()}")
                candidates = await self._search_topic(client, topic_query, max_pages=2)
                good = [(did, cb) for did, cb in candidates if cb >= min_cited]
                low = [(did, cb) for did, cb in candidates if cb < min_cited and cb >= 0]

                for doc_id, cited_by in (good + low):
                    if saved >= needed:
                        break
                    if doc_id in self.downloaded_ids:
                        continue

                    text, case_name, date_str = await self._fetch_doc(client, doc_id)
                    if not text:
                        continue
                    ok, reason = self._verify(text, meta)
                    if not ok:
                        continue

                    year_m = re.search(r"\d{4}$", date_str)
                    year = int(year_m.group()) if year_m else 0
                    key = f"hc_{court_key}_{doc_id}"

                    # Generate PDF using FPDF
                    fp = folder / f"{key}.pdf"
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("helvetica", size=11)
                    safe_text = text.encode("latin-1", "ignore").decode("latin-1")
                    safe_name = case_name.encode("latin-1", "ignore").decode("latin-1")
                    pdf.multi_cell(0, 5, text=f"{safe_name}\n\n{safe_text}")
                    pdf.output(str(fp))

                    entry = {
                        "case_key": key,
                        "name": case_name,
                        "year": year,
                        "court": meta["name"],
                        "court_key": court_key,
                        "filename": fp.name,
                        "folder": court_key,
                        "kanoon_id": doc_id,
                        "cited_by": cited_by,
                        "topic_query": topic_query,
                        "char_count": len(text),
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "verified": True,
                        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    self.manifest[key] = entry
                    self.downloaded_ids.add(doc_id)
                    self._save()
                    saved += 1
                    log.info(f"  [{saved}/{needed}] cited_by={cited_by:>5} {case_name[:50]} ({len(text):,} chars)")

        return already + saved

    async def scrape_all(self, courts: list[str] | None = None):
        targets = courts or list(COURTS.keys())
        results = {}
        for court_key in targets:
            n = await self.scrape_court(court_key)
            results[court_key] = n
        self.status()
        return results

    def status(self):
        total = len(self.manifest)
        log.info(f"\n{'='*60}")
        log.info(f"Total HC cases: {total}")
        for ck, meta in COURTS.items():
            n = sum(1 for v in self.manifest.values() if v.get("court_key") == ck)
            t = meta["target"]
            log.info(f"  {ck:<12} {n:>3}/{t}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--courts", "-c", default="all")
    p.add_argument("--output", "-o", default="corpus/raw/cases/hc")
    p.add_argument("--status", "-s", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    s = HCImportantScraper(args.output, verbose=args.verbose)
    if args.status:
        s.status()
        return
    courts = None if args.courts == "all" else args.courts.split(",")
    asyncio.run(s.scrape_all(courts=courts))


if __name__ == "__main__":
    main()
