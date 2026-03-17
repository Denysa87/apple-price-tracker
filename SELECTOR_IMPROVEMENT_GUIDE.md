# 🎯 Guia: Melhorar Seletores para Preço Exato

## Problema Atual

O scraper extrai **todos os preços** da página e escolhe o mínimo:
```
Preços encontrados: [1423.0, 1429.0, ...]
Preço selecionado: 1423.0€  ❌ (deveria ser 1429.0€)
```

## Solução: Seletores Específicos por Site

Em vez de extrair todos os preços, vamos usar **seletores CSS/XPath** para extrair apenas o preço principal.

---

## 📝 Passo a Passo

### 1. Identificar o Seletor Correto

**Método A: Usar DevTools do Browser**

1. Abre a página do produto no Chrome/Firefox
2. Clica com botão direito no preço → "Inspecionar"
3. Vê o HTML do elemento:
   ```html
   <span class="price-value">€1.429,00</span>
   ```
4. Identifica um seletor único:
   - Por classe: `.price-value`
   - Por atributo: `[data-price]`
   - Por estrutura: `.product-price > .price-value`

**Método B: Usar o Playwright Inspector**

```python
# No teste, adiciona:
await page.pause()  # Abre inspector
```

### 2. Testar o Seletor

```python
# Testa se o seletor funciona
price_element = await page.query_selector('.price-value')
if price_element:
    price_text = await price_element.text_content()
    print(f"Preço encontrado: {price_text}")
```

### 3. Adicionar ao Scraper

Modifica a função `extract_prices_from_html()` para usar Playwright diretamente:

```python
async def extract_price_with_selector(page, site: str) -> Optional[float]:
    """
    Extrai preço usando seletor específico do site.
    Mais preciso que regex no HTML.
    """
    selectors = {
        "Worten": [
            ".product-price .price-value",
            "[data-test-id='product-price']",
            ".price-box .price",
        ],
        "MEO": [
            ".product-price",
            "[class*='price']",
        ],
        # Adicionar outros sites...
    }
    
    for selector in selectors.get(site, []):
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                price = _parse_pt_price(text)
                if price:
                    return price
        except Exception:
            continue
    
    return None
```

---

## 🔧 Implementação Prática

### Opção 1: Seletores Prioritários (Recomendado)

Adiciona seletores específicos **antes** da extração genérica:

```python
# No scraper.py, função scrape_all_async()

# Depois de carregar a página...
html = await page.content()

# 🆕 Tentar seletor específico primeiro
specific_price = await extract_price_with_selector(page, site)
if specific_price:
    price = specific_price
else:
    # Fallback: extração genérica
    prices = extract_prices_from_html(html)
    price = best_match(prices, query)
```

### Opção 2: Seletores por Site

Cria dicionário de seletores:

```python
PRICE_SELECTORS = {
    "Worten": {
        "primary": ".product-price .price-value",
        "fallback": [".price-box .price", "[itemprop='price']"]
    },
    "MEO": {
        "primary": ".product-price",
        "fallback": [".price", "[class*='price']"]
    },
    # ...
}
```

---

## 📊 Exemplo Completo: Worten

### 1. Identificar Seletor

Baseado na imagem que partilhaste, o preço está em:
```html
<span class="price-value">€1.429,00</span>
```

Seletor: `.price-value` ou `.product-price .price-value`

### 2. Adicionar ao Código

```python
async def extract_worten_price(page) -> Optional[float]:
    """Extrai preço principal da Worten."""
    selectors = [
        ".product-price .price-value",  # Mais específico
        ".price-value",                  # Genérico
        "[data-price]",                  # Atributo data
    ]
    
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.text_content()
                # Remove "€" e espaços
                text = text.replace('€', '').strip()
                price = _parse_pt_price(text)
                if price and 1400 <= price <= 1600:  # Validação
                    return price
        except Exception:
            continue
    
    return None
```

### 3. Integrar no Scraper

```python
# No loop principal do scraper
if site == "Worten" and not is_override:
    # Tentar seletor específico
    price = await extract_worten_price(page)
    if not price:
        # Fallback: método genérico
        prices = extract_prices_from_html(html)
        price = best_match(prices, query)
else:
    # Outros sites: método genérico
    prices = extract_prices_from_html(html)
    price = best_match(prices, query)
```

---

## ⚠️ Considerações Importantes

### Vantagens dos Seletores Específicos
✅ **Precisão 100%** - Extrai exatamente o preço principal  
✅ **Mais rápido** - Não precisa processar todo o HTML  
✅ **Menos falsos positivos** - Ignora preços de acessórios  

### Desvantagens
❌ **Manutenção** - Se site mudar estrutura, seletor quebra  
❌ **Específico por site** - Precisa configurar cada site  
❌ **Mais código** - Mais complexo que método genérico  

---

## 🎯 Recomendação

**Para o teu caso:**

1. **Curto prazo:** Aceita margem de erro de 0.4% (6€)
   - Mais simples
   - Funciona para todos os sites
   - Suficiente para price tracking

2. **Médio prazo:** Adiciona seletores para sites principais
   - Worten, MEO, Darty
   - Melhora precisão gradualmente
   - Mantém fallback genérico

3. **Longo prazo:** Sistema híbrido
   - Seletores específicos quando disponíveis
   - Fallback genérico quando falham
   - Melhor dos dois mundos

---

## 🚀 Próximo Passo

Queres que implemente os seletores específicos para a Worten agora? Ou preferes manter o método genérico (mais simples, 99.6% preciso)?
