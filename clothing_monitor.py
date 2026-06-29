#!/usr/bin/env python3
"""
Clothing Brand Sale Monitor
Detects site-wide sales at premium menswear brands and sends Pushover + email alerts.
"""

import asyncio
import json
import logging
import os
import smtplib
import sys
import time
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# ── Config ─────────────────────────────────────────────────────────────────────

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SENDER_EMAIL       = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL    = os.getenv("RECIPIENT_EMAIL", "bhoogs24@gmail.com")
PUSHOVER_USER      = os.getenv("PUSHOVER_USER")
PUSHOVER_TOKEN     = os.getenv("PUSHOVER_TOKEN")

SCRIPT_DIR = Path(__file__).parent
LOG_FILE   = SCRIPT_DIR / "clothing_monitor.log"
SEEN_FILE  = SCRIPT_DIR / "seen_sales.json"

BRANDS = [
    {"name": "Travis Matthew",      "home": "https://www.travismathew.com",                    "threshold": 30},
    {"name": "Rhoback",             "home": "https://rhoback.com",                             "threshold": 30},
    {"name": "Vuori",               "home": "https://vuoriclothing.com",                       "threshold": 20},
    {"name": "Peter Millar",        "home": "https://www.petermillar.com/sale",                "threshold": 20},
    {"name": "Holderness & Bourne", "home": "https://www.holdernessandbourne.com",             "threshold": 30},
    {"name": "Titleist",            "home": "https://www.titleist.com/apparel-gear/",          "threshold": 30},
    {"name": "Johnnie O",           "home": "https://www.johnnieo.com",                        "threshold": 30},
    {"name": "Primo Golf",          "home": "https://www.primogolf.com",                       "threshold": 30},
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Seen Sales ─────────────────────────────────────────────────────────────────

def load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {}
    data = json.loads(SEEN_FILE.read_text())
    today_ord = date.today().toordinal()
    return {
        k: v for k, v in data.items()
        if today_ord - date.fromisoformat(v.get("first_seen", date.today().isoformat())).toordinal() <= 10
    }

def save_seen(seen: dict) -> None:
    SEEN_FILE.write_text(json.dumps(seen, indent=2))

# ── Scraper ────────────────────────────────────────────────────────────────────

async def fetch_page_text(page, url: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(6_000)
        return await page.inner_text("body")
    except Exception as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return ""

async def scrape_brands() -> list[dict]:
    results = []
    async with async_playwright() as pw:
        # --disable-http2 fixes ERR_HTTP2_PROTOCOL_ERROR on sites like Lululemon
        browser = await pw.chromium.launch(headless=True, args=["--disable-http2"])
        ctx = await browser.new_context(user_agent=USER_AGENT)

        for brand in BRANDS:
            log.info("Checking %s...", brand["name"])
            page = await ctx.new_page()
            text = await fetch_page_text(page, brand["home"])
            await page.close()
            results.append({
                "name":      brand["name"],
                "home":      brand["home"],
                "threshold": brand["threshold"],
                "text":      text[:4000],
            })
            await asyncio.sleep(2)

        await browser.close()
    return results

# ── Gemini Evaluation ──────────────────────────────────────────────────────────

EVAL_PROMPT = """\
You are analyzing clothing brand homepages to detect active site-wide sales.

For each brand below, determine if there is a current site-wide or significant promotional discount.

Flag as a sale ONLY if there is a clear, active discount such as:
- "X% off sitewide"
- "X% off all orders"
- "Extra X% off everything"
- A prominent promo code for a meaningful discount (20%+)

Do NOT flag:
- Permanent clearance or sale sections with individual items marked down
- Loyalty or rewards program benefits
- Email signup welcome offers (typically 10-15%)
- Free shipping promotions only

Brands to analyze:
{brands_text}

Respond with ONLY valid JSON, no markdown:
{{
  "results": [
    {{
      "name": "Travis Matthew",
      "sale_detected": true,
      "discount_pct": 30,
      "description": "30% off sitewide this weekend",
      "promo_code": "SUMMER30",
      "ends": "Sunday July 6"
    }}
  ]
}}

Include one entry per brand. Use empty string for promo_code and ends if not found.
"""

def evaluate_with_gemini(results: list[dict]) -> list[dict]:
    client = genai.Client(api_key=GEMINI_API_KEY)

    brands_text = ""
    for r in results:
        brands_text += f"\n\n=== {r['name']} (alert threshold: {r['threshold']}% off) ===\n{r['text']}"

    prompt = EVAL_PROMPT.format(brands_text=brands_text)

    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(resp.text)
            return data.get("results", [])
        except Exception as e:
            if attempt < 2:
                wait = 15 * (attempt + 1)
                log.warning("Gemini attempt %d failed: %s — retrying in %ds", attempt + 1, e, wait)
                time.sleep(wait)
            else:
                raise

# ── Notifications ──────────────────────────────────────────────────────────────

def send_pushover(message: str) -> None:
    try:
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token":   PUSHOVER_TOKEN,
                "user":    PUSHOVER_USER,
                "message": message,
                "title":   "Sale Alert",
            },
            timeout=10,
        )
        log.info("Pushover sent (%s): %s", resp.status_code, message)
    except Exception as e:
        log.error("Pushover failed: %s", e)

