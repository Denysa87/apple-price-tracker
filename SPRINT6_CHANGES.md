# Sprint 6: Otimizações de Performance

**Data:** 17 Março 2026  
**Objetivo:** Reduzir tempo de execução de ~2h para 15-20min

---

## 🎯 Problema Identificado

### Tempo de Execução Excessivo
- **Tempo atual:** ~2 horas (120 minutos)
- **Causa:** Execução sequencial + timeouts excessivos
- **Impacto:** GitHub Actions timeout, custos elevados

### Cálculo Detalhado
```
3 categorias × 10 produtos × 6 sites = 180 requests
Tempo por request: 30s (timeout) + 5s (espera) + 2.5s (delay) = 37.5s
Total: 180 × 37.5s = 6,750s = 112 minutos (1.87h)
```

### Gargalos Identificados
1. 🔴 **Execução sequencial** - 1 site de cada vez (90 min perdidos)
2. 🔴 **Timeouts excessivos** - 30-40s quando 15-20s é suficiente (30 min perdidos)
3. 🟡 **Esperas extras** - 5-7s redundantes (15 min perdidos)
4. 🟡 **Cloudflare wait** - 30s quando 15s é suficiente (5 min perdidos)

---

## ✅ Fase 1: Quick Wins (Implementado)

### 1. Timeouts Otimizados (-50%)

**Antes (Sprint 3):**
```python
timeout_map = {
    "Worten": 40000,        # 40s
    "Darty": 40000,         # 40s
    "Rádio Popular": 35000, # 35s
    "MEO": 30000,           # 30s
    "Vodafone": 30000,      # 30s
    "NOS": 30000,           # 30s
}
```

**Depois (Sprint 6):**
```python
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
- Se falhar em 15-20s, provavelmente é Cloudflare (não resolve com mais tempo)
- Reduz tempo médio por request de 30s → 17.5s

---

### 2. Esperas Extras Otimizadas (-60%)

**Antes (Sprint 3):**
```python
extra_wait = 7000 if site in ("Rádio Popular", "MEO") else 5000
```

**Depois (Sprint 6):**
```python
extra_wait = 3000 if site in ("Rádio Popular", "MEO") else 2000 if site in ("Vodafone", "NOS") else 1500
```

**Justificação:**
- `wait_for_selector()` já aguarda elementos carregarem
- Espera extra de 5-7s é redundante
- 2-3s é suficiente para JavaScript renderizar

---

### 3. Cloudflare Wait Otimizado (-50%)

**Antes (Sprint 3):**
```python
await page.wait_for_timeout(30000)  # 30s
```

**Depois (Sprint 6):**
```python
await page.wait_for_timeout(15000)  # 15s
```

**Justificação:**
- Cloudflare resolve em 5-10s ou nunca resolve
- 30s é excessivo
- Se não resolver em 15s, usar URL override

---

## 📊 Resultados Fase 1

### Impacto por Request
```
ANTES:
Timeout: 30s + Espera: 5s + Delay: 2.5s = 37.5s por request

DEPOIS:
Timeout: 17.5s + Espera: 2.5s + Delay: 2.5s = 22.5s por request

Redução: 37.5s → 22.5s (-40% por request)
```

### Impacto Total
```
ANTES: 180 requests × 37.5s = 6,750s = 112 min
DEPOIS: 180 requests × 22.5s = 4,050s = 67 min

