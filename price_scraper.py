#!/usr/bin/env python3
"""
💰 Price Scraper — Comparador de Preços
Suporta múltiplos sites e compara preços de um produto.

Dependências:
    pip install requests beautifulsoup4 lxml rich

Uso:
    python price_scraper.py "nome do produto"
    python price_scraper.py "airpods pro" --sites amazon ebay
    python price_scraper.py "iphone 15" --output resultados.json
"""

import argparse
import json
import time
import random
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌  Dependências em falta. Instala com:\n    pip install requests beautifulsoup4 lxml rich")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ─────────────────────────────────────────────
# Configuração global
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─────────────────────────────────────────────
# Modelo de dados
# ─────────────────────────────────────────────

@dataclass
class PriceResult:
    site: str
    title: str
    price: Optional[float]
    currency: str
    url: str
    rating: Optional[str] = None
    reviews: Optional[str] = None
    availability: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def price_display(self) -> str:
        if self.price is None:
            return "N/D"
        symbols = {"EUR": "€", "USD": "$", "GBP": "£"}
        sym = symbols.get(self.currency, self.currency + " ")
        return f"{sym}{self.price:,.2f}"


# ─────────────────────────────────────────────
# Utilitários
# ─────────────────────────────────────────────

def parse_price(text: str) -> tuple[Optional[float], str]:
    """Extrai valor numérico e moeda de uma string de preço.
    Suporta: '1.234,56', '1,234.56', '1234.56', '899,99', '999' (inteiro).
    """
    if not text:
        return None, "EUR"
    text = text.strip().replace("\xa0", " ").replace("\u202f", "")

    currency = "EUR"
    if "$" in text:
        currency = "USD"
    elif "£" in text:
        currency = "GBP"
    elif "€" in text or "EUR" in text.upper():
        currency = "EUR"

    cleaned = re.sub(r"[^\d.,]", "", text)

    # Formato PT com milhar: 1.234,56 ou 1.234 (sem decimais)
    if re.search(r"\d{1,3}(\.\d{3})+(,\d+)?$", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    # Formato EN com milhar: 1,234.56 ou 1,234
    elif re.search(r"\d{1,3}(,\d{3})+(\.\d+)?$", cleaned):
        cleaned = cleaned.replace(",", "")
    # Só vírgula decimal: 899,99
    elif re.search(r"^\d+,\d{1,2}$", cleaned):
        cleaned = cleaned.replace(",", ".")
    # Já está normalizado: 1234.56 ou 1234
    # else: não fazer nada

    try:
        return float(cleaned), currency
    except ValueError:
        return None, currency


def get_page(url: str, retries: int = 2) -> Optional[BeautifulSoup]:
    """Faz GET com retry e backoff aleatório."""
    for attempt in range(retries + 1):
        try:
            time.sleep(random.uniform(1.0, 2.5))
            resp = SESSION.get(url, timeout=10)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            if attempt == retries:
                print(f"  ⚠️  Erro ao aceder {url}: {e}")
            else:
                time.sleep(2 ** attempt)
    return None


# ─────────────────────────────────────────────
# Scrapers por site
# ─────────────────────────────────────────────

def scrape_amazon_pt(query: str) -> list[PriceResult]:
    """Scraper para amazon.es (mais acessível em PT)."""
    results = []
    url = f"https://www.amazon.es/s?k={quote_plus(query)}"
    soup = get_page(url)
    if not soup:
        return results

    items = soup.select("div[data-component-type='s-search-result']")[:5]
    for item in items:
        try:
            title_el = item.select_one("h2 span")
            price_whole = item.select_one(".a-price-whole")
            price_frac = item.select_one(".a-price-fraction")
            link_el = item.select_one("h2 a")
            rating_el = item.select_one(".a-icon-star-small span")
            reviews_el = item.select_one("[aria-label*='stars'] + span")

            if not title_el or not price_whole:
                continue

            price_str = price_whole.get_text() + (price_frac.get_text() if price_frac else "00")
            price_val, currency = parse_price(price_str + "€")
            href = "https://www.amazon.es" + link_el["href"] if link_el else url

            results.append(PriceResult(
                site="Amazon ES",
                title=title_el.get_text(strip=True)[:80],
                price=price_val,
                currency="EUR",
                url=href,
                rating=rating_el.get_text(strip=True) if rating_el else None,
                reviews=reviews_el.get_text(strip=True) if reviews_el else None,
            ))
        except Exception:
            continue
    return results


def scrape_ebay(query: str) -> list[PriceResult]:
    """Scraper para eBay."""
    results = []
    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}&_ipg=10"
    soup = get_page(url)
    if not soup:
        return results

    items = soup.select(".s-item")[:5]
    for item in items:
        try:
            title_el = item.select_one(".s-item__title")
            price_el = item.select_one(".s-item__price")
            link_el = item.select_one(".s-item__link")

            if not title_el or not price_el:
                continue
            title = title_el.get_text(strip=True)
            if title.lower() == "shop on ebay":
                continue

            price_val, currency = parse_price(price_el.get_text(strip=True))

            results.append(PriceResult(
                site="eBay",
                title=title[:80],
                price=price_val,
                currency=currency,
                url=link_el["href"] if link_el else url,
            ))
        except Exception:
            continue
    return results


