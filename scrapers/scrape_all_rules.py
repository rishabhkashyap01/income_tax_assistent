"""
Income Tax Rules Scraper
========================
Scrapes all 520+ Income Tax Rules from incometaxindia.gov.in

The government website is SharePoint-based with heavy JS rendering and
ASP.NET postback pagination — standard scrapers (crawl4ai, requests) fail.

Strategy:
  Phase 1 — Use Playwright to navigate the paginated rule listing and extract
             CMS IDs from each rule's onclick handler (openRuleViewer calls).
             Progress is saved after EVERY page so nothing is lost on crash.
  Phase 2 — Fetch each rule's .htm file directly via HTTP (no browser needed).
  Phase 3 — Convert HTML to clean markdown and save.

The CMS ID → .htm URL mapping:
  https://incometaxindia.gov.in/Rules/Income-tax%20Rules/{CMS_ID}.htm

Setup:
    pip install playwright requests beautifulsoup4 markdownify
    playwright install chromium

Usage:
    python scrapers/scrape_all_rules.py
    python scrapers/scrape_all_rules.py --force    # re-download existing files
    python scrapers/scrape_all_rules.py --skip-browser  # skip Phase 1 if index exists
"""

import asyncio
import argparse
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RULES_LISTING_URL = "https://incometaxindia.gov.in/Pages/rules/income-tax-rules-1962.aspx"
RULES_HTM_BASE = "https://incometaxindia.gov.in/Rules/Income-tax%20Rules/"
RULES_API_BASE = (
    "https://incometaxindia.gov.in/_vti_bin/taxmann.iti.webservices/"
    "DataWebService.svc/GetContentsByRuleNumber"
)

OUTPUT_DIR = os.path.join("data", "raw_markdown", "rules")
INDEX_FILE = os.path.join("data", "rules_index.json")

REQUEST_DELAY = 0.4          # seconds between HTTP requests (be polite)
PAGE_LOAD_WAIT = 4000        # ms to wait after pagination click
BROWSER_TIMEOUT = 60_000     # ms for initial page load
MAX_RETRIES = 3              # retries per page on failure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_index() -> list[dict]:
    """Load existing index file, or return empty list."""
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_index(rules: list[dict]):
    """Persist the index to disk immediately."""
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Phase 1 — Collect CMS IDs via Playwright
# ---------------------------------------------------------------------------
async def extract_rules_from_page(page):
    """Extract rule number, CMS ID and title from the current listing page."""
    rules = []
    divs = await page.query_selector_all("div.search_result")

    for div in divs:
        onclick = await div.get_attribute("onclick") or ""

        # Pattern: openRuleViewer('Rule', '<CMS_ID>', ...)
        m = re.search(r"openRuleViewer\(\s*'Rule'\s*,\s*'([^']+)'", onclick)
        if not m:
            continue
        cms_id = m.group(1)

        # Rule number — inside <h3 class="search_title"><a>Rule - 2BA</a></h3>
        title_el = await div.query_selector("h3.search_title a")
        rule_text = (await title_el.inner_text()).strip() if title_el else ""
        rule_number = rule_text.replace("Rule - ", "").replace("Rule -", "").strip()

        # Description — <p class="text-1 ...">
        desc_el = await div.query_selector("p.text-1")
        description = (await desc_el.inner_text()).strip() if desc_el else ""

        rules.append({
            "rule_number": rule_number,
            "cms_id": cms_id,
            "description": description,
        })

    return rules


async def click_next_page(page):
    """Click the Next button and wait for navigation. Returns True on success."""
    next_btn = await page.query_selector("input[id*='imgbtnNext']")
    if next_btn:
        async with page.expect_navigation(wait_until="networkidle", timeout=30000):
            await next_btn.click()
        await page.wait_for_timeout(PAGE_LOAD_WAIT)
        return True

    # Fallback: set __EVENTTARGET and submit the form
    postback_target = (
        "ctl00$SPWebPartManager1$"
        "g_fa5bfb26_6660_4160_a46a_49812f2e8ad4$"
        "ctl01$imgbtnNext"
    )
    async with page.expect_navigation(wait_until="networkidle", timeout=30000):
        await page.evaluate(
            f"document.getElementById('__EVENTTARGET').value = '{postback_target}';"
            "document.getElementById('aspnetForm').submit();"
        )
    await page.wait_for_timeout(PAGE_LOAD_WAIT)
    return True