Redução: 112 min → 67 min (-40% ou -45 min)
```

**Nota:** Estimativa conservadora. Na prática, pode ser ainda mais rápido devido a:
- Menos timeouts (sites carregam mais rápido)
- Menos retries (falhas mais rápidas)
- Cloudflare resolve mais rápido

---

## ⏳ Fase 2: Paralelização (Próximo Sprint)

### Conceito
Scrape 6 sites em **paralelo** em vez de sequencial usando `asyncio.gather()`.

### Implementação

#### 1. Função para Scrape de Site Individual
```python
async def scrape_single_site(
    key: str,
    query: str,
    site: str,
    overrides: dict,
    context,
    logger,
    memory: URLMemory,
    stats: dict,
    debug_dir: Path,
    ts: str
) -> dict:
    """
    Scrape um único site para um produto.
    Retorna resultado com preço ou erro.
    """
    page = await context.new_page()
    if STEALTH_AVAILABLE:
        await _stealth_async(page)
    
    try:
        override_url = overrides.get(key, {}).get(site)
        url = override_url if override_url else search_url(site, query)
        is_override = bool(override_url)
        
        # Timeout otimizado
        timeout_map = {
            "Worten": 20000, "Darty": 20000, "Rádio Popular": 25000,
            "MEO": 15000, "Vodafone": 15000, "NOS": 15000,
        }
        page_timeout = timeout_map.get(site, 15000)
        
        # Navegação
        wait_mode = "networkidle" if site in ("Rádio Popular", "MEO", "Vodafone", "NOS") else "domcontentloaded"
        await page.goto(url, wait_until=wait_mode, timeout=page_timeout)
        await dismiss_cookie_banner(page)
        
        # Espera otimizada
        extra_wait = 3000 if site in ("Rádio Popular", "MEO") else 2000
        await page.wait_for_timeout(extra_wait)
        
        html = await page.content()
        
        # Cloudflare check
        if is_cloudflare_blocked(html):
            await page.wait_for_timeout(15000)
            html = await page.content()
            if is_cloudflare_blocked(html):
                return {"site": site, "success": False, "error": "Cloudflare"}
        
        # Navegação para produto (se não override)
        if not is_override:
            site_bases = {
                "Worten": "https://www.worten.pt",
                "Rádio Popular": "https://www.radiopopular.pt",
                "Darty": "https://www.darty.com",
                "MEO": "https://loja.meo.pt",
                "Vodafone": "https://www.vodafone.pt",
                "NOS": "https://www.nos.pt",
            }
            product_url = find_product_url(html, query, site, site_bases.get(site, ""))
            if product_url and product_url != page.url:
                try:
                    await page.goto(product_url, wait_until=wait_mode, timeout=20000)
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                except Exception:
                    pass
        
        # Extração de preço
        price = None
        if PRICE_EXTRACTORS_AVAILABLE and should_use_specific_extractor(site, page.url):
            if site == "NOS":
                price = await extract_nos_online_price(page)
            elif site == "Vodafone":
                price = await extract_vodafone_online_price(page)
        
        if not price:
            prices = extract_prices_from_html(html)
            price = best_match(prices, query)
        
        if price:
            # Validação
            if UTILS_AVAILABLE:
                is_valid, reason = validate_price(price, key)
                if is_valid and is_likely_accessory_price(price, key):
                    is_valid = False
                    reason = f"Preço {price:.2f}€ muito baixo - provavelmente acessório"
                
                if not is_valid:
                    return {"site": site, "success": False, "error": f"Validação: {reason}"}
            
            return {
                "site": site,
                "success": True,
                "price": price,
                "url": page.url,
                "is_override": is_override
            }
        else:
            return {"site": site, "success": False, "error": "Nenhum preço encontrado"}
    
    except Exception as e:
        return {"site": site, "success": False, "error": str(e)[:100]}
    
    finally:
        await page.close()
```

#### 2. Função para Scrape Paralelo
```python
async def scrape_product_parallel(
    key: str,
    query: str,
    sites: list,
    overrides: dict,
    context,
    logger,
    memory: URLMemory,
    stats: dict,
    debug_dir: Path,
    ts: str
) -> list:
    """
    Scrape um produto em todos os sites em paralelo.
    Retorna lista de resultados.
    """
    # Criar tasks para todos os sites
    tasks = []
    for site in sites:
        task = scrape_single_site(
            key, query, site, overrides, context, logger,
            memory, stats, debug_dir, ts
        )
        tasks.append(task)
    
    # Executar em paralelo
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

#### 3. Loop Principal Modificado
```python
for category, models in CATALOGUE.items():
    results.setdefault(category, {})
    print(f"\n📦  {category}")
    
    for model_name, model_info in models.items():
        for variant, query in model_info["variants"].items():
            key = f"{model_name} {variant}".strip()
            results[category].setdefault(key, {})
            print(f"  🔍  {key}")
            
            # 🆕 Scrape todos os sites em paralelo
            site_results = await scrape_product_parallel(
                key, query, SITES, overrides, context, logger,
                memory, stats, debug_dir, ts
            )
            
            # Processar resultados
            for result in site_results:
                if isinstance(result, Exception):
                    print(f"      ❌  {result}")
                    stats["failed"] += 1
                    continue
                
                site = result["site"]
                flag = "🔗" if result.get("is_override") else "📡"
                
                if result["success"]:
                    price = result["price"]
                    url = result["url"]
                    
                    results[category][key].setdefault(site, [])
                    results[category][key][site].append({
                        "date": ts,
                        "price": price,
                        "url": url,
                        "url_source": "override" if result.get("is_override") else "auto",
                    })
                    
                    print(f"      {flag}  {site}... ✅  {price:.2f} €")
                    stats["successful"] += 1
                    
                    if not result.get("is_override"):
                        memory.record_success(key, site, url, price)
                else:
                    error = result.get("error", "Desconhecido")
                    print(f"      {flag}  {site}... ❌  {error}")
                    stats["failed"] += 1
            
            # Delay entre produtos (não entre sites!)
            delay = get_random_delay(1.5, 3.5) if ANTI_BOT_AVAILABLE else 2.0
            await asyncio.sleep(delay)
```

