"""
Validação de preços para o Apple Price Tracker.
Previne extração de preços incorretos (ex: 1499€ para todos os produtos).
"""

from typing import Optional


# Ranges de preços esperados por categoria de produto (em euros)
# 🆕 Sprint 8: Expandidos para aceitar preços válidos do mercado (799.99€, 149.99€, etc.)
PRICE_RANGES = {
    # AirPods - ranges expandidos para aceitar promoções e preços reais
    "airpods 4": (130, 200),  # Sprint 8: Expandido de (120,180) para aceitar 149.99€
    "airpods 4 anc": (170, 250),  # Sprint 8: Expandido para aceitar variações
    "airpods pro": (140, 300),
    "airpods max": (400, 650),
    
    # iPhones Pro Max
    "iphone 17 pro max 256gb": (1400, 1600),
    "iphone 17 pro max 512gb": (1650, 1850),
    "iphone 17 pro max 1tb": (1900, 2100),
    "iphone 16 pro max": (1300, 1700),
    
    # iPhones Pro
    "iphone 17 pro 256gb": (1200, 1400),
    "iphone 17 pro 512gb": (1450, 1650),
    "iphone 17 pro 1tb": (1700, 1900),
    "iphone 16 pro": (1100, 1500),
    
    # iPhones Standard
    "iphone 17 128gb": (900, 1100),
    "iphone 17 256gb": (1050, 1300),  # Sprint 8: Expandido para aceitar 1249.99€
    "iphone 17 512gb": (1300, 1500),
    "iphone 17 air": (1000, 1350),
    "iphone 17e": (550, 1150),  # Sprint 8: Expandido para aceitar 989.99€ e variações
    "iphone 16 128gb": (750, 1050),  # Sprint 8: Expandido de (750,1000) para aceitar 799.99€
    "iphone 16 256gb": (950, 1150),
    "iphone 16 512gb": (1150, 1350),
    "iphone 16e": (550, 1050),
    "iphone 15": (650, 1150),
    
    # Apple Watch
    "apple watch se": (250, 380),
    "apple watch series": (400, 600),
    "apple watch ultra": (800, 1000),
}


def validate_price(price: float, product_key: str) -> tuple[bool, Optional[str]]:
    """
    Valida se o preço está no range esperado para o produto.
    
    Args:
        price: Preço extraído (em euros)
        product_key: Chave do produto (ex: "iPhone 17 Pro Max 256GB")
    
    Returns:
        (is_valid, reason): Tupla com booleano de validação e razão da rejeição
    
    Examples:
        >>> validate_price(1479.0, "iPhone 17 Pro Max 256GB")
        (True, None)
        >>> validate_price(1499.0, "AirPods 4")
        (False, "Preço 1499.00€ fora do range esperado (120-180€)")
    """
    if price is None:
        return False, "Preço é None"
    
    if price <= 0:
        return False, f"Preço inválido: {price:.2f}€"
    
    # Normalizar chave do produto para lowercase
    key_lower = product_key.lower()
    
    # Encontrar o range apropriado
    min_price, max_price = None, None
    
    for pattern, (min_p, max_p) in PRICE_RANGES.items():
        if pattern in key_lower:
            min_price, max_p = min_p, max_p
            max_price = max_p
            break
    
    # Se não encontrou range específico, usar heurísticas gerais
    if min_price is None:
        if "pro max" in key_lower or "ultra" in key_lower:
            min_price, max_price = 800, 2100
        elif "pro" in key_lower and "iphone" in key_lower:
            min_price, max_price = 600, 1900
        elif "iphone" in key_lower:
            min_price, max_price = 400, 1500
        elif "watch" in key_lower:
            min_price, max_price = 150, 1000
        elif "airpods" in key_lower:
            min_price, max_price = 100, 650
        else:
            # Range genérico para produtos Apple
            min_price, max_price = 50, 2500
    
    # Validar se está no range
    if price < min_price or price > max_price:
        return False, f"Preço {price:.2f}€ fora do range esperado ({min_price}-{max_price}€)"
    
    return True, None


def is_likely_accessory_price(price: float, product_key: str) -> bool:
    """
    Detecta se o preço parece ser de um acessório em vez do produto principal.
    
    Args:
        price: Preço extraído
        product_key: Chave do produto
    
    Returns:
        True se parece ser preço de acessório
    
    Examples:
        >>> is_likely_accessory_price(29.99, "iPhone 17 Pro Max 256GB")
        True  # Provavelmente uma capa ou cabo
        >>> is_likely_accessory_price(1479.0, "iPhone 17 Pro Max 256GB")
        False  # Preço plausível para o iPhone
    """
    key_lower = product_key.lower()
    
    # Preços muito baixos para produtos principais
    if "iphone" in key_lower and price < 300:
        return True
    if "watch" in key_lower and price < 100:
        return True
    if "airpods" in key_lower and price < 80:
        return True
    
    return False


def get_expected_range(product_key: str) -> tuple[float, float]:
    """
    Retorna o range de preços esperado para um produto.
    
    Args:
        product_key: Chave do produto
    
    Returns:
        (min_price, max_price): Tupla com preços mínimo e máximo esperados
    """
    key_lower = product_key.lower()
    
    for pattern, (min_p, max_p) in PRICE_RANGES.items():
        if pattern in key_lower:
            return min_p, max_p
    
    # Fallback para heurísticas
    if "pro max" in key_lower or "ultra" in key_lower:
        return 800, 2100
    elif "pro" in key_lower and "iphone" in key_lower:
        return 600, 1900
    elif "iphone" in key_lower:
        return 400, 1500
    elif "watch" in key_lower:
        return 150, 1000
    elif "airpods" in key_lower:
        return 100, 650
    
    return 50, 2500