async def collect_all_rule_ids(start_page: int = 1):
    """Navigate listing pages and return a list of rule dicts.

    If start_page > 1, navigates forward to that page first (for resuming).
    Saves progress to INDEX_FILE after every page.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: Playwright is not installed.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    # Load any previously collected rules
    all_rules = load_index()
    # Track which rule CMS IDs we already have (to avoid duplicates on resume)
    existing_ids = {r["cms_id"] for r in all_rules}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        print("  Loading rules listing page...")
        await page.goto(RULES_LISTING_URL, wait_until="networkidle", timeout=BROWSER_TIMEOUT)
        await page.wait_for_timeout(PAGE_LOAD_WAIT)

        # Detect total pages from header: "520 Record(s) | Page [1 of 52]"
        header_el = await page.query_selector("div.act_search_header")
        header_text = (await header_el.inner_text()) if header_el else ""
        total_match = re.search(r"of\s+(\d+)", header_text)
        total_pages = int(total_match.group(1)) if total_match else 52
        record_match = re.search(r"(\d+)\s+Record", header_text)
        total_records = int(record_match.group(1)) if record_match else 520
        print(f"  Found {total_records} rules across {total_pages} pages")

        # Fast-forward to start_page if resuming
        if start_page > 1:
            print(f"  Skipping to page {start_page} ...", end=" ", flush=True)
            for _ in range(1, start_page):
                try:
                    await click_next_page(page)
                except Exception:
                    # If skip-navigation fails, try reloading from scratch
                    break
            print("done")

        print()

        for page_num in range(start_page, total_pages + 1):
            print(f"  Page {page_num:>2}/{total_pages} ... ", end="", flush=True)

            # Try to extract rules, with retries on failure
            rules = []
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # Wait for at least one search_result to appear
                    await page.wait_for_selector(
                        "div.search_result", state="attached", timeout=15000
                    )
                    rules = await extract_rules_from_page(page)
                    if rules:
                        break
                except Exception:
                    pass

                # Retry: wait longer and try again
                if attempt < MAX_RETRIES:
                    print(f"(retry {attempt}) ", end="", flush=True)
                    await page.wait_for_timeout(5000)

            # If all retries failed, try reloading the page entirely
            if not rules:
                print("(reload) ", end="", flush=True)
                try:
                    await page.reload(wait_until="networkidle", timeout=BROWSER_TIMEOUT)
                    await page.wait_for_timeout(PAGE_LOAD_WAIT)
                    await page.wait_for_selector(
                        "div.search_result", state="attached", timeout=15000
                    )
                    rules = await extract_rules_from_page(page)
                except Exception:
                    pass

            # Add new rules (skip duplicates)
            new_count = 0
            for r in rules:
                if r["cms_id"] not in existing_ids:
                    all_rules.append(r)
                    existing_ids.add(r["cms_id"])
                    new_count += 1

            print(f"  {len(rules):>2} found, {new_count:>2} new  (total: {len(all_rules)})")

            # Save progress after EVERY page
            save_index(all_rules)

            # Navigate to next page
            if page_num < total_pages:
                try:
                    await click_next_page(page)
                except Exception as e:
                    print(f"\n  Navigation error on page {page_num}: {e}")
                    print(f"  Progress saved. Re-run to resume from page {page_num + 1}.")
                    break

        await browser.close()

    return all_rules


# ---------------------------------------------------------------------------
# Phase 2 — Fetch .htm content via HTTP
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
})


def fetch_rule_htm(cms_id: str, rule_number: str = "") -> str | None:
    """Fetch rule HTML — tries WCF API first (clean UTF-8), .htm as fallback."""
    # Attempt 1: WCF Web Service API — returns clean UTF-8 JSON for all rules.
    # The response is a JSON string wrapping HTML, e.g. "<div>...</div>"
    # Some rule names need variation (e.g. "11-OB" must be sent as "11 OB")
    if rule_number:
        name_variants = [rule_number]
        if "-" in rule_number:
            name_variants.append(rule_number.replace("-", " "))
        for variant in name_variants:
            api_url = f"{RULES_API_BASE}?rule=Income-tax%20Rules&number={variant}"
            try:
                resp = SESSION.get(api_url, timeout=30)
                resp.raise_for_status()
                html = json.loads(resp.text)
                if isinstance(html, str) and len(html) > 50:
                    return html
            except (requests.RequestException, json.JSONDecodeError):
                pass

    # Attempt 2: Direct .htm file (fallback — needs UTF-16 decoding)
    url = f"{RULES_HTM_BASE}{cms_id}.htm"
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        # .htm files are served as UTF-16; decode from raw bytes
        raw = resp.content
        for encoding in ("utf-16", "utf-16-le", "utf-8"):
            try:
                return raw.decode(encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return resp.text
    except requests.RequestException:
        pass

    print("(404) ", end="", flush=True)
    return None


def htm_to_markdown(html: str) -> str:
    """Convert raw rule HTML into clean, LLM-friendly markdown."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "meta", "link", "nav", "header", "footer"]):
        tag.decompose()

    # Convert to markdown
    content = md(str(soup), heading_style="ATX", strip=["img"])

    # Clean up
    content = re.sub(r"\n{3,}", "\n\n", content)       # collapse blank lines
    content = re.sub(r"[ \t]+\n", "\n", content)        # trailing whitespace
    content = re.sub(r"\[([^\]]*)\]\(javascript:[^)]*\)", r"\1", content)  # js links
    content = content.strip()

    return content


