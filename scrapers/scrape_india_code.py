"""
India Code Central Statute Scraper v3
======================================
Verified against live site July 2026.

Key findings from live analysis:
1. India Code runs DSpace 5.5
2. Central Acts collection handle = 1362
3. Each act = a DSpace item page at /handle/123456789/{handle}?sam_handle=123456789/1362
4. The meta-citation_pdf_url tag in the item page <head> gives the canonical PDF URL
5. CRITICAL: same act appears under multiple handles (central + state copies).
   Must use sam_handle=123456789/1362 to stay in central acts collection.
6. Search within central acts ONLY: /handle/123456789/1362/simple-search?query=...

Strategy per act:
  - If known_handle set: fetch item page directly, extract citation_pdf_url from <head>
  - Else: search within central collection, pick best match, fetch item page
  - Download PDF, verify first-page text matches expected title
  - Save only on successful verification

Usage:
    pip install httpx beautifulsoup4 pymupdf
    python scrape_india_code.py --output corpus/raw/statutes/
    python scrape_india_code.py --acts ipc,ni_act --output corpus/raw/statutes/
    python scrape_india_code.py --check --output corpus/raw/statutes/
    python scrape_india_code.py --list
"""

import argparse
import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("india_code")

BASE = "https://www.indiacode.nic.in"
CENTRAL_HANDLE = "1362"
RATE = 2.5  # seconds between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# ---------------------------------------------------------------------------
# Act registry
# known_handle: verified central-collection DSpace item handle (from live lookup)
# title_match:  lowercase substrings checked in PDF first 3 pages (ANY must match)
# min_pages:    sanity floor (allows 50% tolerance for versioning differences)
# search_terms: used when known_handle is None to find the act
# ---------------------------------------------------------------------------
ACTS = {
    # CRIMINAL
    "ipc": {
        "title": "The Indian Penal Code, 1860",
        "known_handle": "2263",           # verified: central, sam_handle=1362
        "title_match": ["indian penal code"],
        "min_pages": 100,
        "search_terms": "Indian Penal Code 1860",
    },
    "crpc": {
        "title": "The Code of Criminal Procedure, 1973",
        "known_handle": "16225",          # verified: central, sam_handle=1362
        "title_match": ["code of criminal procedure"],
        "min_pages": 150,
        "search_terms": "Code of Criminal Procedure 1973",
    },
    "evidence_act": {
        "title": "The Indian Evidence Act, 1872",
        "known_handle": None,
        "title_match": ["indian evidence act"],
        "min_pages": 30,
        "search_terms": "Indian Evidence Act 1872",
    },
    "bns": {
        "title": "The Bharatiya Nyaya Sanhita, 2023",
        "known_handle": None,
        "title_match": ["bharatiya nyaya sanhita"],
        "min_pages": 80,
        "search_terms": "Bharatiya Nyaya Sanhita 2023",
    },
    "bnss": {
        "title": "The Bharatiya Nagarik Suraksha Sanhita, 2023",
        "known_handle": None,
        "title_match": ["bharatiya nagarik suraksha sanhita"],
        "min_pages": 80,
        "search_terms": "Bharatiya Nagarik Suraksha Sanhita 2023",
    },
    "bsa": {
        "title": "The Bharatiya Sakshya Adhiniyam, 2023",
        "known_handle": None,
        "title_match": ["bharatiya sakshya adhiniyam"],
        "min_pages": 20,
        "search_terms": "Bharatiya Sakshya Adhiniyam 2023",
    },
    "ndps": {
        "title": "The Narcotic Drugs and Psychotropic Substances Act, 1985",
        "known_handle": None,
        "title_match": ["narcotic drugs and psychotropic substances"],
        "min_pages": 40,
        "search_terms": "Narcotic Drugs and Psychotropic Substances Act 1985",
    },
    "arms_act": {
        "title": "The Arms Act, 1959",
        "known_handle": None,
        "title_match": ["arms act"],
        "min_pages": 15,
        "search_terms": "Arms Act 1959",
    },
    "prevention_corruption": {
        "title": "The Prevention of Corruption Act, 1988",
        "known_handle": None,
        "title_match": ["prevention of corruption act"],
        "min_pages": 15,
        "search_terms": "Prevention of Corruption Act 1988",
    },
    "pmla": {
        "title": "The Prevention of Money-Laundering Act, 2002",
        "known_handle": None,
        "title_match": ["prevention of money-laundering", "prevention of money laundering"],
        "min_pages": 30,
        "search_terms": "Prevention of Money Laundering Act 2002",
    },
    # CIVIL AND CONTRACT
    "contract_act": {
        "title": "The Indian Contract Act, 1872",
        "known_handle": None,
        "title_match": ["indian contract act"],
        "min_pages": 15,
        "search_terms": "Indian Contract Act 1872",
    },
    "cpc": {
        "title": "The Code of Civil Procedure, 1908",
        "known_handle": None,
        "title_match": ["code of civil procedure"],
        "min_pages": 100,
        "search_terms": "Code of Civil Procedure 1908",
    },
    "specific_relief": {
        "title": "The Specific Relief Act, 1963",
        "known_handle": None,
        "title_match": ["specific relief act"],
        "min_pages": 15,
        "search_terms": "Specific Relief Act 1963",
    },
    "limitation_act": {
        "title": "The Limitation Act, 1963",
        "known_handle": None,
        "title_match": ["limitation act"],
        "min_pages": 20,
        "search_terms": "Limitation Act 1963",
    },
    "transfer_property": {
        "title": "The Transfer of Property Act, 1882",
        "known_handle": None,
        "title_match": ["transfer of property act"],
        "min_pages": 30,
        "search_terms": "Transfer of Property Act 1882",
    },
    "registration_act": {
        "title": "The Registration Act, 1908",
        "known_handle": None,
        "title_match": ["registration act"],
        "min_pages": 20,
        "search_terms": "Registration Act 1908",
    },
    "stamp_act": {
        "title": "The Indian Stamp Act, 1899",
        "known_handle": "20095",          # verified: central bitstream confirmed
        "title_match": ["indian stamp act"],
        "min_pages": 20,
        "search_terms": "Indian Stamp Act 1899",
    },
    # COMMERCIAL AND CORPORATE
    "companies_act": {
        "title": "The Companies Act, 2013",
        "known_handle": "2114",           # verified: bitstream 2114/5/A2013-18.pdf
        "title_match": ["companies act, 2013", "the companies act"],
        "min_pages": 200,
        "search_terms": "Companies Act 2013",
    },
    "ibc": {
        "title": "The Insolvency and Bankruptcy Code, 2016",
        "known_handle": None,
        "title_match": ["insolvency and bankruptcy code"],
        "min_pages": 80,
        "search_terms": "Insolvency and Bankruptcy Code 2016",
    },
    "ni_act": {
        "title": "The Negotiable Instruments Act, 1881",
        "known_handle": "2189",           # verified: central, sam_handle=1362
        "title_match": ["negotiable instruments act"],
        "min_pages": 20,
        "search_terms": "Negotiable Instruments Act 1881",
    },
    "sebi_act": {
        "title": "The Securities and Exchange Board of India Act, 1992",
        "known_handle": None,
        "title_match": ["securities and exchange board of india act"],
        "min_pages": 25,
        "search_terms": "Securities Exchange Board India Act 1992",
    },
    "competition_act": {
        "title": "The Competition Act, 2002",
        "known_handle": None,
        "title_match": ["competition act"],
        "min_pages": 30,
        "search_terms": "Competition Act 2002",
    },
    "fema": {
        "title": "The Foreign Exchange Management Act, 1999",
        "known_handle": None,
        "title_match": ["foreign exchange management act"],
        "min_pages": 20,
        "search_terms": "Foreign Exchange Management Act 1999",
    },
    "banking_act": {
        "title": "The Banking Regulation Act, 1949",
        "known_handle": None,
        "title_match": ["banking regulation act"],
        "min_pages": 60,
        "search_terms": "Banking Regulation Act 1949",
    },
    "rbi_act": {
        "title": "The Reserve Bank of India Act, 1934",
        "known_handle": "2398",           # verified: bitstream a1934-2.pdf
        "title_match": ["reserve bank of india act"],
        "min_pages": 30,
        "search_terms": "Reserve Bank of India Act 1934",
    },
    "msme_act": {
        "title": "The Micro, Small and Medium Enterprises Development Act, 2006",
        "known_handle": None,
        "title_match": ["micro, small and medium enterprises"],
        "min_pages": 10,
        "search_terms": "Micro Small Medium Enterprises Development Act 2006",
    },
    # PROPERTY AND REAL ESTATE
    "rera": {
        "title": "The Real Estate (Regulation and Development) Act, 2016",
        "known_handle": None,
        "title_match": ["real estate (regulation and development)"],
        "min_pages": 30,
        "search_terms": "Real Estate Regulation Development Act 2016",
    },
    "motor_vehicles": {
        "title": "The Motor Vehicles Act, 1988",
        "known_handle": None,
        "title_match": ["motor vehicles act"],
        "min_pages": 100,
        "search_terms": "Motor Vehicles Act 1988",
    },
    # INTELLECTUAL PROPERTY
    "patents_act": {
        "title": "The Patents Act, 1970",
        "known_handle": None,
        "title_match": ["patents act"],
        "min_pages": 60,
        "search_terms": "Patents Act 1970",
    },
    "copyright_act": {
        "title": "The Copyright Act, 1957",
        "known_handle": None,
        "title_match": ["copyright act"],
        "min_pages": 40,
        "search_terms": "Copyright Act 1957",
    },
    "trademark_act": {
        "title": "The Trade Marks Act, 1999",
        "known_handle": None,
        "title_match": ["trade marks act"],
        "min_pages": 50,
        "search_terms": "Trade Marks Act 1999",
    },
    # TAX
    "income_tax": {
        "title": "The Income-tax Act, 1961",
        "known_handle": None,
        "title_match": ["income-tax act", "income tax act"],
        "min_pages": 200,
        "search_terms": "Income-tax Act 1961",
    },
    "cgst": {
        "title": "The Central Goods and Services Tax Act, 2017",
        "known_handle": None,
        "title_match": ["central goods and services tax"],
        "min_pages": 60,
        "search_terms": "Central Goods and Services Tax Act 2017",
    },
    "igst": {
        "title": "The Integrated Goods and Services Tax Act, 2017",
        "known_handle": None,
        "title_match": ["integrated goods and services tax"],
        "min_pages": 10,
        "search_terms": "Integrated Goods and Services Tax Act 2017",
    },
    "customs_act": {
        "title": "The Customs Act, 1962",
        "known_handle": None,
        "title_match": ["customs act"],
        "min_pages": 80,
        "search_terms": "Customs Act 1962",
    },
    # LABOUR
    "labour_code": {
        "title": "The Industrial Relations Code, 2020",
        "known_handle": None,
        "title_match": ["industrial relations code"],
        "min_pages": 40,
        "search_terms": "Industrial Relations Code 2020",
    },
    "factories_act": {
        "title": "The Factories Act, 1948",
        "known_handle": None,
        "title_match": ["factories act"],
        "min_pages": 40,
        "search_terms": "Factories Act 1948",
    },
    # CONSTITUTIONAL AND RIGHTS
    "constitution": {
        "title": "The Constitution of India",
        "known_handle": "16124",          # verified: bitstream 16124/1/the_constitution_of_india.pdf
        "title_match": ["constitution of india"],
        "min_pages": 200,
        "search_terms": "Constitution of India",
    },
    "right_to_information": {
        "title": "The Right to Information Act, 2005",
        "known_handle": None,
        "title_match": ["right to information act"],
        "min_pages": 15,
        "search_terms": "Right to Information Act 2005",
    },
    "domestic_violence": {
        "title": "The Protection of Women from Domestic Violence Act, 2005",
        "known_handle": None,
        "title_match": ["protection of women from domestic violence"],
        "min_pages": 10,
        "search_terms": "Protection of Women Domestic Violence Act 2005",
    },
    "pocso": {
        "title": "The Protection of Children from Sexual Offences Act, 2012",
        "known_handle": None,
        "title_match": ["protection of children from sexual offences"],
        "min_pages": 15,
        "search_terms": "Protection of Children Sexual Offences Act 2012",
    },
    "sc_st_act": {
        "title": "The Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989",
        "known_handle": None,
        "title_match": ["scheduled castes and the scheduled tribes", "scheduled castes and scheduled tribes"],
        "min_pages": 15,
        "search_terms": "Scheduled Castes Scheduled Tribes Prevention Atrocities Act 1989",
    },
    # TECHNOLOGY AND DATA
    "it_act": {
        "title": "The Information Technology Act, 2000",
        "known_handle": "13116",          # verified: bitstream 13116/1/it_act_2000_updated.pdf
        "title_match": ["information technology act"],
        "min_pages": 10,
        "search_terms": "Information Technology Act 2000",
    },
    "digital_personal_data": {
        "title": "The Digital Personal Data Protection Act, 2023",
        "known_handle": None,
        "title_match": ["digital personal data protection"],
        "min_pages": 15,
        "search_terms": "Digital Personal Data Protection Act 2023",
    },
    "telecom_act": {
        "title": "The Telecommunications Act, 2023",
        "known_handle": None,
        "title_match": ["telecommunications act"],
        "min_pages": 20,
        "search_terms": "Telecommunications Act 2023",
    },
    # ENVIRONMENT AND RESOURCES
    "environment_protection": {
        "title": "The Environment (Protection) Act, 1986",
        "known_handle": None,
        "title_match": ["environment (protection) act", "environment protection act"],
        "min_pages": 10,
        "search_terms": "Environment Protection Act 1986",
    },
    "forest_act": {
        "title": "The Indian Forest Act, 1927",
        "known_handle": None,
        "title_match": ["indian forest act"],
        "min_pages": 40,
        "search_terms": "Indian Forest Act 1927",
    },
    "electricity_act": {
        "title": "The Electricity Act, 2003",
        "known_handle": None,
        "title_match": ["electricity act"],
        "min_pages": 80,
        "search_terms": "Electricity Act 2003",
    },
    "explosive_act": {
        "title": "The Explosives Act, 1884",
        "known_handle": None,
        "title_match": ["explosives act"],
        "min_pages": 10,
        "search_terms": "Explosives Act 1884",
    },
    # DISPUTE RESOLUTION AND CONSUMER
    "arbitration_act": {
        "title": "The Arbitration and Conciliation Act, 1996",
        "known_handle": None,
        "title_match": ["arbitration and conciliation act"],
        "min_pages": 40,
        "search_terms": "Arbitration and Conciliation Act 1996",
    },
    "consumer_protection": {
        "title": "The Consumer Protection Act, 2019",
        "known_handle": None,
        "title_match": ["consumer protection act, 2019"],
        "min_pages": 30,
        "search_terms": "Consumer Protection Act 2019",
    },
}


