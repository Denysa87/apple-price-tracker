# 📊 Estado Atual do Apple Price Tracker

**Data:** 17 Março 2026  
**Versão:** Sprint 6 Fase 1

---

## 🎯 Estado por Site

| Site | Status | Taxa Sucesso | Precisão | Tempo Médio | Problemas | Solução |
|------|--------|--------------|----------|-------------|-----------|---------|
| **MEO** | ✅ Funcional | ~100% | 100% | 15s | Nenhum | Sprint 4: Navegação por categoria |
| **NOS** | ✅ Funcional | ~90% | 100% | 15s | Preços DCN vs Online | Sprint 5: Extrator específico |
| **Vodafone** | ✅ Funcional | ~85% | 100% | 15s | Preços loyalty vs PVP | Sprint 5: Extrator específico |
| **Worten** | ⚠️ Parcial | ~30% | 99.6% | 20s | Cloudflare bloqueia 70% | URL overrides recomendado |
| **Darty** | ⚠️ Parcial | ~25% | 95% | 20s | Cloudflare bloqueia 75% | URL overrides recomendado |
| **Rádio Popular** | ⚠️ Parcial | ~40% | 98% | 25s | Timeouts frequentes | URL overrides recomendado |

### Legenda
- ✅ **Funcional:** >80% taxa de sucesso
- ⚠️ **Parcial:** 20-80% taxa de sucesso
- ❌ **Não funcional:** <20% taxa de sucesso

---

## 📈 Evolução da Performance

| Métrica | Inicial | Sprint 1-3 | Sprint 4-5 | Sprint 6 Fase 1 | Meta Final |
|---------|---------|------------|------------|-----------------|------------|
| **Tempo Total** | ~2h | ~2h | ~2h | ~40-50min | ~15-20min |
| **Taxa Sucesso Global** | ~0% | ~50% | ~65% | ~65% | ~80% |
| **Preços Válidos** | 0% | 100% | 100% | 100% | 100% |
| **Sites Funcionais** | 0/6 | 3/6 | 3/6 | 3/6 | 5/6 |
| **Precisão Média** | N/A | 95% | 99% | 99.5% | 99.5% |

---

## 🔧 Funcionalidades Implementadas

### ✅ Validação e Qualidade
- [x] Validação de preços por categoria (ranges esperados)
- [x] Detecção de preços de acessórios
- [x] Logging estruturado (arquivo + console)
- [x] Debug automático (screenshots + HTML)
- [x] Extratores específicos por site (NOS, Vodafone)

### ✅ Anti-Bot
- [x] Headers HTTP realistas (Sec-Fetch-*, DNT, sec-ch-ua)
- [x] Rotação de User-Agents (5 opções)
- [x] Cookies persistentes (7 dias)
- [x] Delays aleatórios (distribuição triangular)
- [x] Scroll humano (200-800px)
- [x] Retry com backoff exponencial (3x)
- [x] Stealth mode (playwright-stealth)

### ✅ Performance
- [x] Timeouts otimizados por site (15-25s)
- [x] Esperas extras reduzidas (2-3s)
- [x] Cloudflare wait otimizado (15s)
- [ ] Paralelização (asyncio.gather) - **Pendente**

### ✅ Navegação
- [x] Navegação por categoria (MEO)
- [x] Filtros melhorados (ignora links genéricos)
- [x] Navegação dupla (pesquisa → produto)
- [x] URL overrides (manual)

---

## 🚀 Otimizações Adicionais (Sem Custos)

### 1. **Paralelização (Sprint 6 Fase 2)** 🔴 CRÍTICO
**Impacto:** 40-50min → 15-20min (-65%)  
**Esforço:** 2-4 horas  
**Custo:** €0

```python
# Scrape 6 sites em paralelo em vez de sequencial
async def scrape_product_parallel(key, query, sites):
    tasks = [scrape_single_site(key, query, site) for site in sites]
    results = await asyncio.gather(*tasks)
    return results
```

**Benefícios:**
- 6x speedup (sites em paralelo)
- Tempo = max(site_times) em vez de sum(site_times)
- Redução de 2h → 15-20min total

---

### 2. **Cache de Resultados** 🟡 MÉDIO
**Impacto:** -10-20% requests  
**Esforço:** 1-2 horas  
**Custo:** €0

