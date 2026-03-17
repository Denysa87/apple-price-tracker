#!/usr/bin/env python3
"""
Script de teste para scraping de produto individual.
Útil para debugging e validação de melhorias.

Uso:
    python tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site Worten
    python tests/test_single_product.py "AirPods Pro 3" --site "Rádio Popular" --headless False
    python tests/test_single_product.py "iPhone 17 Pro Max 256GB" --all-sites
"""

import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Adicionar diretório pai ao path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from utils.validators import validate_price, get_expected_range
from utils.logger import setup_logger

# Importar funções do scraper principal
import scraper


async def test_single_product(
    product_key: str,
    site: str,
    headless: bool = True,
    save_debug: bool = True
) -> dict:
    """
    Testa scraping de um único produto em um site específico.
    
    Args:
        product_key: Nome do produto (ex: "iPhone 17 Pro Max 256GB")
        site: Nome do site (ex: "Worten", "Rádio Popular")
        headless: Se True, executa browser em modo headless
        save_debug: Se True, guarda screenshot e HTML em caso de erro
    
    Returns:
        Dicionário com resultado do teste
    """
    logger = setup_logger(level=10 if not headless else 20)  # DEBUG se não headless
    
    logger.info(f"🧪 Testando: {product_key} em {site}")
    logger.info(f"   Headless: {headless} | Debug: {save_debug}")
    
    # Verificar se produto existe no catálogo
    found = False
    query = None
    for category, models in scraper.CATALOGUE.items():
        for model_name, model_info in models.items():
            for variant, q in model_info["variants"].items():
                key = f"{model_name} {variant}".strip()
                if key == product_key:
                    found = True
                    query = q
                    logger.info(f"   Categoria: {category}")
                    logger.info(f"   Query: {query}")
                    break
            if found:
                break
        if found:
            break
    
    if not found:
        logger.error(f"❌ Produto '{product_key}' não encontrado no catálogo")
        return {"success": False, "error": "Produto não encontrado"}
    
    # Verificar range de preços esperado
    min_price, max_price = get_expected_range(product_key)
    logger.info(f"   Range esperado: {min_price}€ - {max_price}€")
    
    # Verificar se existe override
    overrides = {}
    if scraper.OVERRIDES_FILE.exists():
        import json
        with open(scraper.OVERRIDES_FILE, encoding="utf-8") as f:
            raw_ov = json.load(f)
            overrides = {k: v for k, v in raw_ov.items() if not k.startswith("_")}
    
    override_url = overrides.get(product_key, {}).get(site)
    url = override_url if override_url else scraper.search_url(site, query)
    is_override = bool(override_url)
    
    logger.info(f"   URL: {url}")
    logger.info(f"   Tipo: {'Override' if is_override else 'Automático'}")
    
    result = {
        "product": product_key,
        "site": site,
        "url": url,
        "is_override": is_override,
        "timestamp": datetime.now().isoformat(),
        "success": False,
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1280,800",
            ],
        )
        
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-PT",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
        )
        
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        page = await context.new_page()
        
        # Aplicar stealth se disponível
        if scraper.STEALTH_AVAILABLE:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        
        try:
            logger.info(f"🌐 Navegando para {url[:80]}...")
            
            # Determinar wait mode
            wait_mode = "networkidle" if site in ("Rádio Popular", "MEO", "Vodafone", "NOS") else "domcontentloaded"
            await page.goto(url, wait_until=wait_mode, timeout=25000)
            
            # Fechar banner de cookies
            await scraper.dismiss_cookie_banner(page)
            
            # Espera extra (melhorada no Sprint 1)
            extra_wait = 5000 if site in ("Rádio Popular", "MEO", "Vodafone", "NOS") else 3000
            logger.info(f"⏱️  Aguardando {extra_wait}ms...")
            await page.wait_for_timeout(extra_wait)
            
            html = await page.content()
            result["html_length"] = len(html)
            
            # Detectar Cloudflare
            if scraper.is_cloudflare_blocked(html):
                logger.warning("⛔ Cloudflare detectado, aguardando 15s...")
                await page.wait_for_timeout(15000)
                html = await page.content()
                
                if scraper.is_cloudflare_blocked(html):
                    result["error"] = "Cloudflare bloqueou"
                    logger.error("❌ Cloudflare ainda ativo após 15s")
                    
                    if save_debug:
                        debug_dir = Path(__file__).parent.parent / "debug" / datetime.now().strftime("%Y%m%d_%H%M%S")
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(path=debug_dir / f"{site}_cloudflare.png")
                        (debug_dir / f"{site}_cloudflare.html").write_text(html, encoding="utf-8")
                        logger.info(f"🔍 Debug guardado em {debug_dir}")
                    
                    await browser.close()
                    return result
            
            # Se não é override, tentar navegar para página do produto
            if not is_override:
                site_bases = {
                    "Worten": "https://www.worten.pt",
                    "Rádio Popular": "https://www.radiopopular.pt",
                    "Darty": "https://www.darty.com",
                    "MEO": "https://loja.meo.pt",
                    "Vodafone": "https://www.vodafone.pt",
                    "NOS": "https://www.nos.pt",
                }
                
                logger.info("🔍 Procurando link do produto...")
                product_url = scraper.find_product_url(html, query, site, site_bases.get(site, ""))
                
                if product_url and product_url != page.url:
                    logger.info(f"➡️  Navegando para produto: {product_url[:80]}...")
                    try:
                        await page.goto(product_url, wait_until=wait_mode, timeout=20000)
                        await page.wait_for_timeout(3000)
                        html = await page.content()
                        result["product_url"] = product_url
                    except Exception as e:
                        logger.warning(f"⚠️  Falha ao navegar para produto: {e}")
            
            # Extrair preços - usar extrator específico se disponível
            logger.info("💰 Extraindo preços...")
            
            # Verificar se deve usar extrator específico
            try:
                from utils.price_extractors import should_use_specific_extractor, extract_nos_online_price, extract_vodafone_online_price
                
                if should_use_specific_extractor(site, page.url):
                    logger.info(f"🎯 Usando extrator específico para {site}")
                    
                    if site == "NOS":
                        price = await extract_nos_online_price(page)
                        if price:
                            logger.info(f"   ✅ Extrator NOS: {price:.2f}€")
                            result["prices_found"] = [price]
                            result["extractor_used"] = "NOS specific"
                        else:
                            logger.warning("   ⚠️  Extrator NOS falhou, usando método genérico")
                            prices = scraper.extract_prices_from_html(html)
                            result["prices_found"] = prices
                            result["extractor_used"] = "generic (NOS fallback)"
                            price = scraper.best_match(prices, query)
                    
                    elif site == "Vodafone":
                        price = await extract_vodafone_online_price(page)
                        if price:
                            logger.info(f"   ✅ Extrator Vodafone: {price:.2f}€")
                            result["prices_found"] = [price]
                            result["extractor_used"] = "Vodafone specific"
                        else:
                            logger.warning("   ⚠️  Extrator Vodafone falhou, usando método genérico")
                            prices = scraper.extract_prices_from_html(html)
                            result["prices_found"] = prices
                            result["extractor_used"] = "generic (Vodafone fallback)"
                            price = scraper.best_match(prices, query)
                    else:
                        # Não deveria chegar aqui
                        prices = scraper.extract_prices_from_html(html)
                        result["prices_found"] = prices
                        result["extractor_used"] = "generic"
                        price = scraper.best_match(prices, query)
                else:
                    # Usar método genérico
                    prices = scraper.extract_prices_from_html(html)
                    result["prices_found"] = prices
                    result["extractor_used"] = "generic"
                    logger.info(f"   Preços encontrados: {prices}")
                    price = scraper.best_match(prices, query)
                    
            except ImportError:
                logger.warning("⚠️  Extratores específicos não disponíveis, usando método genérico")
                prices = scraper.extract_prices_from_html(html)
                result["prices_found"] = prices
                result["extractor_used"] = "generic (no extractors)"
                logger.info(f"   Preços encontrados: {prices}")
                price = scraper.best_match(prices, query)
            result["selected_price"] = price
            
            if price:
                logger.info(f"   Preço selecionado: {price:.2f}€")
                
                # Validar preço
                is_valid, reason = validate_price(price, product_key)
                result["price_valid"] = is_valid
                result["validation_reason"] = reason
                
                if is_valid:
                    logger.info(f"✅ Preço válido: {price:.2f}€")
                    result["success"] = True
                    result["final_price"] = price
                    result["final_url"] = page.url
                else:
                    logger.warning(f"⚠️  Preço rejeitado: {reason}")
                    
                    if save_debug:
                        debug_dir = Path(__file__).parent.parent / "debug" / datetime.now().strftime("%Y%m%d_%H%M%S")
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(path=debug_dir / f"{site}_invalid_price.png")
                        (debug_dir / f"{site}_invalid_price.html").write_text(html, encoding="utf-8")
                        logger.info(f"🔍 Debug guardado em {debug_dir}")
            else:
                logger.warning("❌ Nenhum preço encontrado")
                result["error"] = "Nenhum preço encontrado"
                
                if save_debug:
                    debug_dir = Path(__file__).parent.parent / "debug" / datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=debug_dir / f"{site}_no_price.png")
                    (debug_dir / f"{site}_no_price.html").write_text(html, encoding="utf-8")
                    logger.info(f"🔍 Debug guardado em {debug_dir}")
        
        except Exception as e:
            logger.error(f"❌ Erro: {str(e)}")
            result["error"] = str(e)
            
            if save_debug:
                try:
                    debug_dir = Path(__file__).parent.parent / "debug" / datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=debug_dir / f"{site}_error.png")
                    html = await page.content()
                    (debug_dir / f"{site}_error.html").write_text(html, encoding="utf-8")
                    logger.info(f"🔍 Debug guardado em {debug_dir}")
                except Exception:
                    pass
        
        finally:
            await browser.close()
    
    return result


