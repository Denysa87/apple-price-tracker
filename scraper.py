#!/usr/bin/env python3
"""
🍎 Apple Price Tracker — scraper.py
Monitoriza AirPods, iPhones e Apple Watch em 6 retalhistas PT.
Usa Playwright (Chromium headless) para scraping de sites JavaScript.

Uso local (demo):     python3 scraper.py --demo
Uso local (real):     python3 scraper.py
GitHub Actions:       python3 scraper.py  (automático via workflow)
"""

import argparse
import asyncio
import json
import re
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_FILE      = Path(__file__).parent / "prices.json"
OVERRIDES_FILE = Path(__file__).parent / "url_overrides.json"
SUGGESTIONS_FILE       = Path(__file__).parent / "url_suggestions.json"
OVERRIDE_FAILURES_FILE = Path(__file__).parent / "url_override_failures.json"

# ─────────────────────────────────────────────────────────────
# Sistema híbrido de memória de URLs
# ─────────────────────────────────────────────────────────────

class URLMemory:
    """Regista URLs que funcionaram e rastreia falhas de overrides."""

    FAILURE_THRESHOLD = 3

    def __init__(self):
        self.suggestions = self._load(SUGGESTIONS_FILE)
        self.failures    = self._load(OVERRIDE_FAILURES_FILE)

    def _load(self, path: Path) -> dict:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self, data: dict, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_success(self, key: str, site: str, url: str, price: float) -> None:
        """Regista URL que funcionou como sugestão para consulta futura."""
        self.suggestions.setdefault(key, {})
        existing = self.suggestions[key].get(site, {})
        self.suggestions[key][site] = {
            "url":          url,
            "last_price":   price,
            "last_seen":    datetime.now().strftime("%Y-%m-%d"),
            "times_worked": existing.get("times_worked", 0) + 1,
        }
        self.reset_override_failure(key, site)
        self._save(self.suggestions, SUGGESTIONS_FILE)

    def reset_override_failure(self, key: str, site: str) -> None:
        """Limpa contador de falhas quando override volta a funcionar."""
        if key in self.failures and site in self.failures.get(key, {}):
            del self.failures[key][site]
            if not self.failures[key]:
                del self.failures[key]
            self._save(self.failures, OVERRIDE_FAILURES_FILE)

    def handle_override_failure(self, key: str, site: str, overrides: dict) -> None:
        """Regista falha de override e remove-o ao atingir o threshold."""
        self.failures.setdefault(key, {})
        self.failures[key][site] = self.failures[key].get(site, 0) + 1
        count = self.failures[key][site]
        self._save(self.failures, OVERRIDE_FAILURES_FILE)

        if count >= self.FAILURE_THRESHOLD:
            print(f"\n      ⚠️  Override \"{key}\" / {site} falhou {count}x — a remover automaticamente.")
            if key in overrides and site in overrides[key]:
                del overrides[key][site]
            try:
                if OVERRIDES_FILE.exists():
                    with open(OVERRIDES_FILE, encoding="utf-8") as f:
                        raw = json.load(f)
                    if key in raw and site in raw.get(key, {}):
                        del raw[key][site]
                        if not raw[key]:
                            del raw[key]
                        with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
                            json.dump(raw, f, ensure_ascii=False, indent=2)
                        print(f"      🗑️  Removido de url_overrides.json — tracker volta ao automático.")
            except Exception:
                pass
            del self.failures[key][site]
            if not self.failures[key]:
                del self.failures[key]
            self._save(self.failures, OVERRIDE_FAILURES_FILE)
        else:
            remaining = self.FAILURE_THRESHOLD - count
            suffix = " — será removido na próxima falha" if remaining == 1 else ""
            print(f" ⚠️  override falhou ({count}/{self.FAILURE_THRESHOLD}){suffix}", end="")


# ─────────────────────────────────────────────────────────────
# Catálogo de produtos
# ─────────────────────────────────────────────────────────────