```python
# Só scrape se passou >6h desde última vez
def should_scrape(key, site, last_time):
    if not last_time:
        return True
    hours_since = (datetime.now() - last_time).total_seconds() / 3600
    return hours_since >= 6
```

**Benefícios:**
- Evita re-scraping de produtos que não mudaram
- Reduz carga nos sites (menos detecção)
- Mais rápido em execuções subsequentes

---

### 3. **Limitar Produtos no CI** 🟡 MÉDIO
**Impacto:** -50% requests  
**Esforço:** 30 min  
**Custo:** €0

```python
# Scrape apenas produtos principais no GitHub Actions
PRIORITY_PRODUCTS = [
    "iPhone 17 Pro Max 256GB",
    "iPhone 17 Pro 256GB",
    "iPhone 17 256GB",
    "AirPods Pro 3",
    "Apple Watch Ultra 3 49mm",
]

if os.getenv("GITHUB_ACTIONS"):
    # Filtrar apenas produtos prioritários
    filtered_catalogue = filter_priority_products(CATALOGUE)
```

**Benefícios:**
- Menos produtos = menos tempo
- Foco em produtos mais populares
- Ainda cobre gama completa

---

### 4. **Excluir Sites Problemáticos no CI** 🟡 MÉDIO
**Impacto:** -30% tempo  
**Esforço:** 15 min  
**Custo:** €0

```python
# Excluir Worten/Darty (Cloudflare) no CI
WORKING_SITES = ["MEO", "NOS", "Vodafone", "Rádio Popular"]

if os.getenv("GITHUB_ACTIONS"):
    SITES = WORKING_SITES  # Só sites que funcionam
```

**Benefícios:**
- Elimina 70% de falhas (Cloudflare)
- Mais rápido (sem esperar timeouts)
- Ainda cobre 4/6 sites

---

### 5. **URL Overrides Completos** 🟢 BAIXO
**Impacto:** -50% navegação  
**Esforço:** 2-3 horas (manual)  
**Custo:** €0

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/...",
    "Darty": "https://www.darty.com/...",
    "Rádio Popular": "https://www.radiopopular.pt/produto/..."
  }
}
```

**Benefícios:**
- Elimina navegação pesquisa → produto
- Bypassa Cloudflare (URLs diretos)
- 100% taxa de sucesso em sites com override

---

### 6. **Reduzir Produtos Totais** 🟢 BAIXO
**Impacto:** -30% requests  
**Esforço:** 15 min  
**Custo:** €0

```python
# Remover variantes menos populares
# Ex: iPhone 17 Pro Max 1TB (pouco vendido)
# Ex: Apple Watch SE 3 40mm (menos popular que 44mm)
```

**Benefícios:**
- Menos produtos = menos tempo
- Foco em variantes mais vendidas
- Ainda cobre modelos principais

---

### 7. **Scraping Incremental** 🟢 BAIXO
**Impacto:** -20% tempo  
**Esforço:** 1 hora  
**Custo:** €0

```python
# Scrape sites em ordem de prioridade
# Se MEO/NOS/Vodafone funcionam, skip Worten/Darty
priority_sites = ["MEO", "NOS", "Vodafone"]
fallback_sites = ["Worten", "Darty", "Rádio Popular"]

# Só scrape fallback se priority falhar
if success_rate(priority_sites) >= 0.8:
    skip(fallback_sites)
```

**Benefícios:**
- Menos requests se sites principais funcionam
- Mais rápido em média
- Ainda tem fallback

---

### 8. **Otimizar Seletores CSS** 🟢 BAIXO
**Impacto:** -1-2s por site  
**Esforço:** 2 horas  
**Custo:** €0

```python
# Usar seletores mais específicos
# ANTES: await page.wait_for_selector("[class*='product']", timeout=10000)
# DEPOIS: await page.wait_for_selector(".product-card", timeout=5000)
```

**Benefícios:**
- Seletores específicos = mais rápido
- Menos falsos positivos
- Menos espera

---

### 9. **Desativar Recursos Desnecessários** 🟢 BAIXO
**Impacto:** -10-15% tempo  
**Esforço:** 30 min  
**Custo:** €0

```python
# Bloquear imagens, fontes, CSS (só precisamos de HTML)
await context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", 
                    lambda route: route.abort())
