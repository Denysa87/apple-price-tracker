#!/usr/bin/env python3
"""Fetches real prices from PT retailer pages."""
import re, json, time, random
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

TARGETS = [
    ("Vodafone",        "iPhone 17 Pro Max 256GB", "https://www.vodafone.pt/loja/telemoveis/apple/iphone-17-pro-max-5g.html?color=prateado&storage=256&segment=consumer&paymentType=pvp"),
    ("Vodafone",        "iPhone 17 Pro Max 512GB", "https://www.vodafone.pt/loja/telemoveis/apple/iphone-17-pro-max-5g.html?color=prateado&storage=512&segment=consumer&paymentType=pvp"),
    ("MEO",             "iPhone 17 Pro Max 256GB", "https://loja.meo.pt/comprar/telemoveis/apple/iphone-17-pro-max-256gb"),
    ("MEO",             "iPhone 17 Pro Max 512GB", "https://loja.meo.pt/comprar/telemoveis/apple/iphone-17-pro-max-512gb"),
    ("Worten",          "iPhone 17 Pro Max",        "https://www.worten.pt/search?query=iphone+17+pro+max"),
    ("Rádio Popular",   "iPhone 17 Pro Max",        "https://www.radiopopular.pt/pesquisa/?q=iphone+17+pro+max"),
    ("NOS",             "iPhone 17 Pro Max",        "https://www.nos.pt/particulares/equipamentos/pesquisa?q=iphone+17+pro+max"),
    ("Darty",           "iPhone 17 Pro Max",        "https://www.darty.com/nav/recherche?text=iphone+17+pro+max"),
    ("Worten",          "AirPods Pro 2",            "https://www.worten.pt/search?query=airpods+pro+2"),
    ("Rádio Popular",   "AirPods Pro 2",            "https://www.radiopopular.pt/pesquisa/?q=airpods+pro+2"),
    ("Worten",          "Apple Watch Ultra 3",      "https://www.worten.pt/search?query=apple+watch+ultra+3"),
]

PRICE_PATTERNS = [
    r'"price"\s*:\s*"?(\d{3,5}\.?\d*)"?',
    r'"salePrice"\s*:\s*"?(\d{3,5}\.?\d*)"?',
    r'"regularPrice"\s*:\s*"?(\d{3,5}\.?\d*)"?',
    r'"finalPrice"\s*:\s*(\d{3,5}\.?\d*)',
    r'"pvp"\s*:\s*(\d{3,5}\.?\d*)',
    r'"amount"\s*:\s*(\d{3,5}\.?\d*)',
    r'content="(\d{3,5}[.,]\d{2})"[^>]*itemprop="price"',
    r'itemprop="price"[^>]*content="(\d{3,5}[.,]\d{2})"',
    r'>(\d{1}\.\d{3},\d{2})\s*[€]',   # 1.499,99 €
    r'>(\d{3,4},\d{2})\s*[€]',         # 1499,99 €
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"

def extract_prices(html):
    found = set()
    for pat in PRICE_PATTERNS:
        for m in re.findall(pat, html, re.IGNORECASE):
            try:
                v = float(str(m).replace(".","").replace(",","."))
                if 50 < v < 10000:
                    found.add(round(v, 2))
            except:
                pass
    return sorted(found)

results = {}
for site, product, url in TARGETS:
    print(f"  Fetching {site} — {product}...", end=" ", flush=True)
    time.sleep(random.uniform(0.8, 1.5))
    html = fetch(url)
    if html.startswith("ERROR"):
        print(f"❌ {html}")
        continue
    prices = extract_prices(html)
    print(f"→ {prices[:6] if prices else 'sem preços (JS?)'}")
    key = f"{site} | {product}"
    results[key] = {"url": url, "prices": prices, "html_len": len(html)}

print("\n=== RESUMO ===")
for k, v in results.items():
    print(f"  {k}: {v['prices'][:5]} (html={v['html_len']}b)")

# Save for inspection
with open("fetched_prices.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nGuardado em fetched_prices.json")