def scrape_fnac(query: str) -> list[PriceResult]:
    """Scraper para Fnac Portugal."""
    results = []
    url = f"https://www.fnac.pt/SearchResult/ResultSet.aspx?SCat=0&Search={quote_plus(query)}"
    soup = get_page(url)
    if not soup:
        return results

    items = soup.select(".Article-item")[:5]
    for item in items:
        try:
            title_el = item.select_one(".Article-desc") or item.select_one(".Article-title")
            price_el = item.select_one(".userPrice") or item.select_one(".price")
            link_el = item.select_one("a")

            if not title_el or not price_el:
                continue

            price_val, currency = parse_price(price_el.get_text(strip=True))
            href = link_el["href"] if link_el else url
            if href.startswith("/"):
                href = "https://www.fnac.pt" + href

            results.append(PriceResult(
                site="Fnac PT",
                title=title_el.get_text(strip=True)[:80],
                price=price_val,
                currency="EUR",
                url=href,
            ))
        except Exception:
            continue
    return results


def scrape_worten(query: str) -> list[PriceResult]:
    """Scraper para Worten Portugal."""
    results = []
    url = f"https://www.worten.pt/search?query={quote_plus(query)}"
    soup = get_page(url)
    if not soup:
        return results

    items = soup.select(".w-product")[:5]
    for item in items:
        try:
            title_el = item.select_one(".w-product__title") or item.select_one("[class*='title']")
            price_el = item.select_one(".price") or item.select_one("[class*='price']")
            link_el = item.select_one("a[href]")

            if not title_el or not price_el:
                continue

            price_val, currency = parse_price(price_el.get_text(strip=True))
            href = link_el["href"] if link_el else url
            if href.startswith("/"):
                href = "https://www.worten.pt" + href

            results.append(PriceResult(
                site="Worten",
                title=title_el.get_text(strip=True)[:80],
                price=price_val,
                currency="EUR",
                url=href,
            ))
        except Exception:
            continue
    return results


# ─────────────────────────────────────────────
# Registo de scrapers disponíveis
# ─────────────────────────────────────────────

SCRAPERS = {
    "amazon":  scrape_amazon_pt,
    "ebay":    scrape_ebay,
    "fnac":    scrape_fnac,
    "worten":  scrape_worten,
}


# ─────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────