```

**Benefícios:**
- Menos dados transferidos
- Mais rápido
- Menos memória

---

### 10. **Reutilizar Contexto do Browser** 🟢 BAIXO
**Impacto:** -5-10s total  
**Esforço:** 1 hora  
**Custo:** €0

```python
# ANTES: Criar novo browser para cada produto
# DEPOIS: Reutilizar mesmo browser/contexto
async with async_playwright() as p:
    browser = await p.chromium.launch()
    context = await browser.new_context()
    # Reutilizar para todos os produtos
```

**Benefícios:**
- Menos overhead de inicialização
- Cookies persistem entre requests
- Mais rápido

---

## 📊 Priorização de Otimizações

| Otimização | Impacto | Esforço | ROI | Prioridade |
|------------|---------|---------|-----|------------|
| **1. Paralelização** | 🔴 Muito Alto | Médio | 🔴 Muito Alto | **P0** |
| **2. Cache de Resultados** | 🟡 Médio | Baixo | 🟡 Alto | **P1** |
| **3. Limitar Produtos CI** | 🟡 Médio | Muito Baixo | 🟡 Alto | **P1** |
| **4. Excluir Sites CI** | 🟡 Médio | Muito Baixo | 🟡 Alto | **P1** |
| **5. URL Overrides** | 🟡 Médio | Médio | 🟢 Médio | **P2** |
| **6. Reduzir Produtos** | 🟢 Baixo | Muito Baixo | 🟢 Médio | **P2** |
| **7. Scraping Incremental** | 🟢 Baixo | Baixo | 🟢 Médio | **P2** |
| **8. Otimizar Seletores** | 🟢 Baixo | Médio | 🟢 Baixo | **P3** |
| **9. Desativar Recursos** | 🟢 Baixo | Muito Baixo | 🟢 Médio | **P2** |
| **10. Reutilizar Contexto** | 🟢 Baixo | Baixo | 🟢 Baixo | **P3** |

---

## 🎯 Roadmap Recomendado

### Fase 1: Quick Wins (1-2 horas) ✅ **CONCLUÍDO**
- [x] Reduzir timeouts (40s → 20s)
- [x] Reduzir esperas (7s → 3s)
- [x] Cloudflare wait (30s → 15s)
- **Resultado:** 2h → 40-50min (-55%)

### Fase 2: Paralelização (2-4 horas) ⏳ **PRÓXIMO**
- [ ] Implementar `asyncio.gather()`
- [ ] Refatorar loop principal
- **Resultado:** 40-50min → 15-20min (-65%)

### Fase 3: Otimizações Adicionais (2-3 horas)
- [ ] Cache de resultados
- [ ] Limitar produtos/sites no CI
- [ ] Desativar recursos desnecessários
- **Resultado:** 15-20min → 10-15min (-30%)

### Fase 4: Refinamento (opcional)
- [ ] URL overrides completos
- [ ] Scraping incremental
- [ ] Otimizar seletores
- **Resultado:** 10-15min → 8-12min (-20%)

---

## 💰 Comparação: Gratuito vs Pago

| Solução | Custo | Taxa Sucesso | Tempo | Manutenção |
|---------|-------|--------------|-------|------------|
| **Atual (Sprint 6 Fase 1)** | €0 | ~65% | 40-50min | Baixa |
| **Sprint 6 Fase 2 (Paralelo)** | €0 | ~65% | 15-20min | Baixa |
| **Sprint 6 Completo** | €0 | ~80% | 10-15min | Média |
| **ScraperAPI** | €49/mês | ~95% | 5-10min | Muito Baixa |
| **Bright Data** | €500/mês | ~99% | 3-5min | Muito Baixa |
| **Oxylabs** | €300/mês | ~98% | 3-5min | Muito Baixa |

**Recomendação:** Implementar Sprint 6 Fase 2 (paralelização) antes de considerar soluções pagas. Com €0 de custo, consegues 80% da performance de soluções pagas.

---

## 🎯 Meta Final (Sem Custos)

| Métrica | Atual | Meta |
|---------|-------|------|
| **Tempo Total** | 40-50min | 10-15min |
| **Taxa Sucesso** | ~65% | ~80% |
| **Sites Funcionais** | 3/6 | 5/6 |
| **Custo Mensal** | €0 | €0 |
| **Manutenção** | Baixa | Média |

**Próximo Passo:** Implementar Paralelização (Sprint 6 Fase 2)
