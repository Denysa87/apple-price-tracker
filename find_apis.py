#!/usr/bin/env python3
"""
Tenta encontrar APIs internas dos sites PT para obter preços sem browser.
Estratégia: inspecionar o HTML estático à procura de chamadas API,
chaves Algolia, endpoints GraphQL, ou JSON embebido com preços.
"""
import re, json
import urllib.request, urllib.parse

UA  = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
PT  = {"Accept-Language": "pt-PT,pt;q=0.9", "Accept": "application/json,text/html,*/*"}

def get(url, headers=None):
    h = {"User-Agent": UA, **(PT), **(headers or {})}
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace"), r.geturl()
    except Exception as e:
        return f"ERR:{e}", url

# ── MEO ───────────────────────────────────────────────────────────────────────
print("\n=== MEO ===")
html, _ = get("https://loja.meo.pt/comprar/telemoveis/apple/iphone-17-pro-max-256gb")
print(f"HTML size: {len(html)}")
# 1. JSON-LD schema.org
for m in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
    try:
        d = json.loads(m)
        s = json.dumps(d)
        if any(k in s for k in ["price","Price","offer"]):
            print("JSON-LD:", s[:300])
    except: pass
# 2. next/nuxt __NUXT__ or __NEXT_DATA__
for pat in [r'__NEXT_DATA__\s*=\s*(\{.*?\})\s*;?\s*</script>', r'window\.__data\s*=\s*(\{.*?\})\s*;']:
    m = re.search(pat, html, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            s = json.dumps(d)
            prices = re.findall(r'"(?:price|finalPrice|pvp|amount)"\s*:\s*(\d{3,5}\.?\d*)', s)
            print(f"NEXT_DATA prices: {prices[:8]}")
        except: pass
# 3. direct price patterns
for pat in [r'"price"\s*:\s*"?(\d{3,5}\.?\d{2})"?', r'"pvp"\s*:\s*(\d{3,5}\.?\d{2})',
            r'"amount"\s*:\s*(\d{3,5}\.?\d{2})', r'>(\d{1,2}\.\d{3},\d{2})\s*€',
            r'>(\d{3,4},\d{2})\s*€', r'\"finalPrice\":(\d{3,5}\.?\d{2})']:
    hits = re.findall(pat, html, re.IGNORECASE)
    valid = sorted(set(round(float(h.replace('.','').replace(',','.')),2) for h in hits
                       if 50 < float(h.replace('.','').replace(',','.')) < 10000))
    if valid: print(f"Pattern '{pat[:30]}': {valid[:5]}")

# MEO API attempt — typical NuxtJS site
print("\n-- MEO API attempt --")
for api_url in [
    "https://loja.meo.pt/api/products/iphone-17-pro-max-256gb",
    "https://loja.meo.pt/_next/data/index.json",
    "https://loja.meo.pt/api/catalog?slug=iphone-17-pro-max-256gb",
]:
    resp, _ = get(api_url, {"Accept": "application/json"})
    if not resp.startswith("ERR") and len(resp) > 100:
        prices = re.findall(r'"(?:price|pvp|amount|finalPrice)"\s*:\s*(\d{3,5}\.?\d{2})', resp)
        print(f"  {api_url}: {prices[:5] if prices else resp[:100]}")
    else:
        print(f"  {api_url}: {resp[:60]}")

# ── VODAFONE ─────────────────────────────────────────────────────────────────
print("\n=== VODAFONE ===")
html, _ = get("https://www.vodafone.pt/loja/telemoveis/apple/iphone-17-pro-max-5g.html?color=prateado&storage=256&segment=consumer&paymentType=pvp")
print(f"HTML size: {len(html)}")
# Look for embedded JSON state
for pat in [r'"pvp"\s*:\s*(\d{3,5}\.?\d{2})', r'"price"\s*:\s*(\d{3,5}\.?\d{2})',
            r'"finalPrice"\s*:\s*(\d{3,5}\.?\d{2})', r'>(\d{1,2}\.\d{3},\d{2})\s*€',
            r'data-price="(\d{3,5}\.?\d{2})"']:
    hits = re.findall(pat, html, re.IGNORECASE)
    valid = sorted(set(round(float(h.replace('.','').replace(',','.')),2) for h in hits
                       if 50 < float(h.replace('.','').replace(',','.')) < 10000))
    if valid: print(f"Pattern '{pat[:35]}': {valid[:5]}")

# Vodafone API patterns
print("-- Vodafone API attempt --")
for api_url in [
    "https://www.vodafone.pt/bin/vodafone/getdevicedetails?slug=iphone-17-pro-max-5g&storage=256",
    "https://www.vodafone.pt/api/devices/iphone-17-pro-max?storage=256",
    "https://www.vodafone.pt/content/dam/vodafone/devices/apple/iphone-17-pro-max.json",
]:
    resp, _ = get(api_url, {"Accept": "application/json"})
    if not resp.startswith("ERR") and len(resp) > 50:
        prices = re.findall(r'"(?:price|pvp|finalPrice)"\s*:\s*(\d{3,5}\.?\d{2})', resp)
        print(f"  {api_url.split('vodafone.pt')[1][:60]}: {prices[:5] if prices else resp[:80]}")
    else:
        print(f"  {api_url.split('vodafone.pt')[1][:60]}: {resp[:60]}")

# ── WORTEN ────────────────────────────────────────────────────────────────────
print("\n=== WORTEN (Algolia) ===")
# Worten uses Algolia — find the app ID and API key from their JS
html, _ = get("https://www.worten.pt/search?query=iphone+17+pro+max+256gb")
algolia_app = re.search(r'["\']([A-Z0-9]{10})["\']', html)
algolia_key = re.search(r'ALGOLIA[_\w]*["\']:\s*["\']([a-f0-9]{32})["\']', html, re.IGNORECASE)
print(f"Algolia AppID: {algolia_app.group(1) if algolia_app else 'not found'}")
print(f"Algolia Key:   {algolia_key.group(1) if algolia_key else 'not found'}")

# Try Worten search API directly
for api_url in [
    "https://www.worten.pt/api/search?q=iphone+17+pro+max+256gb",
    "https://www.worten.pt/api/catalog/search?query=iphone+17+pro+max",
    "https://api.worten.pt/catalog/v1/search?q=iphone+17+pro+max",
]:
    resp, _ = get(api_url, {"Accept": "application/json"})
    if not resp.startswith("ERR") and len(resp) > 50:
        prices = re.findall(r'"(?:price|salePrice|regularPrice)"\s*:\s*(\d{3,5}\.?\d{0,2})', resp)
        print(f"  {api_url.split('worten.pt')[1][:50]}: size={len(resp)} prices={prices[:5]}")
    else:
        print(f"  {api_url.split('worten.pt')[1][:50]}: {resp[:60]}")

# ── RADIO POPULAR ─────────────────────────────────────────────────────────────
print("\n=== RÁDIO POPULAR ===")
html, _ = get("https://www.radiopopular.pt/pesquisa/?q=iphone+17+pro+max+256gb")
print(f"HTML size: {len(html)}")
for pat in [r'itemprop="price"[^>]*content="([0-9.,]+)"',
            r'"regularPrice"\s*:\s*(\d{3,5}\.?\d{2})',
            r'"specialPrice"\s*:\s*(\d{3,5}\.?\d{2})',
            r'class="[^"]*price[^"]*"[^>]*>\s*(\d{1,2}\.\d{3},\d{2})',
            r'class="[^"]*price[^"]*"[^>]*>\s*(\d{3,4},\d{2})']:
    hits = re.findall(pat, html, re.IGNORECASE)
    valid = [round(float(h.replace('.','').replace(',','.')),2) for h in hits
             if 50 < float(h.replace('.','').replace(',','.')) < 10000]
    if valid: print(f"  '{pat[:40]}': {sorted(set(valid))[:5]}")

print("\nDone.")