def print_results_rich(results: list[PriceResult], query: str) -> None:
    console = Console()
    console.print(Panel(
        f"[bold cyan]🔍 Resultados para:[/bold cyan] [yellow]{query}[/yellow]\n"
        f"[dim]{len(results)} resultado(s) encontrado(s) · {datetime.now().strftime('%H:%M %d/%m/%Y')}[/dim]",
        box=box.ROUNDED,
    ))

    if not results:
        console.print("[red]Nenhum resultado encontrado.[/red]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_lines=True)
    table.add_column("Site", style="bold cyan", width=12)
    table.add_column("Produto", style="white", max_width=45, overflow="fold")
    table.add_column("Preço", style="bold green", justify="right", width=12)
    table.add_column("⭐ Rating", justify="center", width=10)
    table.add_column("URL", style="dim blue", max_width=35, overflow="fold")

    valid = sorted([r for r in results if r.price is not None], key=lambda x: x.price)
    invalid = [r for r in results if r.price is None]

    best_price = valid[0].price if valid else None

    for r in valid + invalid:
        price_text = r.price_display
        if r.price is not None and r.price == best_price:
            price_text = f"[bold yellow]★ {price_text}[/bold yellow]"

        table.add_row(
            r.site,
            r.title,
            price_text,
            r.rating or "—",
            r.url,
        )

    console.print(table)

    if valid:
        best = valid[0]
        console.print(Panel(
            f"[bold green]💰 Melhor preço:[/bold green] [bold yellow]{best.price_display}[/bold yellow] "
            f"em [bold cyan]{best.site}[/bold cyan]\n"
            f"[dim]{best.title}[/dim]\n"
            f"[blue underline]{best.url}[/blue underline]",
            title="[bold]✅ Recomendação[/bold]",
            box=box.ROUNDED,
        ))


def print_results_plain(results: list[PriceResult], query: str) -> None:
    print(f"\n{'='*60}")
    print(f"  🔍 Resultados para: {query}")
    print(f"{'='*60}")
    valid = sorted([r for r in results if r.price is not None], key=lambda x: x.price)
    for i, r in enumerate(valid, 1):
        print(f"\n[{i}] {r.site}")
        print(f"    Produto : {r.title}")
        print(f"    Preço   : {r.price_display}")
        if r.rating:
            print(f"    Rating  : {r.rating}")
        print(f"    URL     : {r.url}")
    if valid:
        best = valid[0]
        print(f"\n{'='*60}")
        print(f"  ★ Melhor preço: {best.price_display} em {best.site}")
        print(f"{'='*60}\n")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="💰 Price Scraper — Comparador de preços entre múltiplos sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python price_scraper.py "airpods pro"
  python price_scraper.py "macbook air m3" --sites amazon fnac
  python price_scraper.py "samsung tv 55" --output precos.json
  python price_scraper.py "iphone 15" --sites amazon ebay worten fnac
        """,
    )
    parser.add_argument("query", help="Produto a pesquisar")
    parser.add_argument(
        "--sites",
        nargs="+",
        choices=list(SCRAPERS.keys()),
        default=list(SCRAPERS.keys()),
        help=f"Sites a pesquisar (default: todos). Opções: {', '.join(SCRAPERS.keys())}",
    )
    parser.add_argument("--output", help="Guardar resultados em ficheiro JSON")
    parser.add_argument("--no-color", action="store_true", help="Desativar output colorido")
    args = parser.parse_args()

    print(f"\n🔎  A pesquisar \"{args.query}\" em: {', '.join(args.sites)}...\n")

    all_results: list[PriceResult] = []
    for site_name in args.sites:
        scraper = SCRAPERS[site_name]
        print(f"  📡  {site_name.capitalize()}...", end=" ", flush=True)
        results = scraper(args.query)
        print(f"{len(results)} resultado(s)")
        all_results.extend(results)

    print()

    if HAS_RICH and not args.no_color:
        print_results_rich(all_results, args.query)
    else:
        print_results_plain(all_results, args.query)

    if args.output:
        data = {
            "query": args.query,
            "scraped_at": datetime.now().isoformat(),
            "sites": args.sites,
            "results": [asdict(r) for r in all_results],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅  Resultados guardados em: {args.output}")


if __name__ == "__main__":
    main()