CATALOGUE = {
    "AirPods": {
        "AirPods 4":         {"variants": {"": "Apple AirPods 4"}},
        "AirPods 4 ANC":     {"variants": {"": "Apple AirPods 4 ANC"}},
        "AirPods Pro 3":     {"variants": {"": "Apple AirPods Pro 3"}},
        "AirPods Max USB-C": {"variants": {"": "Apple AirPods Max"}},
    },
    "iPhone": {
        "iPhone 17 Pro Max": {"variants": {
            "256GB": "Apple iPhone 17 Pro Max 256GB",
            "512GB": "Apple iPhone 17 Pro Max 512GB",
            "1TB":   "Apple iPhone 17 Pro Max 1TB",
        }},
        "iPhone 17 Pro": {"variants": {
            "256GB": "Apple iPhone 17 Pro 256GB",
            "512GB": "Apple iPhone 17 Pro 512GB",
            "1TB":   "Apple iPhone 17 Pro 1TB",
        }},
        "iPhone 17": {"variants": {
            "128GB": "Apple iPhone 17 128GB",
            "256GB": "Apple iPhone 17 256GB",
            "512GB": "Apple iPhone 17 512GB",
        }},
        "iPhone 17 Air": {"variants": {
            "128GB": "Apple iPhone 17 Air 128GB",
            "256GB": "Apple iPhone 17 Air 256GB",
        }},
        "iPhone 17e": {"variants": {
            "128GB": "Apple iPhone 17e 128GB",
            "256GB": "Apple iPhone 17e 256GB",
        }},
        "iPhone 16": {"variants": {
            "128GB": "Apple iPhone 16 128GB",
            "256GB": "Apple iPhone 16 256GB",
            "512GB": "Apple iPhone 16 512GB",
        }},
        "iPhone 16e": {"variants": {
            "128GB": "Apple iPhone 16e 128GB",
            "256GB": "Apple iPhone 16e 256GB",
        }},
        "iPhone 15": {"variants": {
            "128GB": "Apple iPhone 15 128GB",
            "256GB": "Apple iPhone 15 256GB",
            "512GB": "Apple iPhone 15 512GB",
        }},
    },
    "Apple Watch": {
        "Apple Watch SE 3": {"variants": {
            "40mm": "Apple Watch SE 3 40mm",
            "44mm": "Apple Watch SE 3 44mm",
        }},
        "Apple Watch Series 11": {"variants": {
            "42mm": "Apple Watch Series 11 42mm",
            "46mm": "Apple Watch Series 11 46mm",
        }},
        "Apple Watch Ultra 3": {"variants": {
            "49mm": "Apple Watch Ultra 3 49mm",
        }},
    },
}

# ─────────────────────────────────────────────────────────────
# URLs de pesquisa por site
# ─────────────────────────────────────────────────────────────

from urllib.parse import quote_plus

def search_url(site: str, query: str) -> str:
    q = quote_plus(query)
    return {
        "Worten":        f"https://www.worten.pt/search?query={q}",
        "Rádio Popular": f"https://www.radiopopular.pt/pesquisa/?q={q}",
        "Darty":         f"https://www.darty.com/nav/recherche?text={q}",
        "MEO":           f"https://loja.meo.pt/pesquisa?q={q}",
        "Vodafone":      f"https://www.vodafone.pt/loja/pesquisa.html?q={q}",
        "NOS":           f"https://www.nos.pt/particulares/equipamentos/pesquisa?q={q}",
    }[site]

SITES = ["Worten", "Rádio Popular", "Darty", "MEO", "Vodafone", "NOS"]

# Extracção de preços — estratégia unificada para todos os sites
# ─────────────────────────────────────────────────────────────

def _parse_pt_price(text: str) -> Optional[float]:
    """
    Converte texto de preço PT/FR para float.
    Suporta: '1.299,99', '899,99', '1299.99', inteiros como '999'.
    """
    try:
        cleaned = re.sub(r'[€$\s\xa0\u202f]', '', str(text))
        # Milhar com ponto e decimal com vírgula: 1.299,99
        if re.search(r'\d\.\d{3},', cleaned):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        # Milhar com vírgula e decimal com ponto: 1,299.99
        elif re.search(r'\d,\d{3}\.', cleaned):
            cleaned = cleaned.replace(',', '')
        # Ponto com exatamente 3 dígitos após = milhar: 1.299
        elif re.search(r'^\d{1,3}\.\d{3}$', cleaned):
            cleaned = cleaned.replace('.', '')
        else:
            # Só vírgula decimal: 899,99
            cleaned = cleaned.replace(',', '.')
        match = re.search(r'\d+\.?\d*', cleaned)
        return float(match.group()) if match else None
    except (ValueError, AttributeError):
        return None