---

### Impacto Esperado Fase 2

```
ANTES (Fase 1): 180 requests × 22.5s = 4,050s = 67 min (sequencial)
DEPOIS (Fase 2): 30 produtos × max(6 sites × 22.5s) = 30 × 22.5s = 675s = 11 min (paralelo)

Redução: 67 min → 11 min (-84% ou -56 min)
```

**Nota:** Tempo = max(site_times) porque sites executam em paralelo, não sum(site_times).

---

## 📈 Roadmap Completo

| Fase | Otimizações | Tempo Estimado | Status |
|------|-------------|----------------|--------|
| **Inicial** | Nenhuma | ~120 min | ❌ |
| **Fase 1** | Timeouts + Esperas | ~67 min | ✅ **Implementado** |
| **Fase 2** | Paralelização | ~11 min | ⏳ Próximo |
| **Fase 3** | Cache + Limites | ~8 min | Futuro |

---

## 🔧 Arquivos Modificados

### Sprint 6 Fase 1
- ✅ [`scraper.py`](scraper.py) (linhas 778-818)
  - Timeouts otimizados (20s Worten/Darty, 25s Rádio Popular, 15s outros)
  - Esperas extras otimizadas (3s → 2s → 1.5s)
  - Cloudflare wait otimizado (30s → 15s)
  - Cabeçalho atualizado com Sprint 6

---

## 📊 Comparação de Performance

| Métrica | Inicial | Sprint 1-5 | Sprint 6 Fase 1 | Sprint 6 Fase 2 (Meta) |
|---------|---------|------------|-----------------|------------------------|
| **Tempo Total** | ~120 min | ~120 min | ~67 min | ~11 min |
| **Tempo/Request** | 40s | 37.5s | 22.5s | 22.5s (paralelo) |
| **Execução** | Sequencial | Sequencial | Sequencial | **Paralelo** |
| **Redução vs Inicial** | 0% | 0% | **-44%** | **-91%** |

---

## 🎓 Lições Aprendidas

### 1. Timeouts Conservadores São Caros
- Timeouts de 30-40s "por segurança" custam 45 minutos
- Sites modernos carregam em 5-10s
- Melhor falhar rápido e usar URL override

### 2. Esperas Redundantes Acumulam
- Espera extra após timeout é redundante
- `wait_for_selector()` já aguarda elementos
- 5-7s × 180 requests = 15 minutos perdidos

### 3. Paralelização É o Maior Ganho
- Execução sequencial: sum(times) = 67 min
- Execução paralela: max(times) = 11 min
- **6x speedup** com mesma infraestrutura

### 4. Cloudflare Não Resolve com Mais Tempo
- Se não resolve em 15s, não resolve em 30s
- Melhor usar URL overrides
- Economiza 15s × bloqueios = tempo significativo

---

## 🚀 Próximos Passos

### Implementar Fase 2 (Paralelização)
1. Refatorar `scrape_single_site()` isolada
2. Criar `scrape_product_parallel()` com `asyncio.gather()`
3. Modificar loop principal
4. Testar localmente
5. Testar no GitHub Actions

### Otimizações Adicionais (Fase 3)
- Cache de resultados (<6h)
- Limitar produtos no CI
- Desativar recursos (imagens/CSS)
- Excluir sites problemáticos no CI

---

## 📝 Notas Técnicas

### Considerações de Paralelização

**Recursos GitHub Actions:**
- CPU: 2 cores (suficiente para 6 sites paralelos)
- RAM: 7GB (Chromium ~200MB × 6 = 1.2GB)
- Timeout: 6 horas (muito acima dos 11 min necessários)

**Anti-Bot:**
- Paralelização pode parecer mais "bot-like"
- **Solução:** Manter delays entre produtos (não entre sites)
- User-Agent e headers diferentes por página

**Cloudflare:**
- Paralelização não resolve Cloudflare
- **Solução:** URL overrides para Worten/Darty

---

**Status:** ✅ Fase 1 Concluída (-44% tempo)  
**Próximo:** Fase 2 - Paralelização (-91% tempo total)