class IndiaCodeScraper:
    def __init__(self, output_dir: str, verbose: bool = False):
        self.out = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out / "manifest.json"
        self.manifest: dict = (
            json.loads(self.manifest_path.read_text())
            if self.manifest_path.exists()
            else {}
        )
        if verbose:
            log.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------ #
    def _save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2))

    # ------------------------------------------------------------------ #
    # PDF verification: read first 3 pages, check title, check page count
    # ------------------------------------------------------------------ #
    def verify_pdf(self, data: bytes, meta: dict) -> tuple[bool, str]:
        if not data.startswith(b"%PDF"):
            return False, "not a PDF"
        if not HAS_FITZ:
            return len(data) > 50_000, "size-only (install pymupdf for content check)"
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            return False, f"corrupt PDF: {e}"
        pages = len(doc)
        text = "".join(doc[i].get_text() for i in range(min(3, pages))).lower()
        matches = [m for m in meta["title_match"] if m in text]
        if not matches:
            snippet = " ".join(text.split())[:100]
            return False, f"title mismatch — got: '{snippet}'"
        min_p = meta.get("min_pages", 1)
        if pages < min_p * 0.5:
            return False, f"too few pages ({pages}, expected ~{min_p})"
        return True, f"ok ({pages}pp, matched '{matches[0]}')"

    # ------------------------------------------------------------------ #
    # Get the canonical PDF URL from a DSpace item page <head>
    # meta-citation_pdf_url is the most reliable signal in DSpace 5.5
    # ------------------------------------------------------------------ #
    def _extract_pdf_url_from_item(self, html: str, handle: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls = []

        # Primary: citation_pdf_url meta tag (DSpace canonical)
        meta = soup.find("meta", {"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            urls.append(meta["content"].replace("http://", "https://"))

        # Secondary: all bitstream links in the page body for this handle
        for a in soup.select(f"a[href*='/bitstream/123456789/{handle}/']"):
            href = a.get("href", "")
            if href.lower().endswith(".pdf"):
                full = urljoin(BASE, href).replace("http://", "https://")
                if full not in urls:
                    urls.append(full)

        # Tertiary: any bitstream PDF links on the page
        for a in soup.select("a[href*='/bitstream/']"):
            href = a.get("href", "")
            if href.lower().endswith(".pdf"):
                full = urljoin(BASE, href).replace("http://", "https://")
                if full not in urls:
                    urls.append(full)

        return urls

    # ------------------------------------------------------------------ #
    # Search within CENTRAL ACTS ONLY and return candidate handles
    # ------------------------------------------------------------------ #
    async def _search_central(
        self, client: httpx.AsyncClient, search_terms: str
    ) -> list[str]:
        """
        Search within /handle/123456789/1362/ — central acts only.
        Returns a list of candidate item handles.
        """
        url = (
            f"{BASE}/handle/123456789/{CENTRAL_HANDLE}/simple-search"
            f"?query={quote(search_terms)}&sort_by=score&order=desc&rpp=10"
        )
        log.debug(f"  Searching: {url}")
        try:
            r = await client.get(url, timeout=30)
            await asyncio.sleep(RATE)
            if r.status_code != 200:
                log.debug(f"  Search HTTP {r.status_code}")
                return []
            soup = BeautifulSoup(r.text, "html.parser")
            handles = []
            seen = set()
            for a in soup.select("a[href*='/handle/123456789/']"):
                href = a.get("href", "")
                m = re.search(r"/handle/123456789/(\d+)", href)
                if not m:
                    continue
                h = m.group(1)
                if h == CENTRAL_HANDLE or h in seen:
                    continue
                seen.add(h)
                handles.append(h)
            log.debug(f"  Found candidate handles: {handles[:6]}")
            return handles[:6]
        except Exception as e:
            log.debug(f"  Search error: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Fetch item page and get PDF URLs, ensuring it's a central act
    # ------------------------------------------------------------------ #
    async def _get_pdf_urls_for_handle(
        self, client: httpx.AsyncClient, handle: str, force_central: bool = True
    ) -> list[str]:
        # Always request with sam_handle to ensure we're in central context
        url = (
            f"{BASE}/handle/123456789/{handle}"
            f"?sam_handle=123456789%2F{CENTRAL_HANDLE}"
        )
        log.debug(f"  Item page: {url}")
        try:
            r = await client.get(url, timeout=30)
            await asyncio.sleep(RATE)
            if r.status_code != 200:
                log.debug(f"  Item page HTTP {r.status_code}")
                return []
            # Verify it's a central act, not a state copy
            if force_central:
                soup = BeautifulSoup(r.text, "html.parser")
                type_meta = soup.find("meta", {"name": "DC.type"})
                dc_type = type_meta.get("content", "").upper() if type_meta else ""
                if dc_type == "STATE":
                    log.debug(f"  Handle {handle} is a STATE copy — skipping")
                    return []
            return self._extract_pdf_url_from_item(r.text, handle)
        except Exception as e:
            log.debug(f"  Item page error: {e}")
            return []

    # ------------------------------------------------------------------ #
    # Download + verify a PDF from a URL
    # ------------------------------------------------------------------ #
    async def _download_and_verify(
        self, client: httpx.AsyncClient, pdf_url: str, meta: dict
    ) -> tuple[bool, bytes, str]:
        try:
            log.debug(f"  Downloading: {pdf_url}")
            r = await client.get(pdf_url, timeout=120, follow_redirects=True)
            await asyncio.sleep(RATE)
            if r.status_code != 200:
                return False, b"", f"HTTP {r.status_code}"
            data = r.content
            ok, reason = self.verify_pdf(data, meta)
            return ok, data, reason
        except Exception as e:
            return False, b"", str(e)

    # ------------------------------------------------------------------ #
    # Main: download one act
    # ------------------------------------------------------------------ #
    async def download_act(
        self,
        client: httpx.AsyncClient,
        key: str,
        meta: dict,
        force: bool = False,
    ) -> bool:
        fp = self.out / f"{key}.pdf"

        # Skip if already verified
        if fp.exists() and not force:
            entry = self.manifest.get(key, {})
            if entry.get("verified"):
                log.info(f"[SKIP] {key}: already verified ({entry.get('verify_note','')})")
                return True

        log.info(f"[GET] {key}: {meta['title']}")

        # --- Step 1: get PDF URLs ---
        pdf_urls: list[str] = []

        if meta.get("known_handle"):
            handle = meta["known_handle"]
            log.debug(f"  known handle: {handle}")
            pdf_urls = await self._get_pdf_urls_for_handle(client, handle, force_central=False)
        else:
            # Search central collection
            handles = await self._search_central(client, meta["search_terms"])
            for h in handles:
                urls = await self._get_pdf_urls_for_handle(client, h, force_central=True)
                if urls:
                    pdf_urls = urls
                    log.debug(f"  using handle {h} -> {len(urls)} PDF URL(s)")
                    break

        if not pdf_urls:
            log.warning(f"  [FAIL] {key}: no PDF URLs found")
            return False

        # --- Step 2: try each PDF URL, verify ---
        for pdf_url in pdf_urls:
            ok, data, reason = await self._download_and_verify(client, pdf_url, meta)
            if ok:
                fp.write_bytes(data)
                entry = {
                    "key": key,
                    "title": meta["title"],
                    "filename": fp.name,
                    "pdf_url": pdf_url,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "verified": True,
                    "verify_note": reason,
                    "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self.manifest[key] = entry
                self._save_manifest()
                log.info(f"  [OK] {key}: {reason}")
                return True
            else:
                log.debug(f"  verify failed ({pdf_url}): {reason}")

        log.warning(f"  [FAIL] {key}: all URLs failed verification")
        return False

    # ------------------------------------------------------------------ #
    # Run all (or subset)
    # ------------------------------------------------------------------ #
    async def run(self, acts: list[str] | None = None, force: bool = False) -> dict:
        targets = {k: ACTS[k] for k in (acts or ACTS.keys()) if k in ACTS}
        if acts:
            unknown = [k for k in acts if k not in ACTS]
            if unknown:
                log.warning(f"Unknown keys: {unknown}")

        log.info(f"Starting: {len(targets)} acts → {self.out}")

        ok, fail = [], []
        async with httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=httpx.Timeout(120.0, connect=20.0),
        ) as client:
            for key, meta in targets.items():
                success = await self.download_act(client, key, meta, force=force)
                (ok if success else fail).append(key)

        log.info(f"\n{'='*55}")
        log.info(f"Done: {len(ok)} succeeded, {len(fail)} failed")
        if fail:
            log.warning("\nFailed — manual download needed:")
            for k in fail:
                log.warning(f"  {k}: '{ACTS[k]['title']}'")
                log.warning(f"    Search: {BASE}/handle/123456789/{CENTRAL_HANDLE}/simple-search?query={quote(ACTS[k]['search_terms'])}")
        return {"ok": ok, "failed": fail}

    # ------------------------------------------------------------------ #
    # Verify existing files on disk
    # ------------------------------------------------------------------ #
    def check(self):
        if not HAS_FITZ:
            log.error("Install pymupdf first: pip install pymupdf")
            return
        ok, wrong, missing = [], [], []
        for key, meta in ACTS.items():
            fp = self.out / f"{key}.pdf"
            if not fp.exists():
                missing.append(key)
                continue
            v, reason = self.verify_pdf(fp.read_bytes(), meta)
            (ok if v else wrong).append(f"{key}: {reason}")

        log.info(f"\n{'='*55}")
        log.info(f"CHECK: {len(ok)} correct | {len(wrong)} wrong | {len(missing)} missing")
        for x in ok:
            log.info(f"  ✓ {x}")
        for x in wrong:
            log.warning(f"  ✗ {x}")
        for x in missing:
            log.warning(f"  - {x}")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Download Indian central acts from India Code")
    p.add_argument("--output", "-o", default="corpus/raw/statutes",
                   help="Output directory (default: corpus/raw/statutes)")
    p.add_argument("--acts", "-a", default="all",
                   help="Comma-separated act keys or 'all' (default: all)")
    p.add_argument("--force", "-f", action="store_true",
                   help="Re-download even if already verified")
    p.add_argument("--check", "-c", action="store_true",
                   help="Verify existing files without downloading")
    p.add_argument("--list", "-l", action="store_true",
                   help="List all act keys and exit")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    if args.list:
        w = max(len(k) for k in ACTS)
        print(f"\n{'Key':<{w}}  Title")
        print("-" * (w + 60))
        for k, v in ACTS.items():
            h = v.get("known_handle") or "-"
            print(f"{k:<{w}}  [{h:>6}]  {v['title']}")
        return

    scraper = IndiaCodeScraper(args.output, verbose=args.verbose)

    if args.check:
        scraper.check()
        return

    acts = None if args.acts == "all" else args.acts.split(",")
    asyncio.run(scraper.run(acts=acts, force=args.force))


if __name__ == "__main__":
    main()