def extract_prices_from_html(html: str) -> list[float]:
    """
    Extrai preços do HTML renderizado usando múltiplas estratégias:
    1. JSON-LD schema.org (MEO, Rádio Popular, etc.)
    2. __NEXT_DATA__ (Next.js — Worten, NOS)
    3. itemprop="price" (Rádio Popular, Worten)
    4. Padrões em JSON embebido no JS (Vodafone, Worten, NOS)
    5. Padrões inline no HTML (qualquer site)
    """
    found = set()

    def add(v):
        if v is not None and 50 < v < 10000:
            found.add(round(v, 2))

    # 1. JSON-LD schema.org
    for jld in re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    ):
        try:
            d = json.loads(jld)
            items = d if isinstance(d, list) else [d]
            for item in items:
                if not isinstance(item, dict):
                    continue
                offers = item.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                for key in ('price', 'lowPrice', 'highPrice'):
                    val = offers.get(key)
                    if val is not None:
                        add(_parse_pt_price(str(val)))
        except Exception:
            pass

    # 2. __NEXT_DATA__ (Next.js)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            raw = json.dumps(json.loads(m.group(1)))
            for hit in re.findall(
                r'"(?:price|currentPrice|salePrice|finalPrice|pvp|amount)"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
                raw, re.IGNORECASE
            ):
                add(_parse_pt_price(hit))
        except Exception:
            pass

    # 3. itemprop="price" content="..."
    for pat in [
        r'itemprop=["\']price["\'][^>]*content=["\']([0-9.,]+)["\']',
        r'content=["\']([0-9.,]+)["\'][^>]*itemprop=["\']price["\']',
    ]:
        for hit in re.findall(pat, html):
            add(_parse_pt_price(hit))

    # 4. JSON embebido — padrões comuns em SPAs
    for hit in re.findall(
        r'"(?:price|salePrice|finalPrice|pvp|regularPrice|amount|displayPrice|currentPrice)"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
        html, re.IGNORECASE
    ):
        add(_parse_pt_price(hit))

    # 5. Preços inline visíveis no HTML (formato PT e FR)
    for pat in [
        r'[\s>"\'<](\d{1,2}\.\d{3},\d{2})\s*€',   # 1.499,99 €
        r'[\s>"\'<](\d{3,4},\d{2})\s*€',            # 899,99 €
        r'€\s*(\d{3,4},\d{2})[\s<"\'=]',            # € 899,99
        r'[\s>"\'<](\d{3,4}\.\d{2})\s*€',           # 899.99 € (formato FR/EN)
        r'[\s>"\'<](\d{3,4})\s*€',                  # 999 € (inteiros)
    ]:
        for hit in re.findall(pat, html):
            add(_parse_pt_price(hit))

    # 6. Rádio Popular — <select name="modp"> com data-total nas opcoes de pagamento
    # O preco de compra a vista esta na opcao com value="1"
    pat_sel = re.compile(r'<select[^>]*name=["\']modp["\'][^>]*>(.*?)</select>', re.DOTALL)
    pat_v1  = re.compile(r'<option[^>]*value=["\']1["\'][^>]*data-total=["\']([^"\']+)["\']')
    pat_dt  = re.compile(r'<option[^>]*data-total=["\']([^"\']+)["\']')
    for sel_m in pat_sel.finditer(html):
        sel_html = sel_m.group(1)
        m = pat_v1.search(sel_html)
        if m:
            add(_parse_pt_price(m.group(1)))
        else:
            all_dt = pat_dt.findall(sel_html)
            if all_dt:
                add(_parse_pt_price(all_dt[-1]))

    return sorted(found)


