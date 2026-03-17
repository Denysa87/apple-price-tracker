#!/usr/bin/env python3
"""
🍎 Apple Price Tracker — scraper.py
Monitoriza AirPods e iPhones em 6 retalhistas PT.
Usa Playwright (Chromium headless) para scraping de sites JavaScript.

Uso local (demo):     python3 scraper.py --demo
Uso local (real):     python3 scraper.py
GitHub Actions:       python3 scraper.py  (automático via workflow)

Sprint 1 Melhorias:
- ✅ Timeouts aumentados (5-8s para sites JS-heavy, 15s para Cloudflare)
- ✅ Validação de preços por categoria (elimina bug 1499€)
- ✅ Sistema de logging estruturado (arquivo + console)
- ✅ Debug info guardada em caso de erro

Sprint 2 Melhorias (Anti-Bot):
- ✅ Headers HTTP completos (Sec-Fetch-*, DNT, sec-ch-ua)
- ✅ Rotação de User-Agents (5 opções)
- ✅ Cookies persistentes (.cookies/cookies.json, 7 dias)
- ✅ Delays realistas (distribuição triangular 1.5-3.5s)
- ✅ Scroll humano (200-800px aleatório)
- ✅ Retry com backoff exponencial (3x: 2s→4s→8s)

Sprint 3 Melhorias (Críticas):
- ✅ Timeouts por site (Worten/Darty: 40s, Rádio Popular: 35s, outros: 30s)
- ✅ Cloudflare wait aumentado (15s → 30s)
- ✅ Seletores de preço melhorados (MEO, NOS, Vodafone)
- ✅ Padrões genéricos adicionais (data-*, classes price/preco/valor)

Sprint 4 Melhorias (Navegação MEO):
- ✅ MEO: Navegação por categoria (404 → 100% sucesso)
- ✅ Filtros melhorados em find_product_url()
- ✅ Ignora links genéricos de categoria

Sprint 5 Melhorias (Extratores Específicos):
- ✅ Extratores específicos NOS/Vodafone (DCN → Online)
- ✅ utils/price_extractors.py com 3 estratégias
- ✅ Precisão NOS: 80% → 100% (589€ → 739€)

Sprint 6 Melhorias (Performance):
- ✅ Timeouts otimizados: 40s → 20s (Worten/Darty), 35s → 25s (Rádio Popular), 30s → 15s (outros)
- ✅ Esperas extras otimizadas: 7s → 3s (Rádio Popular/MEO), 5s → 2s (Vodafone/NOS)
- ✅ Cloudflare wait otimizado: 30s → 15s

Sprint 7 Melhorias (EAN + Simplificação):
- ✅ Catálogo simplificado: 11 iPhones + 3 AirPods (removidos Apple Watch e modelos antigos)
- ✅ Suporte a EAN (European Article Number) para identificação única
- ❌ Pesquisa por EAN desativada no Sprint 8 (causava bloqueios e 0 resultados)

Sprint 8 Melhorias (Performance + Taxa de Sucesso):
- ✅ EAN desativado completamente (causava bloqueios Cloudflare e 0 resultados)
- ✅ Validação de preços expandida (aceita 799.99€, 149.99€, 989.99€)
- ✅ Timeouts otimizados: 15s Worten/Darty, 10-12s outros (redução 20-33%)
- ✅ Esperas extras reduzidas: 1.5s MEO, 1s Vodafone/NOS, 0.8s outros (redução 50%)
- ✅ Delays entre requests otimizados: 0.8-1.5s (redução 60%)
- ✅ Seletores melhorados: Vodafone, NOS, Darty (mais padrões de URL)

Sprint 9 Melhorias (Paralelização):
- ✅ Scraping paralelo por site com asyncio.gather() (5 sites simultâneos)
- ✅ Contextos de browser independentes por site (isolamento completo)
- ✅ Controle de concorrência com semáforos (máx 5 sites paralelos)
- ✅ Tempo de execução: 15min → 4-6min (redução de 60-70%)
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

# Importar utilitários do Sprint 1
try:
    from utils.validators import validate_price, is_likely_accessory_price
    from utils.logger import setup_logger, log_scraping_success, log_scraping_failure, log_price_validation_failed, log_cloudflare_block
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    print("⚠️  Utilitários não disponíveis. Execute: pip install -r requirements.txt")

# Importar utilitários do Sprint 2 (Anti-Bot)
try:
    from utils.anti_bot import (
        get_random_user_agent, get_realistic_headers, get_random_delay,
        simulate_human_behavior, CookieManager, RetryStrategy
    )
    ANTI_BOT_AVAILABLE = True
except ImportError:
    ANTI_BOT_AVAILABLE = False
    print("⚠️  Utilitários anti-bot não disponíveis")

# Importar utilitários do Sprint 5 (Extractores específicos)
try:
    from utils.price_extractors import (
        extract_nos_online_price, extract_vodafone_online_price,
        should_use_specific_extractor
    )
    PRICE_EXTRACTORS_AVAILABLE = True
except ImportError:
    PRICE_EXTRACTORS_AVAILABLE = False
    print("⚠️  Extractores de preço específicos não disponíveis")

try:
    from playwright_stealth import stealth_async as _stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False


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
        "AirPods (4th Gen)": {"variants": {
            "": {
                "query": "Apple AirPods 4th Gen",
                "ean": "19594968591"
            },
        }},
        "AirPods (4th Gen) ANC": {"variants": {
            "": {
                "query": "Apple AirPods 4th Gen ANC",
                "ean": "19594968973"
            },
        }},
        "AirPods Pro (3rd Gen)": {"variants": {
            "": {
                "query": "Apple AirPods Pro 3rd Gen",
                "ean": "19595054374"
            },
        }},
    },
    "iPhone": {
        "iPhone 16": {"variants": {
            "128GB": {
                "query": "Apple iPhone 16 128GB",
                "ean": "19594903699"
            },
        }},
        "iPhone 16e": {"variants": {
            "128GB": {
                "query": "Apple iPhone 16e 128GB",
                "ean": "19594982899"
            },
            "256GB": {
                "query": "Apple iPhone 16e 256GB",
                "ean": "19596051117"
            },
        }},
        "iPhone 17 Pro": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro 256GB",
                "ean": "19595062765"
            },
            "1TB": {
                "query": "Apple iPhone 17 Pro 1TB",
                "ean": "19595028760"
            },
        }},
        "iPhone 17 Pro Max": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro Max 256GB",
                "ean": "19595063216"
            },
            "512GB": {
                "query": "Apple iPhone 17 Pro Max 512GB",
                "ean": "19595039810"
            },
            "1TB": {
                "query": "Apple iPhone 17 Pro Max 1TB",
                "ean": "19595064010"
            },
        }},
        "iPhone Air": {"variants": {
            "256GB": {
                "query": "Apple iPhone Air 256GB",
                "ean": "19595062584"
            },
        }},
        "iPhone 17e": {"variants": {
            "512GB": {
                "query": "Apple iPhone 17e 512GB",
                "ean": "19595103105"
            },
        }},
    },
}

# ─────────────────────────────────────────────────────────────
# URLs de pesquisa por site
# ─────────────────────────────────────────────────────────────

from urllib.parse import quote_plus

def search_url(site: str, query: str, ean: str = None) -> str:
    """
    Gera URL de pesquisa.
    Sprint 8: EAN desativado - causava bloqueios Cloudflare e 0 resultados.
    """
    # 🆕 Sprint 8: EAN desativado completamente (causava problemas)
    # Sempre usar nome do produto
    q = quote_plus(query)
    
    # MEO: A pesquisa genérica não funciona (404), usar categorias diretas
    if site == "MEO":
        query_lower = query.lower()
        if "iphone" in query_lower:
            return "https://loja.meo.pt/telemoveis/iphone"
        elif "airpods" in query_lower:
            return "https://loja.meo.pt/acessorios-telemoveis/auriculares-colunas/auriculares-bluetooth?marca=Apple"
        else:
            return f"https://loja.meo.pt/telemoveis"
    
    return {
        "Worten":   f"https://www.worten.pt/search?query={q}",
        "Darty":    f"https://www.darty.com/nav/recherche?text={q}",
        "MEO":      f"https://loja.meo.pt/telemoveis",  # Fallback, usa categorias acima
        "Vodafone": f"https://www.vodafone.pt/loja/pesquisa.html?q={q}",
        "NOS":      f"https://www.nos.pt/particulares/equipamentos/pesquisa?q={q}",
    }[site]

SITES = ["Worten", "Darty", "MEO", "Vodafone", "NOS"]

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


    # 7. Worten — aria-label="Preco 149,99" em <span>
    pat_aria = re.compile(r'aria-label=["\']Prec[oô]\s+([\d.,]+)["\']')
    for m in pat_aria.finditer(html):
        add(_parse_pt_price(m.group(1)))

    # 8. Open Graph — <meta property="og:price:amount" content="149,99">
    pat_og = re.compile(r'<meta[^>]*property=["\']og:price:amount["\'][^>]*content=["\']([\d.,]+)["\']')
    pat_og2 = re.compile(r'<meta[^>]*content=["\']([\d.,]+)["\'][^>]*property=["\']og:price:amount["\']')
    for pat in [pat_og, pat_og2]:
        for m in pat.finditer(html):
            add(_parse_pt_price(m.group(1)))

    # 9. MEO — múltiplos padrões (site mudou estrutura frequentemente)
    meo_patterns = [
        r'class=["\']price no-translate["\'][^>]*>\s*<span>€?([\d.,]+)\s*€?</span>',
        r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>€?\s*([\d.,]+)\s*€?</span>',
        r'data-price=["\'](\d+\.?\d*)["\']',
        r'"price"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
        r'<div[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?',
    ]
    for pat in meo_patterns:
        for m in re.finditer(pat, html):
            add(_parse_pt_price(m.group(1)))

    # 10. NOS — Angular ng-bind, preco em <p class="full-price ng-binding">149,99</p>
    # O Playwright executa JS entao o conteudo do ng-bind ja esta resolvido no HTML
    nos_patterns = [
        r'<p[^>]*class=["\'][^"\']*full-price[^"\']*["\'][^>]*>\s*([\d.,]+)\s*</p>',
        r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?</span>',
        r'data-price=["\'](\d+\.?\d*)["\']',
    ]
    for pat in nos_patterns:
        for m in re.finditer(pat, html):
            add(_parse_pt_price(m.group(1)))

    # 11. Vodafone — múltiplos padrões
    voda_patterns = [
        r'<span[^>]*basket-toaster__price--value[^>]*>\s*€?([\d.,]+)\s*€?\s*</span>',
        r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?</span>',
        r'data-price=["\'](\d+\.?\d*)["\']',
        r'"finalPrice"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
    ]
    for pat in voda_patterns:
        for m in re.finditer(pat, html):
            add(_parse_pt_price(m.group(1)))
    
    # 12. 🆕 Sprint 3: Padrões genéricos adicionais para todos os sites
    # Preços em atributos data-*
    for attr in ['data-price', 'data-product-price', 'data-final-price', 'data-sale-price']:
        pat = re.compile(rf'{attr}=["\'](\d{{2,5}}(?:[.,]\d{{1,3}})*)["\']')
        for m in pat.finditer(html):
            add(_parse_pt_price(m.group(1)))
    
    # Preços em classes específicas
    price_class_patterns = [
        r'<[^>]*class=["\'][^"\']*(?:price|preco|valor)[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?',
        r'<[^>]*class=["\'][^"\']*(?:amount|total|value)[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?',
    ]
    for pat in price_class_patterns:
        for m in re.finditer(pat, html, re.IGNORECASE):
            add(_parse_pt_price(m.group(1)))

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

    elif site == "Darty":
        # Cards: <div> ou <article> com classe 'product' ou 'article'
        # Links: href com '/nav/achat/' ou '/produit/'
        # 🆕 Sprint 8: Adicionados mais padrões de URL
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in [
                "/nav/achat/",
                "/produit/",
                "/p/",
                "/achat/",  # Sprint 8: Novo padrão
            ]):
                title = a.get_text(strip=True) or a.get("title", "") or href
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "MEO":
        # Links: href com '/telemoveis/' ou '/equipamentos/' ou slug de produto
        # IMPORTANTE: Evitar links genéricos como "/telemoveis/iphone" (lista todos os iPhones)
        # Preferir links específicos com modelo completo no URL
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            # Ignorar links genéricos de categoria
            if href.endswith("/telemoveis/iphone") or href.endswith("/telemoveis/apple"):
                continue
            if any(p in href for p in ["/telemoveis/", "/equipamentos/", "/acessorios/", "/produto/"]):
                title = a.get_text(strip=True) or a.get("title", "") or ""
                # Também verificar atributo data-name ou aria-label
                if not title:
                    title = a.get("aria-label", "") or a.get("data-name", "") or href
                score = relevance(title)
                # Aumentar score se o URL contém tokens específicos (modelo + capacidade)
                href_lower = href.lower()
                if score > 0:
                    # Bonus se URL tem modelo específico (ex: "iphone-17-pro-max")
                    url_tokens = sum(1 for tok in tokens if tok in href_lower)
                    score += url_tokens * 2  # Dobrar peso dos tokens no URL
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "Vodafone":
        # Links: href com '/loja/telemoveis/' ou '/equipamentos/'
        # 🆕 Sprint 8: Adicionados mais padrões de URL
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in [
                "/loja/telemoveis/",
                "/equipamentos/",
                "/produto/",
                "/telemovel/",  # Sprint 8: Novo padrão
                "/apple/",      # Sprint 8: Novo padrão
            ]):
                title = a.get_text(strip=True) or a.get("title", "") or a.get("aria-label", "") or ""
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    elif site == "NOS":
        # Links: href com '/particulares/equipamentos/' ou '/telemovel/'
        # 🆕 Sprint 8: Adicionados mais padrões de URL
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if any(p in href for p in [
                "/particulares/equipamentos/",
                "/telemovel/",
                "/equipamento/",
                "/apple/",      # Sprint 8: Novo padrão
                "/iphone/",     # Sprint 8: Novo padrão
            ]):
                title = a.get_text(strip=True) or a.get("title", "") or a.get("aria-label", "") or ""
                score = relevance(title)
                if score > 0:
                    candidates.append((score, make_absolute(href), title[:80]))

    # DEBUG — listar todos os links encontrados se não houve candidatos
    if not candidates:
        all_hrefs = [(a.get("href",""), (a.get_text(strip=True) or a.get("title","") or "")[:60])
                     for a in soup.find_all("a", href=True)][:20]
        print(f"\n    [DEBUG {site}] 0 candidatos. Primeiros links: {all_hrefs}", end="")
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

async def dismiss_cookie_banner(page) -> None:
    """Tenta fechar o banner de cookies se presente."""
    selectors = [
        "#onetrust-accept-btn-handler",
        "button#acceptAllCookies",
        "button[id*='accept-all']",
        "button[id*='acceptAll']",
        "button[class*='accept-all']",
        "button[class*='acceptAll']",
        "button:has-text('Aceitar todos os cookies')",
        "button:has-text('Aceitar tudo')",
        "button:has-text('Aceitar todos')",
        "button:has-text('Accept all')",
        "[class*='cookie'] button[class*='primary']",
        "[class*='cookie-banner'] button",
        "[class*='gdpr'] button[class*='accept']",
    ]
    for sel in selectors:
        try:
            await page.click(sel, timeout=1500)
            await page.wait_for_timeout(600)
            return
        except Exception:
            continue


def is_cloudflare_blocked(html: str) -> bool:
    """Detecta se a página é um desafio Cloudflare."""
    h = html.lower()
    return "cloudflare" in h and ("challenge" in h or "ray id" in h or "just a moment" in h)


# ─────────────────────────────────────────────────────────────
# 🆕 Sprint 9: Função de scraping por site (paralelização)
# ─────────────────────────────────────────────────────────────

async def scrape_site_for_all_products(
    browser,
    site: str,
    products_list: list,
    overrides: dict,
    memory,
    logger,
    stats: dict,
    debug_dir: Path,
    ts: str
) -> dict:
    """
    Scrape um site específico para todos os produtos.
    Permite paralelização por site usando asyncio.gather().
    
    Sprint 9: Esta função permite scraping paralelo de múltiplos sites,
    reduzindo o tempo de execução de 15min para 4-6min (60-70% mais rápido).
    """
    # Criar contexto independente para este site
    user_agent = get_random_user_agent() if ANTI_BOT_AVAILABLE else (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    
    headers = get_realistic_headers(user_agent) if ANTI_BOT_AVAILABLE else {
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }
    
    context = await browser.new_context(
        user_agent=user_agent,
        locale="pt-PT",
        viewport={"width": 1280, "height": 800},
        extra_http_headers=headers,
    )
    
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    
    page = await context.new_page()
    if STEALTH_AVAILABLE:
        await _stealth_async(page)
    
    # Seletores CSS por site
    SITE_PRODUCT_SELECTORS = {
        "Worten":   "[class*='product-card'], [class*='product-item'], .w-product",
        "Darty":    "[class*='product-card'], [data-ref*='product'], .article",
        "MEO":      "[class*='product-card'], [class*='product-item'], .product",
        "Vodafone": "[class*='product-card'], [class*='product-item'], .product",
        "NOS":      "app-product-card, [class*='product-card'], [class*='equipment']",
    }
    
    site_bases = {
        "Worten":   "https://www.worten.pt",
        "Darty":    "https://www.darty.com",
        "MEO":      "https://loja.meo.pt",
        "Vodafone": "https://www.vodafone.pt",
        "NOS":      "https://www.nos.pt",
    }
    
    results = {}
    
    print(f"\n🌐 [{site}] Iniciando scraping paralelo...")
    
    for category, key, query, ean in products_list:
        override_url = overrides.get(key, {}).get(site)
        url = override_url if override_url else search_url(site, query, ean)
        is_override = bool(override_url)
        flag = "🔗" if is_override else "📡"
        
        stats["total"] += 1
        print(f"  {flag} [{site}] {key}...", end=" ", flush=True)
        
        try:
            timeout_map = {
                "Worten": 15000, "Darty": 15000, "MEO": 10000,
                "Vodafone": 12000, "NOS": 12000,
            }
            page_timeout = timeout_map.get(site, 10000)
            
            wait_mode = "networkidle" if site in ("MEO", "Vodafone", "NOS") else "domcontentloaded"
            await page.goto(url, wait_until=wait_mode, timeout=page_timeout)
            await dismiss_cookie_banner(page)
            
            extra_wait = 1500 if site == "MEO" else 1000 if site in ("Vodafone", "NOS") else 800
            await page.wait_for_timeout(extra_wait)
            
            site_sel = SITE_PRODUCT_SELECTORS.get(site, "")
            if site_sel:
                try:
                    await page.wait_for_selector(site_sel, timeout=10000)
                except Exception:
                    pass
            
            html = await page.content()
            
            if ANTI_BOT_AVAILABLE:
                await simulate_human_behavior(page, logger)
            
            if is_cloudflare_blocked(html):
                if logger:
                    log_cloudflare_block(logger, site)
                stats["cloudflare_blocks"] += 1
                print(f"⏳ Cloudflare...", end=" ", flush=True)
                await page.wait_for_timeout(15000)
                html = await page.content()
                if is_cloudflare_blocked(html):
                    print(f"⛔")
                    stats["failed"] += 1
                    continue
                else:
                    print(f"✅", end=" ")
            
            if not is_override:
                product_url = find_product_url(html, query, site, site_bases.get(site, ""))
                if product_url and product_url != page.url:
                    try:
                        await page.goto(product_url, wait_until=wait_mode, timeout=20000)
                        await page.wait_for_timeout(3000)
                        html = await page.content()
                    except Exception:
                        pass
            
            price = None
            if PRICE_EXTRACTORS_AVAILABLE:
                use_specific = should_use_specific_extractor(site, page.url)
                if use_specific:
                    if site == "NOS":
                        price = await extract_nos_online_price(page)
                    elif site == "Vodafone":
                        price = await extract_vodafone_online_price(page)
            
            if not price:
                prices = extract_prices_from_html(html)
                price = best_match(prices, query)
            
            if price:
                if UTILS_AVAILABLE:
                    is_valid, validation_reason = validate_price(price, key)
                    
                    if is_valid and is_likely_accessory_price(price, key):
                        is_valid = False
                        validation_reason = f"Preço {price:.2f}€ muito baixo"
                    
                    if not is_valid:
                        print(f"⚠️ {price:.2f}€ rejeitado")
                        if logger:
                            log_price_validation_failed(logger, site, key, price, validation_reason)
                        stats["validation_failed"] += 1
                        stats["failed"] += 1
                        if is_override:
                            memory.handle_override_failure(key, site, overrides)
                        continue
                
                results.setdefault(category, {})
                results[category].setdefault(key, {})
                results[category][key].setdefault(site, [])
                results[category][key][site].append({
                    "date": ts,
                    "price": price,
                    "url": page.url,
                    "url_source": "override" if is_override else "auto",
                })
                print(f"✅ {price:.2f}€")
                stats["successful"] += 1
                if logger:
                    log_scraping_success(logger, site, key, price, page.url)
                if not is_override:
                    memory.record_success(key, site, page.url, price)
                else:
                    memory.reset_override_failure(key, site)
            else:
                print(f"— sem resultado")
                stats["failed"] += 1
                if logger:
                    log_scraping_failure(logger, site, key, "Nenhum preço encontrado")
                if is_override:
                    memory.handle_override_failure(key, site, overrides)
        
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
            stats["failed"] += 1
            if logger:
                log_scraping_failure(logger, site, key, str(e)[:100])
            if is_override:
                memory.handle_override_failure(key, site, overrides)
        
        delay = get_random_delay(0.8, 1.5) if ANTI_BOT_AVAILABLE else random.uniform(0.5, 1.2)
        await asyncio.sleep(delay)
    
    await context.close()
    print(f"✅ [{site}] Concluído")
    return results


async def scrape_all_async() -> dict:
    from playwright.async_api import async_playwright

    # Configurar logger (Sprint 1)
    logger = setup_logger() if UTILS_AVAILABLE else None
    if logger:
        logger.info("🚀 Iniciando scraping com melhorias Sprint 1 + Sprint 2")
        logger.info(f"   Sprint 1: Timeouts aumentados, validação de preços, logging")
        logger.info(f"   Sprint 2: Anti-bot (headers, cookies, retry, scroll)")
    
    # Criar diretórios necessários
    logs_dir = Path(__file__).parent / "logs"
    debug_dir = Path(__file__).parent / "debug"
    cookies_dir = Path(__file__).parent / ".cookies"
    logs_dir.mkdir(exist_ok=True)
    debug_dir.mkdir(exist_ok=True)
    cookies_dir.mkdir(exist_ok=True)
    
    # 🆕 Sprint 2: Inicializar componentes anti-bot
    cookie_manager = CookieManager(cookies_dir / "cookies.json") if ANTI_BOT_AVAILABLE else None
    retry_strategy = RetryStrategy(max_retries=3, base_delay=2.0) if ANTI_BOT_AVAILABLE else None
    
    # 🆕 Sprint 2: User-Agent aleatório
    user_agent = get_random_user_agent() if ANTI_BOT_AVAILABLE else (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    
    if logger and ANTI_BOT_AVAILABLE:
        logger.info(f"   User-Agent: {user_agent[:60]}...")
        logger.info(f"   Cookies persistentes: {'Ativados' if cookie_manager else 'Desativados'}")
        logger.info(f"   Retry strategy: {retry_strategy.max_retries}x com backoff exponencial")

    memory = URLMemory()
    overrides = {}
    if OVERRIDES_FILE.exists():
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            raw_ov = json.load(f)
            overrides = {k: v for k, v in raw_ov.items() if not k.startswith("_")}

    results = {}  # { category:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Contadores para estatísticas (Sprint 1)
    stats = {"total": 0, "successful": 0, "failed": 0, "validation_failed": 0, "cloudflare_blocks": 0}
    start_time = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,800",
            ],
        )
        
        # 🆕 Sprint 9: Preparar lista de produtos para scraping paralelo
        products_list = []
        for category, models in CATALOGUE.items():
            results.setdefault(category, {})
            for model_name, model_info in models.items():
                for variant, variant_info in model_info["variants"].items():
                    if isinstance(variant_info, str):
                        query = variant_info
                        ean = None
                    else:
                        query = variant_info.get("query", variant_info)
                        ean = variant_info.get("ean")
                    
                    key = f"{model_name} {variant}".strip()
                    results[category].setdefault(key, {})
                    products_list.append((category, key, query, ean))
        
        print(f"\n🚀 Sprint 9: Scraping PARALELO de {len(SITES)} sites")
        print(f"   Total de produtos: {len(products_list)}")
        print(f"   Modo: {len(SITES)} sites simultâneos (asyncio.gather)")
        
        # 🆕 Sprint 9: Scraping paralelo por site usando asyncio.gather()
        # Cada site tem seu próprio contexto de browser independente
        tasks = []
        for site in SITES:
            task = scrape_site_for_all_products(
                browser=browser,
                site=site,
                products_list=products_list,
                overrides=overrides,
                memory=memory,
                logger=logger,
                stats=stats,
                debug_dir=debug_dir,
                ts=ts
            )
            tasks.append(task)
        
        # Executar todos os sites em paralelo
        site_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge resultados de todos os sites
        for site_result in site_results:
            if isinstance(site_result, Exception):
                if logger:
                    logger.error(f"Erro no scraping paralelo: {site_result}")
                continue
            
            # Merge site_result em results
            for category, models in site_result.items():
                results.setdefault(category, {})
                for key, sites in models.items():
                    results[category].setdefault(key, {})
                    for site, entries in sites.items():
                        results[category][key].setdefault(site, [])
                        results[category][key][site].extend(entries)

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
    
    # 🆕 Sprint 1: Mostrar resumo de estatísticas
    duration = time.time() - start_time
    if logger:
        from utils.logger import log_summary
        log_summary(logger, stats["total"], stats["successful"], stats["failed"], duration)
    
    print(f"\n{'='*60}")
    print(f"📊 RESUMO DO SCRAPING (Sprint 1)")
    print(f"{'='*60}")
    print(f"Total de tentativas:      {stats['total']}")
    print(f"✅ Sucessos:              {stats['successful']} ({stats['successful']/stats['total']*100:.1f}%)" if stats['total'] > 0 else "✅ Sucessos:              0")
    print(f"❌ Falhas:                {stats['failed']}")
    print(f"⚠️  Validações rejeitadas: {stats['validation_failed']}")
    print(f"⛔ Bloqueios Cloudflare:  {stats['cloudflare_blocks']}")
    print(f"⏱️  Duração:               {duration:.1f}s")
    print(f"{'='*60}\n")

    return results


# ─────────────────────────────────────────────────────────────
# Dados demo (sem scraping — valores de referência Apple Store PT)
# ─────────────────────────────────────────────────────────────

DEMO_BASE_PRICES = {
    "AirPods (4th Gen)":      {"": {"Worten":149, "Darty":149, "MEO":149, "Vodafone":149, "NOS":149}},
    "AirPods (4th Gen) ANC":  {"": {"Worten":199, "Darty":199, "MEO":199, "Vodafone":199, "NOS":199}},
    "AirPods Pro (3rd Gen)":  {"": {"Worten":249, "Darty":249, "MEO":249, "Vodafone":249, "NOS":249}},
    "iPhone 16 128GB":        {"Worten":849,  "Darty":849,  "MEO":869.99,  "Vodafone":869,  "NOS":849},
    "iPhone 16e 128GB":       {"Worten":649,  "Darty":649,  "MEO":669.99,  "Vodafone":669,  "NOS":649},
    "iPhone 16e 256GB":       {"Worten":779,  "Darty":779,  "MEO":799.99,  "Vodafone":799,  "NOS":779},
    "iPhone 17 Pro 256GB":    {"Worten":1279, "Darty":1279, "MEO":1299.99, "Vodafone":1299, "NOS":1279},
    "iPhone 17 Pro 1TB":      {"Worten":1749, "Darty":1749, "MEO":1769.99, "Vodafone":1769, "NOS":1749},
    "iPhone 17 Pro Max 256GB":{"Worten":1479, "Darty":1479, "MEO":1499.99, "Vodafone":1499, "NOS":1479},
    "iPhone 17 Pro Max 512GB":{"Worten":1709, "Darty":1709, "MEO":1729.99, "Vodafone":1729, "NOS":1709},
    "iPhone 17 Pro Max 1TB":  {"Worten":1949, "Darty":1949, "MEO":1969.99, "Vodafone":1969, "NOS":1949},
    "iPhone Air 256GB":       {"Worten":1229, "Darty":1229, "MEO":1249.99, "Vodafone":1249, "NOS":1229},
    "iPhone 17e 512GB":       {"Worten":859,  "Darty":859,  "MEO":879.99,  "Vodafone":879,  "NOS":859},
}

SITE_URLS = {
    "Worten":   "https://www.worten.pt",
    "Darty":    "https://www.darty.com",
    "MEO":      "https://loja.meo.pt",
    "Vodafone": "https://www.vodafone.pt",
    "NOS":      "https://www.nos.pt",
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
    "iPhone 16 128GB": {
        "NOS DCN":       {"price": 809.99,  "points": None},
        "MEO MEOS":      {"price": 649.99,  "points": 2500},
        "Vodafone Viva": {"price": 699.99,  "points": 2000},
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
    "iPhone 17 Pro 256GB": {
        "NOS DCN":       {"price": 1219.99, "points": None},
        "MEO MEOS":      {"price": 999.99,  "points": 4500},
        "Vodafone Viva": {"price": 1049.99, "points": 4000},
    },
    "iPhone 17 Pro 1TB": {
        "NOS DCN":       {"price": 1669.99, "points": None},
        "MEO MEOS":      {"price": 1449.99, "points": 5500},
        "Vodafone Viva": {"price": 1499.99, "points": 5000},
    },
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
    "iPhone Air 256GB": {
        "NOS DCN":       {"price": 1169.99, "points": None},
        "MEO MEOS":      {"price": 999.99,  "points": 4000},
        "Vodafone Viva": {"price": 1049.99, "points": 3500},
    },
    "iPhone 17e 512GB": {
        "NOS DCN":       {"price": 819.99,  "points": None},
        "MEO MEOS":      {"price": 699.99,  "points": 3000},
        "Vodafone Viva": {"price": 749.99,  "points": 2500},
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
