# 🚀 Otimização de Performance - Apple Price Tracker

**Problema:** Scraper demora ~2 horas no GitHub Actions  
**Meta:** Reduzir para **15-30 minutos**

---

## 📊 Análise Atual

### Cálculo de Tempo
```
3 categorias × 10 produtos × 6 sites = 180 requests
Tempo por request: 30s (timeout) + 5s (espera) + 2.5s (delay) = 37.5s
Total: 180 × 37.5s = 6,750s = 1.87 horas ⚠️
```

### Gargalos Identificados

| Gargalo | Impacto | Linha | Tempo Perdido |
|---------|---------|-------|---------------|
| **Execução sequencial** | 🔴 CRÍTICO | 754 | ~90 min |
| **Timeouts excessivos** | 🔴 CRÍTICO | 766-774 | ~30 min |
| **Esperas extras** | 🟡 ALTO | 782 | ~15 min |
| **Navegação dupla** | 🟡 ALTO | 778, 824 | ~20 min |
| **Delays entre sites** | 🟢 MÉDIO | 945 | ~7.5 min |

---

## ✅ Otimizações Propostas

### 1. **Paralelização com asyncio.gather()** 🔴 CRÍTICO
**Impacto:** Reduz tempo de **1.87h → 20-30min** (-70%)

```python
async def scrape_product_parallel(product_key, query, sites, overrides):
    """Scrape um produto em todos os sites em paralelo."""
    tasks = []
    for site in sites:
        task = scrape_single_site(product_key, query, site, overrides)
        tasks.append(task)
    
    # Executar todos os sites em paralelo
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# No loop principal:
for category, models in CATALOGUE.items():
    for model_name, model_info in models.items():
        for variant, query in model_info["variants"].items():
            key = f"{model_name} {variant}".strip()
            
            # Scrape todos os sites em paralelo
            results = await scrape_product_parallel(key, query, SITES, overrides)
```

**Benefícios:**
- 6 sites em paralelo em vez de sequencial
- Tempo = max(site_times) em vez de sum(site_times)
- **Redução: 6x mais rápido**

---

### 2. **Reduzir Timeouts** 🔴 CRÍTICO
**Impacto:** Reduz tempo de **30-40s → 15-20s** por site (-50%)

```python
# ANTES (linhas 766-774)
timeout_map = {
    "Worten": 40000,        # 40s
    "Darty": 40000,         # 40s
    "Rádio Popular": 35000, # 35s
    "MEO": 30000,           # 30s
    "Vodafone": 30000,      # 30s
    "NOS": 30000,           # 30s
}

# DEPOIS (otimizado)
timeout_map = {
    "Worten": 20000,        # 20s (-50%)
    "Darty": 20000,         # 20s (-50%)
    "Rádio Popular": 25000, # 25s (-29%)
    "MEO": 15000,           # 15s (-50%)
    "Vodafone": 15000,      # 15s (-50%)
    "NOS": 15000,           # 15s (-50%)
}
```

**Justificação:**
- Sites modernos carregam em 5-10s
- Timeouts de 30-40s são excessivos
- Se falhar em 15-20s, provavelmente é Cloudflare (não vai resolver com mais tempo)

---

### 3. **Reduzir Esperas Extras** 🟡 ALTO
**Impacto:** Reduz tempo de **5-7s → 2-3s** por site (-60%)

```python
# ANTES (linha 782)
extra_wait = 7000 if site in ("Rádio Popular", "MEO") else 5000

# DEPOIS (otimizado)
extra_wait = 3000 if site in ("Rádio Popular", "MEO") else 2000
```

**Justificação:**
- `wait_for_selector()` já aguarda elementos carregarem
- Espera extra de 5-7s é redundante
- 2-3s é suficiente para JavaScript renderizar

---

### 4. **URL Overrides para Sites Problemáticos** 🟡 ALTO
**Impacto:** Elimina navegação dupla (-50% tempo em sites com override)

```python
# Usar URL overrides para sites que sempre falham
# Worten, Darty → Cloudflare sempre bloqueia
# Rádio Popular → Timeout frequente

# Em url_overrides.json:
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/...",
    "Darty": "https://www.darty.com/...",
    "Rádio Popular": "https://www.radiopopular.pt/produto/..."
  }
}
```

**Benefícios:**
- Elimina navegação de pesquisa → produto
- Vai direto para página do produto
- **Redução: 50% tempo em sites com override**

---

### 5. **Cloudflare Wait Reduzido** 🟢 MÉDIO
**Impacto:** Reduz tempo de **30s → 15s** em bloqueios Cloudflare (-50%)

```python
# ANTES (linha 802)
await page.wait_for_timeout(30000)  # 30s

# DEPOIS (otimizado)
await page.wait_for_timeout(15000)  # 15s
```

**Justificação:**
- Cloudflare resolve em 5-10s ou nunca resolve
- 30s é excessivo
- Se não resolver em 15s, usar URL override

---

### 6. **Limitar Produtos/Sites no GitHub Actions** 🟢 MÉDIO
**Impacto:** Reduz número de requests (-50% requests)

```python
# Opção 1: Scrape apenas produtos principais
PRIORITY_PRODUCTS = [
    "iPhone 17 Pro Max 256GB",
    "iPhone 17 Pro 256GB",
    "iPhone 17 256GB",
    "AirPods Pro 3",
    "Apple Watch Ultra 3 49mm",
]

# Opção 2: Scrape apenas sites que funcionam
WORKING_SITES = ["MEO", "NOS", "Vodafone"]  # Excluir Worten/Darty (Cloudflare)

# No GitHub Actions workflow:
if os.getenv("GITHUB_ACTIONS"):
    SITES = WORKING_SITES
    # Ou filtrar produtos
```

