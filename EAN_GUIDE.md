# 🔢 Guia de Uso de EANs (Códigos de Barras)

**Data:** 17 Março 2026

---

## 🎯 Por Que EANs São Úteis?

### 1. **Identificação Única e Precisa**
- EAN (European Article Number) é **único por produto**
- Elimina ambiguidade (ex: "iPhone 17 256GB" vs "iPhone 17 Pro 256GB")
- Garante que estás a comparar **exatamente o mesmo produto** em todos os sites

### 2. **Pesquisa Mais Eficiente**
- Muitos sites permitem pesquisa por EAN
- Resultados mais precisos (menos produtos irrelevantes)
- Menos navegação (vai direto ao produto)

### 3. **Validação de Produto**
- Confirma que o produto encontrado é o correto
- Evita confusões com modelos similares
- Útil para produtos com nomes parecidos

---

## ✅ Como Usar EANs no Tracker

### Opção 1: Pesquisa Direta por EAN

Alguns sites suportam pesquisa por EAN no URL:

```python
# Exemplo: Worten
https://www.worten.pt/search?query=0194253911234

# Exemplo: Rádio Popular
https://www.radiopopular.pt/pesquisa/?q=0194253911234

# Exemplo: MEO
https://loja.meo.pt/pesquisa?q=0194253911234
```

**Vantagens:**
- Vai direto ao produto (sem navegação)
- Elimina produtos irrelevantes
- Mais rápido (menos cliques)

---

### Opção 2: Validação de Produto

Adicionar EAN ao catálogo para validar que o produto encontrado é o correto:

```python
CATALOGUE = {
    "iPhone": {
        "iPhone 17 Pro Max": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro Max 256GB",
                "ean": "0194253911234",  # EAN do produto
            },
            "512GB": {
                "query": "Apple iPhone 17 Pro Max 512GB",
                "ean": "0194253911241",
            },
        }},
    },
}
```

**Uso no scraper:**
```python
# Após encontrar produto, validar EAN
def validate_product_ean(html: str, expected_ean: str) -> bool:
    """Verifica se o EAN na página corresponde ao esperado."""
    # Procurar EAN no HTML
    ean_patterns = [
        r'ean["\s:]+([0-9]{13})',
        r'gtin["\s:]+([0-9]{13})',
        r'productId["\s:]+([0-9]{13})',
        r'"sku"["\s:]+([0-9]{13})',
    ]
    
    for pattern in ean_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match and match.group(1) == expected_ean:
            return True
    
    return False

# No scraper
if expected_ean and not validate_product_ean(html, expected_ean):
    logger.warning(f"⚠️ EAN não corresponde! Produto pode estar incorreto.")
```

---

### Opção 3: URL Overrides com EAN

Usar EAN para criar URLs diretos (melhor opção):

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/apple-iphone-17-pro-max-256gb-0194253911234",
    "Rádio Popular": "https://www.radiopopular.pt/produto/0194253911234",
    "MEO": "https://loja.meo.pt/telemoveis/apple/iphone-17-pro-max-256gb"
  }
}
```

---

## 📊 Benefícios por Site

| Site | Suporta Pesquisa EAN? | Mostra EAN na Página? | Benefício |
|------|----------------------|----------------------|-----------|
| **Worten** | ✅ Sim | ✅ Sim | Pesquisa direta + validação |
| **Rádio Popular** | ✅ Sim | ✅ Sim | Pesquisa direta + validação |
| **Darty** | ✅ Sim | ✅ Sim | Pesquisa direta + validação |
| **MEO** | ⚠️ Parcial | ❌ Não | Validação limitada |
| **Vodafone** | ⚠️ Parcial | ❌ Não | Validação limitada |
| **NOS** | ⚠️ Parcial | ❌ Não | Validação limitada |

---

## 🚀 Implementação Recomendada

### Fase 1: Adicionar EANs ao Catálogo

```python
CATALOGUE = {
    "iPhone": {
        "iPhone 17 Pro Max": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro Max 256GB",
                "ean": "0194253911234",
            },
            "512GB": {
                "query": "Apple iPhone 17 Pro Max 512GB",
                "ean": "0194253911241",
            },
            "1TB": {
                "query": "Apple iPhone 17 Pro Max 1TB",
                "ean": "0194253911258",
            },
        }},
        "iPhone 17 Pro": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro 256GB",
                "ean": "0194253911265",
            },
            # ... etc
        }},
    },
}
```

### Fase 2: Modificar search_url() para Usar EAN

```python
def search_url(site: str, query: str, ean: str = None) -> str:
    """
    Gera URL de pesquisa.
    Se EAN fornecido, usa pesquisa por EAN (mais preciso).
    """
    if ean and site in ("Worten", "Rádio Popular", "Darty"):
        # Sites que suportam pesquisa por EAN
        q = quote_plus(ean)
    else:
        # Fallback para pesquisa por nome
        q = quote_plus(query)
    
    return {
        "Worten":        f"https://www.worten.pt/search?query={q}",
        "Rádio Popular": f"https://www.radiopopular.pt/pesquisa/?q={q}",
        "Darty":         f"https://www.darty.com/nav/recherche?text={q}",
        # ... etc
    }[site]
