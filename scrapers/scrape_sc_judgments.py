"""
Supreme Court Judgment Scraper v2
===================================
Source: Indian Kanoon (indiankanoon.org)
Target: ~5,000 SC judgments for Themis Machina RAG corpus

Confirmed URL structure (July 2026):
  Browse:  /browse/supremecourt/{year}/{month}/
  Search:  /search/?formInput=doctypes:supremecourt year:{year}&pagenum={n}
  Doc:     /doc/{id}/
  PDF:     button #pdfdoc on the doc page

Strategy:
  TWO MODES:
  1. --mode priority  : downloads the curated landmark case list (22 cases)
                        uses search-by-name + party-name verification
  2. --mode bulk      : crawls by year/month, downloads all SC judgments
                        filters: min length + "Supreme Court of India" in header
                        targets 5,000 cases across 2010-2025

  Both modes:
  - Save full text as JSON (not PDF — text is better for RAG chunking)
  - Verify every document is actually an SC judgment before saving
  - Idempotent: skip already downloaded doc IDs
  - Rate limited: 3.5s between requests

Usage:
    pip install httpx beautifulsoup4
    
    # Download the 22 landmark cases first
    python scrape_sc_judgments.py --mode priority --output corpus/raw/cases/sc/
    
    # Then bulk-scrape by year (run one year at a time)
    python scrape_sc_judgments.py --mode bulk --year 2024 --output corpus/raw/cases/sc/
    python scrape_sc_judgments.py --mode bulk --year 2023 --output corpus/raw/cases/sc/
    # ... repeat for 2010-2025 to reach 5,000 cases
    
    # Check status
    python scrape_sc_judgments.py --status --output corpus/raw/cases/sc/

Legal: Indian Kanoon ToS permits research/personal use. No commercial use.
       Rate limited to 1 request / 3.5s. Save text, not PDFs, to reduce load.
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
log = logging.getLogger("sc_scraper")

BASE = "https://indiankanoon.org"
RATE = 3.5  # seconds between requests — be respectful

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/124.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://indiankanoon.org/",
}

# ---------------------------------------------------------------------------
# Priority landmark cases
# verify_terms: party names that MUST appear in first 2000 chars
# min_chars: minimum text length for a genuine full judgment
# ---------------------------------------------------------------------------
PRIORITY_CASES = {
    "kesavananda_bharati_1973": {
        "name": "Kesavananda Bharati v. State of Kerala",
        "citation": "(1973) 4 SCC 225",
        "year": 1973,
        "tags": ["constitution", "basic_structure"],
        "search": "Kesavananda Bharati State Kerala basic structure constitution",
        "verify_terms": ["kesavananda", "bharati"],
        "min_chars": 100000,
    },
    "minerva_mills_1980": {
        "name": "Minerva Mills Ltd. v. Union of India",
        "citation": "(1980) 3 SCC 625",
        "year": 1980,
        "tags": ["constitution", "basic_structure"],
        "search": "Minerva Mills Union India basic structure forty-second amendment",
        "verify_terms": ["minerva mills"],
        "min_chars": 30000,
    },
    "maneka_gandhi_1978": {
        "name": "Maneka Gandhi v. Union of India",
        "citation": "(1978) 1 SCC 248",
        "year": 1978,
        "tags": ["constitution", "article_21"],
        "search": "Maneka Gandhi Union India passport personal liberty article 21",
        "verify_terms": ["maneka gandhi"],
        "min_chars": 20000,
    },
    "puttaswamy_2017": {
        "name": "Justice K.S. Puttaswamy v. Union of India",
        "citation": "(2017) 10 SCC 1",
        "year": 2017,
        "tags": ["constitution", "privacy"],
        "search": "Puttaswamy Union India right to privacy nine judge bench",
        "verify_terms": ["puttaswamy"],
        "min_chars": 50000,
    },
    "navtej_singh_johar_2018": {
        "name": "Navtej Singh Johar v. Union of India",
        "citation": "(2018) 10 SCC 1",
        "year": 2018,
        "tags": ["constitution", "section_377"],
        "search": "Navtej Singh Johar Union India section 377 IPC",
        "verify_terms": ["navtej", "johar"],
        "min_chars": 50000,
    },
    "adm_jabalpur_1976": {
        "name": "ADM Jabalpur v. Shivakant Shukla",
        "citation": "(1976) 2 SCC 521",
        "year": 1976,
        "tags": ["constitution", "emergency"],
        "search": "ADM Jabalpur Shivakant Shukla habeas corpus emergency detention",
        "verify_terms": ["jabalpur", "shivakant"],
        "min_chars": 15000,
    },
    "shayara_bano_2017": {
        "name": "Shayara Bano v. Union of India",
        "citation": "(2017) 9 SCC 1",
        "year": 2017,
        "tags": ["constitution", "triple_talaq"],
        "search": "Shayara Bano Union India triple talaq talaq-e-biddat",
        "verify_terms": ["shayara bano"],
        "min_chars": 50000,
    },
    "essar_steel_2019": {
        "name": "CoC of Essar Steel v. Satish Kumar Gupta",
        "citation": "(2020) 8 SCC 531",
        "year": 2019,
        "tags": ["ibc", "insolvency"],
        "search": "Committee Creditors Essar Steel Satish Kumar Gupta equitable distribution",
        "verify_terms": ["essar steel"],
        "min_chars": 40000,
    },
    "swiss_ribbons_2019": {
        "name": "Swiss Ribbons v. Union of India",
        "citation": "(2019) 4 SCC 17",
        "year": 2019,
        "tags": ["ibc"],
        "search": "Swiss Ribbons Union India IBC constitutional validity financial creditor",
        "verify_terms": ["swiss ribbons"],
        "min_chars": 30000,
    },
    "vidarbha_industries_2022": {
        "name": "Vidarbha Industries Power v. Axis Bank",
        "citation": "(2022) 8 SCC 352",
        "year": 2022,
        "tags": ["ibc"],
        "search": "Vidarbha Industries Power Axis Bank section 7 IBC discretion",
        "verify_terms": ["vidarbha"],
        "min_chars": 20000,
    },
    "satyabrata_ghose_1954": {
        "name": "Satyabrata Ghose v. Mugneeram Bangur",
        "citation": "AIR 1954 SC 44",
        "year": 1954,
        "tags": ["contract", "frustration"],
        "search": "Satyabrata Ghose Mugneeram Bangur frustration contract section 56",
        "verify_terms": ["satyabrata"],
        "min_chars": 10000,
    },
    "energy_watchdog_2017": {
        "name": "Energy Watchdog v. CERC",
        "citation": "(2017) 14 SCC 80",
        "year": 2017,
        "tags": ["contract", "force_majeure"],
        "search": "Energy Watchdog CERC force majeure frustration power purchase agreement",
        "verify_terms": ["energy watchdog"],
        "min_chars": 15000,
    },
    "dashrath_rupsingh_2014": {
        "name": "Dashrath Rupsingh Rathod v. State of Maharashtra",
        "citation": "(2014) 9 SCC 129",
        "year": 2014,
        "tags": ["ni_act", "section_138"],
        "search": "Dashrath Rupsingh Rathod Maharashtra section 138 territorial jurisdiction",
        "verify_terms": ["dashrath", "rupsingh"],
        "min_chars": 15000,
    },
    "smt_selvi_2010": {
        "name": "Selvi v. State of Karnataka",
        "citation": "(2010) 7 SCC 263",
        "year": 2010,
        "tags": ["criminal", "article_20"],
        "search": "Selvi State Karnataka narco analysis brain mapping self incrimination",
        "verify_terms": ["selvi"],
        "min_chars": 20000,
    },
    "lalita_kumari_2013": {
        "name": "Lalita Kumari v. Govt of UP",
        "citation": "(2014) 2 SCC 1",
        "year": 2013,
        "tags": ["criminal", "fir"],
        "search": "Lalita Kumari Uttar Pradesh FIR mandatory registration cognizable offence",
        "verify_terms": ["lalita kumari"],
        "min_chars": 20000,
    },
    "arnesh_kumar_2014": {
        "name": "Arnesh Kumar v. State of Bihar",
        "citation": "(2014) 8 SCC 273",
        "year": 2014,
        "tags": ["criminal", "arrest"],
        "search": "Arnesh Kumar State Bihar section 498A arrest guidelines checklist",
        "verify_terms": ["arnesh kumar"],
        "min_chars": 8000,
    },
    "d_k_basu_1997": {
        "name": "D.K. Basu v. State of West Bengal",
        "citation": "(1997) 1 SCC 416",
        "year": 1997,
        "tags": ["criminal", "custody"],
        "search": "D K Basu State West Bengal arrest custody torture guidelines",
        "verify_terms": ["basu"],
        "min_chars": 15000,
    },
    "cbse_v_aditya_2011": {
        "name": "CBSE v. Aditya Bandopadhyay",
        "citation": "(2011) 8 SCC 497",
        "year": 2011,
        "tags": ["rti"],
        "search": "CBSE Aditya Bandopadhyay answer sheets right information education",
        "verify_terms": ["aditya bandopadhyay", "bandopadhyay"],
        "min_chars": 10000,
    },
    "suraj_lamp_2012": {
        "name": "Suraj Lamp v. State of Haryana",
        "citation": "(2012) 1 SCC 656",
        "year": 2012,
        "tags": ["property"],
        "search": "Suraj Lamp Industries State Haryana power of attorney sale deed",
        "verify_terms": ["suraj lamp"],
        "min_chars": 8000,
    },
    "cci_v_bharti_airtel_2019": {
        "name": "CCI v. Bharti Airtel",
        "citation": "(2019) 2 SCC 521",
        "year": 2019,
        "tags": ["competition", "telecom"],
        "search": "Competition Commission India Bharti Airtel jurisdiction telecom sector",
        "verify_terms": ["bharti airtel"],
        "min_chars": 20000,
    },
    "bharat_aluminium_2012": {
        "name": "Bharat Aluminium v. Kaiser Aluminium",
        "citation": "(2012) 9 SCC 552",
        "year": 2012,
        "tags": ["arbitration"],
        "search": "Bharat Aluminium Kaiser arbitration Part I applicability international",
        "verify_terms": ["bharat aluminium", "kaiser"],
        "min_chars": 30000,
    },
    "ssangyong_2019": {
        "name": "Ssangyong Engineering v. NHAI",
        "citation": "(2019) 15 SCC 131",
        "year": 2019,
        "tags": ["arbitration"],
        "search": "Ssangyong Engineering Construction NHAI arbitration public policy patent illegality",
        "verify_terms": ["ssangyong"],
        "min_chars": 20000,
    },
}

# ---------------------------------------------------------------------------
# Bulk scrape config: which years and how many cases per year
# Prioritizes recent + high-citation-count years
# ---------------------------------------------------------------------------
BULK_YEARS = {
    # year: target_cases
    2024: 500, 2023: 500, 2022: 400, 2021: 300, 2020: 300,
    2019: 300, 2018: 300, 2017: 300, 2016: 200, 2015: 200,
    2014: 200, 2013: 200, 2012: 200, 2011: 200, 2010: 200,
}


class SCScraper:
    def __init__(self, output_dir: str, verbose: bool = False):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out / "manifest.json"
        self.manifest: dict = (
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest_path.exists() else {}
        )
        # Track downloaded doc IDs to skip duplicates
        self.downloaded_ids: set = {
            v.get("kanoon_id", "") for v in self.manifest.values()
        }
        if verbose:
            log.setLevel(logging.DEBUG)

    def _save(self):
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Extract judgment text from an Indian Kanoon doc page
    # ------------------------------------------------------------------ #
    def _extract(self, html: str) -> tuple[str, str, str]:
        """Returns (full_text, case_name, date_str)"""
        soup = BeautifulSoup(html, "html.parser")

        # Title from <title> tag: "Party A vs Party B on DD Month YYYY"
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        # Strip " - Indian Kanoon" suffix
        case_name = re.sub(r"\s*-\s*Indian Kanoon.*$", "", page_title, flags=re.I).strip()
        # Extract date from title
        date_m = re.search(r"on (\d+ \w+ \d{4})$", case_name)
        date_str = date_m.group(1) if date_m else ""
        if date_str:
            case_name = case_name[:date_m.start()].strip()

        # Main judgment text
        div = (
            soup.find("div", {"id": "judgments"})
            or soup.find("div", class_="judgments")
            or soup.find("div", {"id": "main"})
            or soup.find("div", class_="doc")
        )
        if not div:
            return "", case_name, date_str

        text = div.get_text(separator="\n", strip=True)
        return text, case_name, date_str

    # ------------------------------------------------------------------ #
    # Verify a fetched document is genuinely an SC judgment
    # ------------------------------------------------------------------ #
    def _verify_sc(self, text: str, case_name: str, min_chars: int = 3000) -> tuple[bool, str]:
        if len(text) < min_chars:
            return False, f"too short ({len(text):,} chars < {min_chars:,})"
        head = text[:3000].lower()
        if "supreme court of india" not in head and "supreme court" not in head[:500].lower():
            return False, "not SC — 'Supreme Court of India' not in first 3000 chars"
        return True, f"ok ({len(text):,} chars)"

    def _verify_priority(self, text: str, case_name: str, meta: dict) -> tuple[bool, str]:
        """Stricter verification for priority cases — checks party names."""
        ok, reason = self._verify_sc(text, case_name, meta["min_chars"])
        if not ok:
            return False, reason
        head = (text[:3000] + " " + case_name).lower()
        matched = [t for t in meta["verify_terms"] if t in head or t in text[:6000].lower()]
        if not matched:
            return False, f"party name mismatch — expected {meta['verify_terms']}"
        return True, f"ok ({len(text):,} chars, matched '{matched[0]}')"

    # ------------------------------------------------------------------ #
    # Fetch a doc page and return text
    # ------------------------------------------------------------------ #
    async def _fetch_doc(self, client: httpx.AsyncClient, doc_id: str) -> tuple[str, str, str]:
        url = f"{BASE}/doc/{doc_id}/"
        try:
            r = await client.get(url, timeout=30)
            await asyncio.sleep(RATE)
            if r.status_code != 200:
                log.debug(f"  doc {doc_id}: HTTP {r.status_code}")
                return "", "", ""
            return self._extract(r.text)
        except Exception as e:
            log.debug(f"  doc {doc_id}: {e}")
            return "", "", ""

    # ------------------------------------------------------------------ #
    # Search Indian Kanoon and return doc IDs
    # ------------------------------------------------------------------ #
    async def _search(
        self, client: httpx.AsyncClient, query: str, max_pages: int = 3
    ) -> list[str]:
        ids = []
        seen = set()
        for page in range(max_pages):
            url = f"{BASE}/search/?formInput={quote(query)}&pagenum={page}"
            try:
                r = await client.get(url, timeout=30)
                await asyncio.sleep(RATE)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                found = 0
                for a in soup.select("a[href^='/doc/']"):
                    m = re.search(r"/doc/(\d+)/", a.get("href", ""))
                    if m and m.group(1) not in seen:
                        seen.add(m.group(1))
                        ids.append(m.group(1))
                        found += 1
                if found == 0:
                    break
            except Exception as e:
                log.debug(f"  search error: {e}")
                break
        return ids

    # ------------------------------------------------------------------ #
    # Save a verified case
    # ------------------------------------------------------------------ #
    def _save_case(self, key: str, doc_id: str, text: str, case_name: str,
                   date_str: str, year: int, tags: list, citation: str = "") -> dict:
        if key.startswith("sc_"):
            folder = self.out / str(year)
        else:
            folder = self.out / "landmark"
        folder.mkdir(parents=True, exist_ok=True)
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
            "citation": citation,
            "year": year,
            "filename": fp.name,
            "folder": str(folder.name),
            "kanoon_id": doc_id,
            "char_count": len(text),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "verified": True,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.manifest[key] = entry
        self.downloaded_ids.add(doc_id)
        self._save()
        return entry

    # ------------------------------------------------------------------ #
    # MODE 1: Priority landmark cases
    # ------------------------------------------------------------------ #
    async def scrape_priority(self, only: list[str] | None = None) -> dict:
        targets = {k: v for k, v in PRIORITY_CASES.items()
                   if not only or k in only}
        ok, fail = [], []

        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0)
        ) as client:
            for key, meta in targets.items():
                if self.manifest.get(key, {}).get("verified"):
                    log.info(f"[SKIP] {key}: already downloaded")
                    ok.append(key)
                    continue

                log.info(f"[PRIORITY] {key}: {meta['name']}")
                # Search for the case
                ids = await self._search(
                    client,
                    f"{meta['search']} doctypes:supremecourt",
                    max_pages=3
                )
                if not ids:
                    log.warning(f"  no search results for {key}")
                    fail.append(key)
                    continue

                # Try each result until one passes verification
                saved = False
                for doc_id in ids[:6]:
                    if doc_id in self.downloaded_ids:
                        continue
                    text, case_name, date_str = await self._fetch_doc(client, doc_id)
                    if not text:
                        continue
                    ok_flag, reason = self._verify_priority(text, case_name, meta)
                    log.debug(f"  doc {doc_id}: {reason}")
                    if ok_flag:
                        self._save_case(
                            key, doc_id, text, case_name, date_str,
                            meta["year"], meta["tags"], meta["citation"]
                        )
                        log.info(f"  OK {key}: {reason}")
                        ok.append(key)
                        saved = True
                        break

                if not saved:
                    log.warning(f"  FAIL {key}: no result passed verification")
                    log.warning(f"    Manual: search '{meta['name']}' at indiankanoon.org")
                    fail.append(key)

        log.info(f"\n{'='*55}\nPriority: {len(ok)} ok, {len(fail)} failed")
        return {"ok": ok, "failed": fail}

    # ------------------------------------------------------------------ #
    # MODE 2: Bulk scrape by year
    # ------------------------------------------------------------------ #
    async def scrape_year(self, year: int, target: int | None = None) -> int:
        target = target or BULK_YEARS.get(year, 200)
        log.info(f"[BULK] Year {year}: target {target} cases")

        # Count already downloaded for this year
        already = sum(
            1 for v in self.manifest.values()
            if v.get("year") == year and v.get("verified")
        )
        if already >= target:
            log.info(f"  Already have {already} cases for {year}, skipping")
            return already

        remaining = target - already
        log.info(f"  Already have {already}, need {remaining} more")

        saved = 0
        page = 0

        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0)
        ) as client:
            while saved < remaining:
                # Search for SC judgments for this year
                url = (
                    f"{BASE}/search/?formInput="
                    f"{quote(f'year:{year} doctypes:supremecourt')}"
                    f"&pagenum={page}"
                )
                try:
                    r = await client.get(url, timeout=30)
                    await asyncio.sleep(RATE)
                    if r.status_code != 200:
                        log.warning(f"  HTTP {r.status_code} at page {page}")
                        break
                    soup = BeautifulSoup(r.text, "html.parser")
                    doc_links = soup.select("a[href^='/doc/']")
                    if not doc_links:
                        log.info(f"  No more results at page {page}")
                        break

                    for a in doc_links:
                        if saved >= remaining:
                            break
                        m = re.search(r"/doc/(\d+)/", a.get("href", ""))
                        if not m:
                            continue
                        doc_id = m.group(1)
                        if doc_id in self.downloaded_ids:
                            continue

                        # Fetch the doc
                        text, case_name, date_str = await self._fetch_doc(client, doc_id)
                        if not text:
                            continue

                        ok_flag, reason = self._verify_sc(text, case_name)
                        if not ok_flag:
                            log.debug(f"  skip {doc_id}: {reason}")
                            continue

                        # Generate a key for bulk cases
                        key = f"sc_{year}_{doc_id}"
                        self._save_case(
                            key, doc_id, text, case_name, date_str,
                            year, [], ""
                        )
                        saved += 1
                        log.info(f"  [{already + saved}/{target}] {case_name[:60]} ({len(text):,} chars)")

                except Exception as e:
                    log.error(f"  Error at page {page}: {e}")
                    break

                page += 1

        total = already + saved
        log.info(f"  Year {year}: {total} total cases ({saved} new)")
        return total

    # ------------------------------------------------------------------ #
    # STATUS
    # ------------------------------------------------------------------ #
    def status(self):
        total = len(self.manifest)
        by_year: dict[int, int] = {}
        by_type = {"priority": 0, "bulk": 0}
        total_chars = 0

        for key, v in self.manifest.items():
            yr = v.get("year", 0)
            by_year[yr] = by_year.get(yr, 0) + 1
            total_chars += v.get("char_count", 0)
            if key.startswith("sc_"):
                by_type["bulk"] += 1
            else:
                by_type["priority"] += 1

        log.info(f"\n{'='*55}")
        log.info(f"Total cases: {total}")
        log.info(f"  Priority (landmark): {by_type['priority']}")
        log.info(f"  Bulk (year-crawl):   {by_type['bulk']}")
        log.info(f"  Total text: {total_chars / 1e6:.1f} MB")
        log.info(f"\nBy year:")
        for yr in sorted(by_year.keys(), reverse=True):
            target = BULK_YEARS.get(yr, "—")
            log.info(f"  {yr}: {by_year[yr]:>4} / {str(target):>4}")

        missing_priority = [k for k in PRIORITY_CASES if k not in self.manifest]
        if missing_priority:
            log.warning(f"\nMissing priority cases ({len(missing_priority)}):")
            for k in missing_priority:
                log.warning(f"  - {k}: {PRIORITY_CASES[k]['name']}")


def main():
    p = argparse.ArgumentParser(description="Scrape SC judgments from Indian Kanoon")
    p.add_argument("--mode", choices=["priority", "bulk", "status"], default="priority")
    p.add_argument("--output", "-o", default="corpus/raw/cases/sc")
    p.add_argument("--year", "-y", type=int, help="Year to scrape (bulk mode)")
    p.add_argument("--years", help="Comma-separated years e.g. 2024,2023,2022 (bulk mode)")
    p.add_argument("--target", "-t", type=int, help="Cases to download per year (bulk mode)")
    p.add_argument("--cases", help="Comma-separated priority case keys (priority mode)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    s = SCScraper(args.output, verbose=args.verbose)

    if args.mode == "status":
        s.status()
        return

    if args.mode == "priority":
        only = args.cases.split(",") if args.cases else None
        asyncio.run(s.scrape_priority(only=only))

    elif args.mode == "bulk":
        if args.years:
            years = [int(y.strip()) for y in args.years.split(",")]
        elif args.year:
            years = [args.year]
        else:
            # Default: most useful years first
            years = [2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017,
                     2016, 2015, 2014, 2013, 2012, 2011, 2010]

        total = 0
        for yr in years:
            n = asyncio.run(s.scrape_year(yr, target=args.target))
            total += n
            log.info(f"Running total: {total} cases")

        s.status()


if __name__ == "__main__":
    main()