def find_product_url(html: str, query: str, site: str, base_url: str) -> Optional[str]:
    """
    Extrai o URL da página de produto mais relevante da página de resultados.
    Cada site tem os seus seletores específicos.
    Devolve o URL absoluto do produto ou None.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    query_lower = query.lower()

    # Tokens relevantes da query (ignora palavras curtas)
    tokens = [t for t in query_lower.split() if len(t) > 2]

    def relevance(title: str) -> int:
        """Conta quantos tokens da query aparecem no título."""
        t = title.lower()
        return sum(1 for tok in tokens if tok in t)

    def make_absolute(href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        return base_url.rstrip("/") + "/" + href.lstrip("/")

    candidates = []  # lista de (relevance_score, url, title)

    if site == "Worten":
        # Cards: <li> ou <div> com classe que contém 'product'
        # Link: <a> dentro do card com href que contém '/produtos/' ou '/p/'
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/produtos/" in href or "/p/" in href:
                title = a.get_text(strip=True) or a.get("title", "") or href
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "Rádio Popular":
        # Cards: <article class="js-trigger-href"> com data-href (não "discount-product")
        # Os títulos estão no atributo alt das imagens dentro do article
        for article in soup.find_all("article", class_=lambda c: c and "js-trigger-href" in (c if isinstance(c, str) else " ".join(c))):
            href = article.get("data-href", "")
            # Título: tentar alt da imagem, h2/h3, ou texto dos links
            title = ""
            img = article.find("img")
            if img and img.get("alt"):
                title = img["alt"]
            if not title:
                title_el = article.find(["h2", "h3", "h4"])
                title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                a_el = article.find("a")
                title = a_el.get_text(strip=True) if a_el else href
            # Preferir link direto /produto/ se existir
            direct = article.find("a", href=lambda h: h and "/produto/" in h)
            if direct:
                href = direct.get("href", href)
            score = relevance(title)
            if score > 0 and href:
                candidates.append((score, make_absolute(href), title[:80]))
        # Fallback: todos os links /produto/ na página com relevância
        if not candidates:
            for a in soup.find_all("a", href=lambda h: h and "/produto/" in h):
                title = a.get_text(strip=True) or a.get("title", "") or a.get("aria-label", "") or ""
                # Tentar alt da img dentro do link
                img = a.find("img")
                if not title and img:
                    title = img.get("alt", "")
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(a["href"]), title[:80]))

    elif site == "Darty":
        # Cards: <div> ou <article> com classe 'product' ou 'article'
        # Links: href com '/nav/achat/' ou '/produit/'
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/nav/achat/" in href or "/produit/" in href or "/p/" in href:
                title = a.get_text(strip=True) or a.get("title", "") or href
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "MEO":
        # Links: href com '/telemoveis/' ou '/equipamentos/' ou slug de produto
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in ["/telemoveis/", "/equipamentos/", "/acessorios/", "/produto/"]):
                title = a.get_text(strip=True) or a.get("title", "") or ""
                # Também verificar atributo data-name ou aria-label
                if not title:
                    title = a.get("aria-label", "") or a.get("data-name", "") or href
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "Vodafone":
        # Links: href com '/loja/telemoveis/' ou '/equipamentos/'
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in ["/loja/telemoveis/", "/equipamentos/", "/produto/"]):
                title = a.get_text(strip=True) or a.get("title", "") or a.get("aria-label", "") or ""
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "NOS":
        # Links: href com '/particulares/equipamentos/' ou '/telemovel/'
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in ["/particulares/equipamentos/", "/telemovel/", "/equipamento/"]):
                title = a.get_text(strip=True) or a.get("title", "") or a.get("aria-label", "") or ""
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    if not candidates:
        return None

    # Ordenar por relevância (maior primeiro), desempate pelo URL mais curto (página de produto mais directa)
    candidates.sort(key=lambda x: (-x[0], len(x[1])))
    best_url = candidates[0][1]
    best_title = candidates[0][2]
    print(f" → produto: {best_title[:50]}…" if len(best_title) > 50 else f" → produto: {best_title}", end="")
    return best_url



def best_match(prices: list[float], query: str) -> Optional[float]:
    """
    De uma lista de preços extraídos de uma página de pesquisa,
    devolve o mais provável para o produto pesquisado.
    Heurística: valor mais baixo plausível (evita preços de acessórios muito baratos).
    """
    if not prices:
        return None
    # filtra ruído — preços demasiado baixos para o produto
    query_lower = query.lower()
    min_price = 40
    if "pro max" in query_lower or "ultra" in query_lower:
        min_price = 800
    elif "pro" in query_lower and "iphone" in query_lower:
        min_price = 600
    elif "iphone" in query_lower:
        min_price = 400
    elif "watch" in query_lower:
        min_price = 150
    elif "airpods max" in query_lower:
        min_price = 400
    elif "airpods" in query_lower:
        min_price = 100
    candidates = [p for p in prices if p >= min_price]
    return min(candidates) if candidates else None


# ─────────────────────────────────────────────────────────────
# Playwright scraper (async)
# ─────────────────────────────────────────────────────────────

async def scrape_all_async() -> dict:
    from playwright.async_api import async_playwright

    memory = URLMemory()
    overrides = {}
    if OVERRIDES_FILE.exists():
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            raw_ov = json.load(f)
            overrides = {k: v for k, v in raw_ov.items() if not k.startswith("_")}

    results = {}  # { category:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-PT",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        for category, models in CATALOGUE.items():
            results.setdefault(category, {})
            print(f"\n📦  {category}")

            for model_name, model_info in models.items():
                for variant, query in model_info["variants"].items():
                    key = f"{model_name} {variant}".strip()
                    results[category].setdefault(key, {})
                    print(f"  🔍  {key}")

                    for site in SITES:
                        override_url = overrides.get(key, {}).get(site)
                        url = override_url if override_url else search_url(site, query)
                        is_override = bool(override_url)
                        flag = "🔗" if is_override else "📡"
                        print(f"      {flag}  {site}{'  [override]' if is_override else ''}...", end=" ", flush=True)
                        try:
                            # Alguns sites precisam de networkidle para carregar resultados via JS
                            wait_mode = "networkidle" if site in ("Rádio Popular", "MEO", "Vodafone", "NOS") else "domcontentloaded"
                            await page.goto(url, wait_until=wait_mode, timeout=25000)
                            # Espera extra para JS renderizar os resultados
                            extra_wait = 4000 if site in ("Rádio Popular", "MEO", "Vodafone", "NOS") else 2500
                            await page.wait_for_timeout(extra_wait)
                            html = await page.content()

                            # Se não é override, tentar navegar para a página do produto
                            if not is_override:
                                site_bases = {
                                    "Worten":        "https://www.worten.pt",
                                    "Rádio Popular": "https://www.radiopopular.pt",
                                    "Darty":         "https://www.darty.com",
                                    "MEO":           "https://loja.meo.pt",
                                    "Vodafone":      "https://www.vodafone.pt",
                                    "NOS":           "https://www.nos.pt",
                                }
                                product_url = find_product_url(html, query, site, site_bases.get(site, ""))
                                if product_url and product_url != page.url:
                                    try:
                                        await page.goto(product_url, wait_until=wait_mode, timeout=20000)
                                        await page.wait_for_timeout(3000)
                                        html = await page.content()
                                    except Exception:
                                        pass  # Se falhar, usa o HTML da pesquisa
                            prices = extract_prices_from_html(html)
                            price = best_match(prices, query)

                            if price:
                                results[category][key].setdefault(site, [])
                                results[category][key][site].append({
                                    "date":       ts,
                                    "price":      price,
                                    "url":        page.url,
                                    "url_source": "override" if is_override else "auto",
                                })
                                print(f"✅  {price:.2f} €")
                                if not is_override:
                                    memory.record_success(key, site, page.url, price)
                                else:
                                    memory.reset_override_failure(key, site)
                            else:
                                print(f"—  sem resultado {prices[:3]}")
                                if is_override:
                                    memory.handle_override_failure(key, site, overrides)

                        except Exception as e:
                            print(f"❌  {str(e)[:60]}")
                            if is_override:
                                memory.handle_override_failure(key, site, overrides)

                        await asyncio.sleep(random.uniform(1.0, 2.5))

        # ── Programas de fidelização ─────────────────────────────
        print("\n📋  Programas de Fidelização (iPhones)")
        results.setdefault("Programas", {})

        for key, programs in DEMO_PROGRAMS.items():
            # Usa DEMO_PROGRAMS como referência dos modelos a pesquisar
            results["Programas"].setdefault(key, {})
            print(f"  🔍  {key}")

            for program, _ in programs.items():
                url = PROGRAM_URLS[program](key)
                # Verifica override
                override_url = overrides.get(key, {}).get(program)
                if override_url:
                    url = override_url

                print(f"      {'🔗' if override_url else '📡'}  {program}...", end=" ", flush=True)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(2500)
                    html = await page.content()

                    price = None
                    points = None

                    # Extrai preço principal
                    prices = extract_prices_from_html(html)
                    price = best_match(prices, key)

                    # Tenta extrair pontos (MEO MEOS / Vodafone Viva)
                    if "MEOS" in program or "Viva" in program:
                        for pat in [
                            r'(\d{1,2}[.,]\d{3})\s*pontos',
                            r'(\d{3,5})\s*pontos',
                            r'pontos[:\s]+(\d{3,5})',
                            r'"points"\s*:\s*(\d{3,5})',
                        ]:
                            m = re.search(pat, html, re.IGNORECASE)
                            if m:
                                try:
                                    points = int(m.group(1).replace('.', '').replace(',', ''))
                                    break
                                except Exception:
                                    pass

                    if price:
                        results["Programas"][key].setdefault(program, []).append({
                            "date":   ts,
                            "price":  price,
                            "points": points,
                            "url":    page.url,
                            "url_source": "override" if override_url else "auto",
                        })
                        pts_str = f" · {points} pts" if points else ""
                        print(f"✅  {price:.2f} €{pts_str}")
                        if not override_url:
                            memory.record_success(key, program, page.url, price)
                        else:
                            memory.reset_override_failure(key, program)
                    else:
                        print(f"—  sem resultado")
                        if override_url:
                            memory.handle_override_failure(key, program, overrides)

                except Exception as e:
                    print(f"❌  {str(e)[:60]}")

                await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    return results


# ─────────────────────────────────────────────────────────────
# Dados demo (sem scraping — valores de referência Apple Store PT)
# ─────────────────────────────────────────────────────────────

DEMO_BASE_PRICES = {
    "AirPods 4":              {"": {"Worten":149,  "Rádio Popular":149,  "Darty":149,  "MEO":149,    "Vodafone":149,  "NOS":149  }},
    "AirPods 4 ANC":          {"": {"Worten":199,  "Rádio Popular":199,  "Darty":199,  "MEO":199,    "Vodafone":199,  "NOS":199  }},
    "AirPods Pro 3":          {"": {"Worten":249,  "Rádio Popular":249,  "Darty":249,  "MEO":249,    "Vodafone":249,  "NOS":249  }},
    "AirPods Max USB-C":      {"": {"Worten":579,  "Rádio Popular":579,  "Darty":579,  "MEO":579,    "Vodafone":579,  "NOS":579  }},
    "iPhone 17 Pro Max 256GB":{"Worten":1479, "Rádio Popular":1479, "Darty":1479, "MEO":1499.99, "Vodafone":1499, "NOS":1479},
    "iPhone 17 Pro Max 512GB":{"Worten":1709, "Rádio Popular":1709, "Darty":1709, "MEO":1729.99, "Vodafone":1729, "NOS":1709},
    "iPhone 17 Pro Max 1TB":  {"Worten":1949, "Rádio Popular":1949, "Darty":1949, "MEO":1969.99, "Vodafone":1969, "NOS":1949},
    "iPhone 17 Pro 256GB":    {"Worten":1279, "Rádio Popular":1279, "Darty":1279, "MEO":1299.99, "Vodafone":1299, "NOS":1279},
    "iPhone 17 Pro 512GB":    {"Worten":1509, "Rádio Popular":1509, "Darty":1509, "MEO":1529.99, "Vodafone":1529, "NOS":1509},
    "iPhone 17 Pro 1TB":      {"Worten":1749, "Rádio Popular":1749, "Darty":1749, "MEO":1769.99, "Vodafone":1769, "NOS":1749},
    "iPhone 17 128GB":        {"Worten":979,  "Rádio Popular":979,  "Darty":979,  "MEO":999.99,  "Vodafone":999,  "NOS":979 },
    "iPhone 17 256GB":        {"Worten":1099, "Rádio Popular":1099, "Darty":1099, "MEO":1119.99, "Vodafone":1119, "NOS":1099},
    "iPhone 17 512GB":        {"Worten":1339, "Rádio Popular":1339, "Darty":1339, "MEO":1359.99, "Vodafone":1359, "NOS":1339},
    "iPhone 17 Air 128GB":    {"Worten":1099, "Rádio Popular":1099, "Darty":1099, "MEO":1119.99, "Vodafone":1119, "NOS":1099},
    "iPhone 17 Air 256GB":    {"Worten":1229, "Rádio Popular":1229, "Darty":1229, "MEO":1249.99, "Vodafone":1249, "NOS":1229},
    "iPhone 17e 128GB":       {"Worten":599,  "Rádio Popular":599,  "Darty":599,  "MEO":619.99,  "Vodafone":619,  "NOS":599 },
    "iPhone 17e 256GB":       {"Worten":729,  "Rádio Popular":729,  "Darty":729,  "MEO":749.99,  "Vodafone":749,  "NOS":729 },
    "iPhone 16 128GB":        {"Worten":849,  "Rádio Popular":849,  "Darty":849,  "MEO":869.99,  "Vodafone":869,  "NOS":849 },
    "iPhone 16 256GB":        {"Worten":979,  "Rádio Popular":979,  "Darty":979,  "MEO":999.99,  "Vodafone":999,  "NOS":979 },
    "iPhone 16 512GB":        {"Worten":1219, "Rádio Popular":1219, "Darty":1219, "MEO":1239.99, "Vodafone":1239, "NOS":1219},
    "iPhone 16e 128GB":       {"Worten":649,  "Rádio Popular":649,  "Darty":649,  "MEO":669.99,  "Vodafone":669,  "NOS":649 },
    "iPhone 16e 256GB":       {"Worten":779,  "Rádio Popular":779,  "Darty":779,  "MEO":799.99,  "Vodafone":799,  "NOS":779 },
    "iPhone 15 128GB":        {"Worten":699,  "Rádio Popular":699,  "Darty":699,  "MEO":699,     "Vodafone":699,  "NOS":699 },
    "iPhone 15 256GB":        {"Worten":829,  "Rádio Popular":829,  "Darty":829,  "MEO":829,     "Vodafone":829,  "NOS":829 },
    "iPhone 15 512GB":        {"Worten":1069, "Rádio Popular":1069, "Darty":1069, "MEO":1069,    "Vodafone":1069, "NOS":1069},
    "Apple Watch SE 3 40mm":  {"Worten":289,  "Rádio Popular":289,  "Darty":289,  "MEO":299.99,  "Vodafone":299,  "NOS":289 },
    "Apple Watch SE 3 44mm":  {"Worten":319,  "Rádio Popular":319,  "Darty":319,  "MEO":329.99,  "Vodafone":329,  "NOS":319 },
    "Apple Watch Series 11 42mm":{"Worten":469,"Rádio Popular":469, "Darty":469,  "MEO":489.99,  "Vodafone":489,  "NOS":469 },
    "Apple Watch Series 11 46mm":{"Worten":499,"Rádio Popular":499, "Darty":499,  "MEO":519.99,  "Vodafone":519,  "NOS":499 },
    "Apple Watch Ultra 3 49mm":  {"Worten":879,"Rádio Popular":879, "Darty":879,  "MEO":899.99,  "Vodafone":899,  "NOS":879 },
}

SITE_URLS = {
    "Worten":        "https://www.worten.pt",
    "Rádio Popular": "https://www.radiopopular.pt",
    "Darty":         "https://www.darty.com",
    "MEO":           "https://loja.meo.pt",
    "Vodafone":      "https://www.vodafone.pt",
    "NOS":           "https://www.nos.pt",
}

CATEGORY_FOR_KEY = {}
for cat, models in CATALOGUE.items():
    for model, info in models.items():
        for variant in info["variants"]:
            key = f"{model} {variant}".strip()
            CATEGORY_FOR_KEY[key] = cat


# ─────────────────────────────────────────────────────────────
# Catálogo de Programas de Fidelização (apenas iPhones)
# ─────────────────────────────────────────────────────────────

# Modelos de iPhone a monitorizar nos programas
IPHONE_KEYS = [k for k in CATEGORY_FOR_KEY if k.startswith("iPhone")]

PROGRAM_URLS = {
    "NOS DCN":       lambda q: f"https://www.nos.pt/particulares/equipamentos/pesquisa?q={quote_plus(q)}",
    "MEO MEOS":      lambda q: f"https://loja.meo.pt/meos/equipamentos/telemoveis?q={quote_plus(q)}",
    "Vodafone Viva": lambda q: f"https://www.vodafone.pt/loja/viva/telemoveis.html?q={quote_plus(q)}",
}

# Demo: preços e pontos aproximados para os programas
# NOS DCN  → só preço (desconto ~5% sobre preço online)
# MEO MEOS → pontos + preço com desconto
# Vodafone Viva → pontos + preço com desconto
DEMO_PROGRAMS = {
    "iPhone 17 Pro Max 256GB": {
        "NOS DCN":       {"price": 1419.99, "points": None},
        "MEO MEOS":      {"price": 1199.99, "points": 5000},
        "Vodafone Viva": {"price": 1249.99, "points": 4500},
    },
    "iPhone 17 Pro Max 512GB": {
        "NOS DCN":       {"price": 1629.99, "points": None},
        "MEO MEOS":      {"price": 1399.99, "points": 5500},
        "Vodafone Viva": {"price": 1449.99, "points": 5000},
    },
    "iPhone 17 Pro Max 1TB": {
        "NOS DCN":       {"price": 1859.99, "points": None},
        "MEO MEOS":      {"price": 1649.99, "points": 6000},
        "Vodafone Viva": {"price": 1699.99, "points": 5500},
    },
    "iPhone 17 Pro 256GB": {
        "NOS DCN":       {"price": 1219.99, "points": None},
        "MEO MEOS":      {"price": 999.99,  "points": 4500},
        "Vodafone Viva": {"price": 1049.99, "points": 4000},
    },
    "iPhone 17 Pro 512GB": {
        "NOS DCN":       {"price": 1439.99, "points": None},
        "MEO MEOS":      {"price": 1229.99, "points": 5000},
        "Vodafone Viva": {"price": 1279.99, "points": 4500},
    },
    "iPhone 17 Pro 1TB": {
        "NOS DCN":       {"price": 1669.99, "points": None},
        "MEO MEOS":      {"price": 1449.99, "points": 5500},
        "Vodafone Viva": {"price": 1499.99, "points": 5000},
    },
    "iPhone 17 128GB": {
        "NOS DCN":       {"price": 929.99,  "points": None},
        "MEO MEOS":      {"price": 749.99,  "points": 3000},
        "Vodafone Viva": {"price": 799.99,  "points": 2500},
    },
    "iPhone 17 256GB": {
        "NOS DCN":       {"price": 1049.99, "points": None},
        "MEO MEOS":      {"price": 879.99,  "points": 3500},
        "Vodafone Viva": {"price": 929.99,  "points": 3000},
    },
    "iPhone 17 512GB": {
        "NOS DCN":       {"price": 1279.99, "points": None},
        "MEO MEOS":      {"price": 1099.99, "points": 4000},
        "Vodafone Viva": {"price": 1149.99, "points": 3500},
    },
    "iPhone 17 Air 128GB": {
        "NOS DCN":       {"price": 1049.99, "points": None},
        "MEO MEOS":      {"price": 879.99,  "points": 3500},
        "Vodafone Viva": {"price": 929.99,  "points": 3000},
    },
    "iPhone 17 Air 256GB": {
        "NOS DCN":       {"price": 1169.99, "points": None},
        "MEO MEOS":      {"price": 999.99,  "points": 4000},
        "Vodafone Viva": {"price": 1049.99, "points": 3500},
    },
    "iPhone 17e 128GB": {
        "NOS DCN":       {"price": 569.99,  "points": None},
        "MEO MEOS":      {"price": 449.99,  "points": 2000},
        "Vodafone Viva": {"price": 499.99,  "points": 1500},
    },
    "iPhone 17e 256GB": {
        "NOS DCN":       {"price": 699.99,  "points": None},
        "MEO MEOS":      {"price": 579.99,  "points": 2500},
        "Vodafone Viva": {"price": 629.99,  "points": 2000},
    },
    "iPhone 16 128GB": {
        "NOS DCN":       {"price": 809.99,  "points": None},
        "MEO MEOS":      {"price": 649.99,  "points": 2500},
        "Vodafone Viva": {"price": 699.99,  "points": 2000},
    },
    "iPhone 16 256GB": {
        "NOS DCN":       {"price": 929.99,  "points": None},
        "MEO MEOS":      {"price": 779.99,  "points": 3000},
        "Vodafone Viva": {"price": 829.99,  "points": 2500},
    },
    "iPhone 16 512GB": {
        "NOS DCN":       {"price": 1159.99, "points": None},
        "MEO MEOS":      {"price": 999.99,  "points": 3500},
        "Vodafone Viva": {"price": 1049.99, "points": 3000},
    },
    "iPhone 16e 128GB": {
        "NOS DCN":       {"price": 619.99,  "points": None},
        "MEO MEOS":      {"price": 499.99,  "points": 2000},
        "Vodafone Viva": {"price": 549.99,  "points": 1500},
    },
    "iPhone 16e 256GB": {
        "NOS DCN":       {"price": 739.99,  "points": None},
        "MEO MEOS":      {"price": 629.99,  "points": 2500},
        "Vodafone Viva": {"price": 679.99,  "points": 2000},
    },
    "iPhone 15 128GB": {
        "NOS DCN":       {"price": 659.99,  "points": None},
        "MEO MEOS":      {"price": 549.99,  "points": 2000},
        "Vodafone Viva": {"price": 599.99,  "points": 1500},
    },
    "iPhone 15 256GB": {
        "NOS DCN":       {"price": 789.99,  "points": None},
        "MEO MEOS":      {"price": 679.99,  "points": 2500},
        "Vodafone Viva": {"price": 729.99,  "points": 2000},
    },
    "iPhone 15 512GB": {
        "NOS DCN":       {"price": 1019.99, "points": None},
        "MEO MEOS":      {"price": 899.99,  "points": 3000},
        "Vodafone Viva": {"price": 949.99,  "points": 2500},
    },
}


def run_demo(existing: dict) -> dict:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    count = 0
    for key, site_prices in DEMO_BASE_PRICES.items():
        # AirPods têm estrutura diferente: {variant: {site: price}}
        if isinstance(list(site_prices.values())[0], dict):
            for variant, sp in site_prices.items():
                full_key = f"{key} {variant}".strip()
                cat = CATEGORY_FOR_KEY.get(full_key, "AirPods")
                existing.setdefault(cat, {}).setdefault(full_key, {})
                for site, price in sp.items():
                    existing[cat][full_key].setdefault(site, []).append(
                        {"date": ts, "price": float(price), "url": SITE_URLS[site]}
                    )
                    count += 1
        else:
            cat = CATEGORY_FOR_KEY.get(key, "iPhone")
            existing.setdefault(cat, {}).setdefault(key, {})
            for site, price in site_prices.items():
                existing[cat][key].setdefault(site, []).append(
                    {"date": ts, "price": float(price), "url": SITE_URLS[site]}
                )
                count += 1
    print(f"  ✅  {count} entradas de hoje registadas (preços de referência Apple Store PT)")

    # Programas de fidelização
    prog_count = 0
    existing.setdefault("Programas", {})
    for key, programs in DEMO_PROGRAMS.items():
        existing["Programas"].setdefault(key, {})
        for program, info in programs.items():
            existing["Programas"][key].setdefault(program, []).append({
                "date":   ts,
                "price":  float(info["price"]),
                "points": info["points"],
                "url":    SITE_URLS.get(program.split()[0], "#"),
            })
            prog_count += 1
    print(f"  ✅  {prog_count} entradas de programas registadas (NOS DCN · MEO MEOS · Vodafone Viva)")
    return existing


# ─────────────────────────────────────────────────────────────
# Persistência
# ─────────────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    total = sum(
        len(h)
        for cat in data.values()
        for model in cat.values()
        for h in model.values()
    )
    print(f"  ✅  Guardado em {DATA_FILE.name} ({total} entradas totais)")


def merge(existing: dict, new_results: dict) -> dict:
    for cat, models in new_results.items():
        existing.setdefault(cat, {})
        for key, sites in models.items():
            existing[cat].setdefault(key, {})
            for site, entries in sites.items():
                existing[cat][key].setdefault(site, [])
                existing[cat][key][site].extend(entries)
    return existing


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="🍎 Apple Price Tracker")
    parser.add_argument("--demo", action="store_true",
                        help="Regista preços de referência sem fazer scraping")
    args = parser.parse_args()

    existing = load_data()

    if args.demo:
        print("📋  Modo demo — preços de referência Apple Store PT")
        existing = run_demo(existing)
    else:
        print("🌐  A fazer scraping com Playwright (Chromium headless)...")
        new_data = asyncio.run(scrape_all_async())
        existing  = merge(existing, new_data)

    save_data(existing)


if __name__ == "__main__":
    main()
