#!/usr/bin/env python3
"""Test Playwright with Firefox on PT retailer sites."""
import re, time
from playwright.sync_api import sync_playwright

PRICE_PATTERNS = [
    r'"price"\s*:\s*"?(\d{3,5}\.?\d{2})"?',
    r'"salePrice"\s*:\s*"?(\d{3,5}\.?\d{2})"?',
    r'"finalPrice"\s*:\s*(\d{3,5}\.?\d{2})',
    r'"pvp"\s*:\s*(\d{3,5}\.?\d{2})',
    r'"amount"\s*:\s*(\d{3,5}\.?\d{2})',
    r'(\d{1,2}\.\d{3},\d{2})\s*\u20ac',
    r'(\d{3,4},\d{2})\s*\u20ac',
    r'\u20ac\s*(\d{3,4},\d{2})',
    r'content="(\d{3,5}[.,]\d{2})"[^>]*itemprop="price"',
    r'itemprop="price"[^>]*content="(\d{3,5}[.,]\d{2})"',
]

def extract_prices(html):
    found = set()
    for pat in PRICE_PATTERNS:
        for m in re.findall(pat, html, re.IGNORECASE):
            try:
                v = float(str(m).replace('.','').replace(',','.'))
                if 50 < v < 10000:
                    found.add(round(v, 2))
            except:
                pass
    return sorted(found)

TESTS = [
    ("MEO",      "iPhone 17 Pro Max 256GB", "https://loja.meo.pt/comprar/telemoveis/apple/iphone-17-pro-max-256gb"),
    ("Vodafone", "iPhone 17 Pro Max 256GB", "https://www.vodafone.pt/loja/telemoveis/apple/iphone-17-pro-max-5g.html?color=prateado&storage=256&segment=consumer&paymentType=pvp"),
    ("Worten",   "iPhone 17 Pro Max",       "https://www.worten.pt/search?query=iphone+17+pro+max+256gb"),
    ("RP",       "iPhone 17 Pro Max",       "https://www.radiopopular.pt/pesquisa/?q=iphone+17+pro+max+256gb"),
]

with sync_playwright() as p:
    print("Abrindo Firefox...")
    browser = p.firefox.launch(headless=True)
    ctx = browser.new_context(locale="pt-PT", viewport={"width":1280,"height":800})
    page = ctx.new_page()

    for site, product, url in TESTS:
        print(f"\n→ {site} — {product}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)
            html = page.content()
            prices = extract_prices(html)
            print(f"  HTML: {len(html)}b | Preços: {prices[:6] if prices else 'NENHUM'}")
            if not prices:
                # try to find price element via selector
                for sel in ['[class*="price"]', '[itemprop="price"]', '[data-price]']:
                    els = page.query_selector_all(sel)
                    for el in els[:3]:
                        txt = el.inner_text().strip()
                        if re.search(r'\d{3}', txt):
                            print(f"  Selector {sel}: '{txt[:60]}'")
                            break
        except Exception as e:
            print(f"  ERRO: {e}")

    browser.close()
    print("\nDone.")