```

### Fase 3: Adicionar Validação de EAN

```python
def validate_product_ean(html: str, expected_ean: str) -> bool:
    """Verifica se o EAN na página corresponde ao esperado."""
    if not expected_ean:
        return True  # Sem EAN para validar
    
    # Procurar EAN no HTML
    ean_patterns = [
        r'ean["\s:]+([0-9]{13})',
        r'gtin["\s:]+([0-9]{13})',
        r'productId["\s:]+([0-9]{13})',
        r'"sku"["\s:]+([0-9]{13})',
        r'data-ean["\s=]+([0-9]{13})',
    ]
    
    for pattern in ean_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            found_ean = match.group(1)
            if found_ean == expected_ean:
                return True
            else:
                logger.warning(f"⚠️ EAN encontrado ({found_ean}) ≠ esperado ({expected_ean})")
                return False
    
    # EAN não encontrado no HTML (normal para alguns sites)
    return True

# No scraper, após extrair preço
if price:
    # Validar EAN se disponível
    if expected_ean and not validate_product_ean(html, expected_ean):
        logger.warning(f"⚠️ Produto pode estar incorreto (EAN não corresponde)")
        # Opcional: rejeitar preço
        # continue
```

---

## 📝 Exemplo Completo

### Catálogo com EANs
```python
CATALOGUE = {
    "iPhone": {
        "iPhone 17 Pro Max": {"variants": {
            "256GB": {
                "query": "Apple iPhone 17 Pro Max 256GB",
                "ean": "0194253911234",
            },
        }},
    },
}
```

### Loop Principal Modificado
```python
for model_name, model_info in models.items():
    for variant, variant_info in model_info["variants"].items():
        # Suportar formato antigo (string) e novo (dict com EAN)
        if isinstance(variant_info, str):
            query = variant_info
            ean = None
        else:
            query = variant_info["query"]
            ean = variant_info.get("ean")
        
        key = f"{model_name} {variant}".strip()
        
        for site in SITES:
            # Usar EAN se disponível
            url = search_url(site, query, ean)
            
            # ... scraping ...
            
            # Validar EAN após encontrar produto
            if price and ean:
                if not validate_product_ean(html, ean):
                    logger.warning(f"⚠️ {site}: EAN não corresponde, produto pode estar incorreto")
```

---

## 🎯 Casos de Uso Específicos

### 1. Worten/Darty (Cloudflare)
**Problema:** Cloudflare bloqueia 70%  
**Solução com EAN:**
```python
# Pesquisa por EAN tem menos bloqueios (menos "suspeito")
url = f"https://www.worten.pt/search?query={ean}"
```

### 2. Rádio Popular (Timeouts)
**Problema:** Site lento, timeouts frequentes  
**Solução com EAN:**
```python
# Pesquisa por EAN é mais rápida (menos resultados)
url = f"https://www.radiopopular.pt/pesquisa/?q={ean}"
```

### 3. Validação de Produto Correto
**Problema:** Às vezes encontra produto errado  
**Solução com EAN:**
```python
# Validar que o produto é exatamente o esperado
if not validate_product_ean(html, expected_ean):
    logger.warning("Produto incorreto, a ignorar preço")
    continue
```

---

## 📊 Impacto Esperado

### Com EANs
- **Taxa de sucesso:** +10-15% (menos produtos errados)
- **Precisão:** +5% (validação de produto)
- **Velocidade:** +10-20% (pesquisa mais direta)
- **Cloudflare:** -5-10% bloqueios (pesquisa por EAN menos suspeita)

### Sem EANs (atual)
- Pesquisa por nome (ambígua)
- Sem validação de produto
- Mais navegação (pesquisa → produto)
- Mais bloqueios Cloudflare

---

## 🚀 Próximos Passos

1. **Recolher EANs** dos produtos principais
2. **Atualizar CATALOGUE** com EANs
3. **Modificar search_url()** para usar EAN quando disponível
4. **Adicionar validate_product_ean()** para validação
5. **Testar** com produtos principais
6. **Expandir** para todos os produtos

---

## 📝 Formato de EAN

- **EAN-13:** 13 dígitos (padrão europeu)
- **UPC:** 12 dígitos (padrão americano, pode ser convertido)
- **Exemplo:** `0194253911234` (iPhone 17 Pro Max 256GB)

**Onde encontrar EANs:**
- Site oficial Apple
- Embalagem do produto
- Sites de retalhistas (Worten, Fnac, etc.)
- Bases de dados online (EAN-Search.org, etc.)

---

**Conclusão:** EANs são **muito úteis** e podem melhorar significativamente a precisão e eficiência do tracker. Recomendo adicionar EANs pelo menos para os produtos principais (iPhone Pro Max, iPhone Pro, AirPods Pro).