def save_rule(rule_number: str, description: str, content: str) -> str:
    """Save rule as a markdown file. Returns the file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    safe_name = re.sub(r"[/\\: ]", "_", rule_number)
    filepath = os.path.join(OUTPUT_DIR, f"rule_{safe_name}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Rule {rule_number} — Income Tax Rules, 1962\n\n")
        f.write(f"**Title:** {description}\n\n")
        f.write("---\n\n")
        f.write(content)
        f.write("\n")

    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Scrape Income Tax Rules")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if file already exists")
    parser.add_argument("--skip-browser", action="store_true",
                        help="Skip Phase 1 if rules_index.json already exists")
    args = parser.parse_args()

    print("=" * 60)
    print("  Income Tax Rules Scraper")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Phase 1: Collect CMS IDs
    # ------------------------------------------------------------------
    print("\n--- Phase 1: Collecting rule CMS IDs from listing pages ---\n")

    if args.skip_browser and os.path.exists(INDEX_FILE):
        print(f"  Loading cached index from {INDEX_FILE}")
        all_rules = load_index()
    elif os.path.exists(INDEX_FILE):
        existing = load_index()
        if len(existing) >= 500:
            # Index looks complete, skip browser
            all_rules = existing
            print(f"  Index already has {len(all_rules)} rules — looks complete.")
            print("  (Delete rules_index.json to re-scrape from scratch)")
        else:
            # Partial index — resume from where we left off
            pages_done = len(existing) // 10  # ~10 rules per page
            resume_page = pages_done + 1
            print(f"  Partial index found: {len(existing)} rules (~{pages_done} pages)")
            print(f"  Resuming from page {resume_page}...\n")
            all_rules = await collect_all_rule_ids(start_page=resume_page)
    else:
        all_rules = await collect_all_rule_ids(start_page=1)

    print(f"\n  Total rules in index: {len(all_rules)}")

    # ------------------------------------------------------------------
    # Phase 2: Fetch .htm files and convert to markdown
    # ------------------------------------------------------------------
    print("\n--- Phase 2: Fetching rule content (.htm files) ---\n")

    success = 0
    skipped = 0
    failed = 0
    failed_rules = []

    for i, rule in enumerate(all_rules, 1):
        rule_num = rule["rule_number"]
        cms_id = rule["cms_id"]
        desc = rule["description"]

        # Check if already downloaded
        safe_name = re.sub(r"[/\\: ]", "_", rule_num)
        filepath = os.path.join(OUTPUT_DIR, f"rule_{safe_name}.md")

        if not args.force and os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            skipped += 1
            continue

        desc_short = desc[:55] + "..." if len(desc) > 55 else desc
        print(f"  [{i:>3}/{len(all_rules)}] Rule {rule_num:<8} {desc_short:<60}", end="  ")

        html = fetch_rule_htm(cms_id, rule_number=rule_num)
        if not html:
            failed += 1
            failed_rules.append(rule_num)
            print("FAILED")
            time.sleep(REQUEST_DELAY)
            continue

        content = htm_to_markdown(html)

        if len(content) < 30:
            # Likely an error page or empty response
            failed += 1
            failed_rules.append(rule_num)
            print("EMPTY")
            time.sleep(REQUEST_DELAY)
            continue

        save_rule(rule_num, desc, content)
        success += 1
        print("OK")

        time.sleep(REQUEST_DELAY)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  Results")
    print("=" * 60)
    print(f"  Downloaded : {success}")
    print(f"  Skipped    : {skipped} (already exist)")
    print(f"  Failed     : {failed}")
    print(f"  Total      : {len(all_rules)}")

    if failed_rules:
        print(f"\n  Failed rules: {', '.join(failed_rules[:20])}")
        if len(failed_rules) > 20:
            print(f"  ... and {len(failed_rules) - 20} more")

    print(f"\n  Rule files saved to: {os.path.abspath(OUTPUT_DIR)}")
    print(f"  Next step: python src/ingest_rules.py")


if __name__ == "__main__":
    asyncio.run(main())