def send_email(new_sales: list[dict]) -> None:
    subject = f"Sale Alert: {', '.join(s['name'] for s in new_sales)}"

    brand_home = {b["name"]: b["home"] for b in BRANDS}
    rows = []
    for sale in new_sales:
        code_html = (
            f'<div style="margin-top:6px;font-size:13px;">Code: '
            f'<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;">'
            f'{sale["promo_code"]}</code></div>'
        ) if sale.get("promo_code") else ""
        ends_html = (
            f'<div style="color:#888;font-size:12px;margin-top:4px;">Ends: {sale["ends"]}</div>'
        ) if sale.get("ends") else ""
        rows.append(f"""
        <div style="border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0;">
          <div style="font-size:20px;font-weight:bold;color:#1a73e8;">{sale['name']}</div>
          <div style="font-size:16px;color:#2e7d32;font-weight:bold;margin-top:4px;">{sale['description']}</div>
          {code_html}
          {ends_html}
          <div style="margin-top:12px;">
            <a href="{brand_home.get(sale['name'], '#')}"
               style="background:#1a73e8;color:white;padding:8px 16px;border-radius:4px;text-decoration:none;font-size:13px;">
              Shop Now →
            </a>
          </div>
        </div>
        """)

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <h2 style="color:#1a73e8;">Sale Alert</h2>
      {''.join(rows)}
      <p style="font-size:12px;color:#999;margin-top:20px;">Verify details on each brand's website before purchasing.</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            smtp.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        log.info("Email sent for %d sale(s)", len(new_sales))
    except Exception as e:
        log.error("Email failed: %s", e)

# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    log.info("══ Clothing monitor run started ══")

    results = await scrape_brands()
    usable = [r for r in results if len(r.get("text", "")) > 200]
    log.info("Fetched %d/%d brand pages", len(usable), len(results))

    if not usable:
        log.warning("No pages fetched — possible connection issue")
        return

    try:
        evaluations = evaluate_with_gemini(usable)
    except Exception as e:
        log.error("Gemini evaluation failed: %s", e)
        return

    seen = load_seen()
    today = date.today().isoformat()
    new_sales = []

    for ev in evaluations:
        if not ev.get("sale_detected"):
            log.info("%-25s No sale", ev["name"])
            seen.pop(ev["name"], None)
            continue

        discount  = ev.get("discount_pct", 0)
        threshold = next((b["threshold"] for b in BRANDS if b["name"] == ev["name"]), 30)

        if discount < threshold:
            log.info("%-25s %d%% off — below %d%% threshold", ev["name"], discount, threshold)
            continue

        desc = ev.get("description", "")
        if ev["name"] in seen and seen[ev["name"]].get("description") == desc:
            log.info("%-25s Already notified for this sale", ev["name"])
            continue

        log.info("%-25s NEW SALE: %s", ev["name"], desc)
        seen[ev["name"]] = {"description": desc, "first_seen": today}
        new_sales.append(ev)

    save_seen(seen)

    if not new_sales:
        log.info("No new sales — done")
        return

    for sale in new_sales:
        msg = f"{sale['name']}: {sale['description']}"
        if sale.get("promo_code"):
            msg += f" | Code: {sale['promo_code']}"
        if sale.get("ends"):
            msg += f" | Ends: {sale['ends']}"
        send_pushover(msg)

    send_email(new_sales)
    log.info("══ Run complete — %d new sale(s) ══", len(new_sales))


if __name__ == "__main__":
    asyncio.run(main())
