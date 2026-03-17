"""
Funções auxiliares para extração de preços específicos por site.
Sprint 5: Seletores específicos para NOS e Vodafone.
"""

from typing import Optional
import re


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


async def extract_nos_online_price(page) -> Optional[float]:
    """
    Extrai o preço ONLINE da NOS (não DCN/fidelização).
    
    A página da NOS tem múltiplos preços:
    - Preço online (o que queremos)
    - Preço DCN (com fidelização - mais barato)
    
    Estratégia:
    1. Procurar elemento com texto "Preço online"
    2. Extrair preço associado
    3. Fallback: preço máximo (online > DCN)
    """
    
    try:
        # Estratégia 1: Procurar por "Preço online" no HTML
        html = await page.content()
        
        # Padrão: "Preço online" seguido de preço
        # Exemplo: <div>Preço online</div><div>€739,99</div>
        pattern = r'Preço\s+online[^€]*€?\s*([\d.,]+)'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            price = _parse_pt_price(match.group(1))
            if price and price > 100:  # Sanity check
                return price
        
        # Estratégia 2: Usar Playwright para encontrar elemento
        # Procurar elemento que contém "Preço online"
        elements = await page.query_selector_all('text=/Preço online/i')
        for element in elements:
            # Tentar encontrar preço próximo
            parent = await element.evaluate('el => el.parentElement')
            if parent:
                text = await page.evaluate('el => el.textContent', parent)
                prices = re.findall(r'€?\s*([\d.,]+)\s*€?', text)
                for p in prices:
                    price = _parse_pt_price(p)
                    if price and price > 100:
                        return price
        
        # Estratégia 3: Fallback - preço máximo
        # Online geralmente é mais caro que DCN
        prices_text = re.findall(r'€?\s*([\d.,]+)\s*€', html)
        prices = []
        for p in prices_text:
            price = _parse_pt_price(p)
            if price and 100 < price < 2000:  # Range razoável para iPhones
                prices.append(price)
        
        if prices:
            # Retornar o preço máximo (online > DCN)
            return max(prices)
        
    except Exception as e:
        print(f"Erro ao extrair preço NOS: {e}")
    
    return None


async def extract_vodafone_online_price(page) -> Optional[float]:
    """
    Extrai o preço ONLINE da Vodafone (não Viva/fidelização).
    
    Similar à NOS, Vodafone tem:
    - Preço online (o que queremos)
    - Preço Viva (com fidelização - mais barato)
    """
    try:
        html = await page.content()
        
        # Estratégia 1: Procurar por "Preço" ou "online" no HTML
        # Vodafone pode ter estrutura diferente da NOS
        pattern = r'(?:Preço|online)[^€]*€?\s*([\d.,]+)'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        prices = []
        for match in matches:
            price = _parse_pt_price(match)
            if price and 100 < price < 2000:
                prices.append(price)
        
        if prices:
            # Retornar o preço máximo (online > Viva)
            return max(prices)
        
    except Exception as e:
        print(f"Erro ao extrair preço Vodafone: {e}")
    
    return None


def should_use_specific_extractor(site: str, url: str) -> bool:
    """
    Determina se deve usar extrator específico para o site.
    
    Usar extrator específico quando:
    - Site é NOS ou Vodafone
    - URL é de produto individual (não pesquisa)
    """
    if site not in ["NOS", "Vodafone"]:
        return False
    
    # Verificar se é URL de produto (não pesquisa)
    product_indicators = [
        "/produto/",
        "/telemoveis/",
        "/equipamentos/",
        "?pt=cn",  # NOS product page
    ]
    
    return any(indicator in url for indicator in product_indicators)