async def test_all_sites(product_key: str, headless: bool = True) -> dict:
    """Testa scraping de um produto em todos os sites."""
    results = {}
    for site in scraper.SITES:
        print(f"\n{'='*60}")
        result = await test_single_product(product_key, site, headless, save_debug=False)
        results[site] = result
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="🧪 Teste de scraping de produto individual",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site Worten
  python tests/test_single_product.py "AirPods Pro 3" --site "Rádio Popular" --no-headless
  python tests/test_single_product.py "iPhone 17 Pro Max 256GB" --all-sites
        """
    )
    
    parser.add_argument("product", help="Nome do produto (ex: 'iPhone 17 Pro Max 256GB')")
    parser.add_argument("--site", help="Site a testar (ex: 'Worten', 'Rádio Popular')")
    parser.add_argument("--all-sites", action="store_true", help="Testar em todos os sites")
    parser.add_argument("--no-headless", action="store_true", help="Mostrar browser (útil para debug)")
    parser.add_argument("--no-debug", action="store_true", help="Não guardar screenshots/HTML")
    
    args = parser.parse_args()
    
    if not args.site and not args.all_sites:
        parser.error("Especifica --site NOME ou --all-sites")
    
    headless = not args.no_headless
    save_debug = not args.no_debug
    
    if args.all_sites:
        results = asyncio.run(test_all_sites(args.product, headless))
        
        print(f"\n{'='*60}")
        print("📊 RESUMO")
        print(f"{'='*60}")
        
        successful = sum(1 for r in results.values() if r.get("success"))
        total = len(results)
        
        for site, result in results.items():
            status = "✅" if result.get("success") else "❌"
            price = f"{result.get('final_price', 0):.2f}€" if result.get("success") else result.get("error", "Falhou")
            print(f"{status} {site:20s} {price}")
        
        print(f"\n🎯 Taxa de sucesso: {successful}/{total} ({successful/total*100:.1f}%)")
    else:
        result = asyncio.run(test_single_product(args.product, args.site, headless, save_debug))
        
        print(f"\n{'='*60}")
        print("📊 RESULTADO")
        print(f"{'='*60}")
        print(f"Produto: {result['product']}")
        print(f"Site: {result['site']}")
        print(f"Sucesso: {'✅ Sim' if result['success'] else '❌ Não'}")
        
        if result.get("success"):
            print(f"Preço: {result['final_price']:.2f}€")
            print(f"URL: {result['final_url']}")
        else:
            print(f"Erro: {result.get('error', 'Desconhecido')}")
        
        if result.get("prices_found"):
            print(f"Preços encontrados: {result['prices_found']}")


if __name__ == "__main__":
    main()