---

### 7. **Cache de Resultados Recentes** 🟢 BAIXO
**Impacto:** Evita re-scraping de produtos que não mudaram

```python
def should_scrape(key, site, last_scraped_time):
    """Só scrape se passou mais de 6h desde última vez."""
    if not last_scraped_time:
        return True
    
    hours_since = (datetime.now() - last_scraped_time).total_seconds() / 3600
    return hours_since >= 6  # Scrape a cada 6h

# No loop:
if should_scrape(key, site, last_time):
    # Fazer scraping
else:
    # Usar preço anterior
```

---

## 📈 Estimativa de Impacto

### Cenário 1: Otimizações Críticas (1 + 2 + 3)
```
Paralelização: 6x mais rápido
Timeouts reduzidos: -50% tempo
Esperas reduzidas: -60% tempo

Tempo atual: 1.87h = 112 min
Após otimizações: 112 / 6 × 0.5 × 0.4 = 3.7 min por produto
Total: 3.7 × 30 produtos = 111 min / 6 (paralelo) = 18.5 min ✅
```

### Cenário 2: Todas as Otimizações (1-7)
```
+ URL overrides: -50% navegação
+ Cloudflare reduzido: -50% bloqueios
+ Limitar sites: -50% requests

Tempo estimado: 18.5 × 0.5 × 0.5 = 4.6 min
Com margem de segurança: ~10-15 min ✅
```

---

## 🛠️ Implementação Recomendada

### Fase 1: Quick Wins (1-2 horas)
1. ✅ Reduzir timeouts (2 → 3)
2. ✅ Reduzir esperas extras (3)
3. ✅ Cloudflare wait reduzido (5)

**Impacto:** 112 min → 40-50 min (-55%)

### Fase 2: Paralelização (2-4 horas)
4. ✅ Implementar `scrape_product_parallel()` (1)
5. ✅ Refatorar loop principal

**Impacto:** 40-50 min → 15-20 min (-65%)

### Fase 3: Otimizações Avançadas (opcional)
6. ⏳ URL overrides para sites problemáticos (4)
7. ⏳ Limitar produtos/sites no CI (6)
8. ⏳ Cache de resultados (7)

**Impacto:** 15-20 min → 10-15 min (-30%)

---

## 📝 Código de Exemplo - Paralelização

```python
async def scrape_single_site(key, query, site, overrides, page, logger):
    """Scrape um único site para um produto."""
    try:
        override_url = overrides.get(key, {}).get(site)
        url = override_url if override_url else search_url(site, query)
        
        # Timeout otimizado
        timeout = 20000 if site in ("Worten", "Darty") else 15000
        
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await dismiss_cookie_banner(page)
        
        # Espera otimizada
        await page.wait_for_timeout(2000)
        
        html = await page.content()
        
        # Extração de preço
        if PRICE_EXTRACTORS_AVAILABLE and should_use_specific_extractor(site, page.url):
            if site == "NOS":
                price = await extract_nos_online_price(page)
            elif site == "Vodafone":
                price = await extract_vodafone_online_price(page)
        else:
            prices = extract_prices_from_html(html)
            price = best_match(prices, query)
        
        return {
            "site": site,
            "price": price,
            "url": page.url,
            "success": price is not None
        }
    
    except Exception as e:
        return {
            "site": site,
            "error": str(e),
            "success": False
        }


async def scrape_product_parallel(key, query, sites, overrides, context, logger):
    """Scrape um produto em todos os sites em paralelo."""
    # Criar uma página por site (paralelização real)
    pages = []
    for _ in sites:
        page = await context.new_page()
        if STEALTH_AVAILABLE:
            await _stealth_async(page)
        pages.append(page)
    
    # Criar tasks
    tasks = []
    for i, site in enumerate(sites):
        task = scrape_single_site(key, query, site, overrides, pages[i], logger)
        tasks.append(task)
    
    # Executar em paralelo
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Fechar páginas
    for page in pages:
        await page.close()
    
    return results


# No loop principal:
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True, args=[...])
    context = await browser.new_context(...)
    
    for category, models in CATALOGUE.items():
        for model_name, model_info in models.items():
            for variant, query in model_info["variants"].items():
                key = f"{model_name} {variant}".strip()
                
                # Scrape todos os sites em paralelo
                results = await scrape_product_parallel(
                    key, query, SITES, overrides, context, logger
                )
                
                # Processar resultados
                for result in results:
                    if result["success"]:
                        # Guardar preço
                        pass
                
                # Delay entre produtos (não entre sites!)
                await asyncio.sleep(2.0)
```

---

## ⚠️ Considerações

### Recursos do GitHub Actions
- **CPU:** 2 cores (suficiente para 6 sites paralelos)
- **RAM:** 7GB (Chromium usa ~200MB por instância = 1.2GB total)
- **Timeout:** 6 horas (muito acima dos 15-30 min necessários)

### Anti-Bot
- Paralelização pode parecer mais "bot-like"
- **Solução:** Manter delays entre produtos (não entre sites)
- User-Agent e headers diferentes por página

### Cloudflare
- Paralelização não resolve Cloudflare
- **Solução:** URL overrides para Worten/Darty

---

## 🎯 Recomendação Final

**Implementar Fase 1 + Fase 2:**
1. Reduzir timeouts (40s → 20s)
2. Reduzir esperas (7s → 3s)
3. Paralelizar sites (6x speedup)

**Resultado esperado:**
- **Tempo atual:** ~2 horas
- **Tempo otimizado:** ~15-20 minutos
- **Redução:** 85% ✅

**Próximo passo:** Implementar otimizações em Sprint 6?
