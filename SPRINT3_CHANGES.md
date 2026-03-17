# 🚀 Sprint 3 - Melhorias Críticas

## 📋 Contexto

Após implementar Sprint 1 (validação, logging) e Sprint 2 (anti-bot), os testes revelaram problemas críticos:

**Problemas identificados nos logs:**
- ❌ **Worten**: Cloudflare bloqueando (timeout 15s insuficiente)
- ❌ **Rádio Popular**: Timeout 25000ms excedido (site muito lento)
- ❌ **MEO**: Nenhum preço encontrado (seletores desatualizados)
- ⚠️ **Darty**: Override falhou (URL inválido)

**Taxa de sucesso observada**: ~0-20% (inaceitável)

## 🎯 Objetivos do Sprint 3

1. **Aumentar timeouts** para sites problemáticos (Cloudflare, sites lentos)
2. **Melhorar seletores de extração** de preços (MEO, NOS, Vodafone)
3. **Adicionar padrões genéricos** para capturar mais preços
4. **Melhorar detecção Cloudflare** com wait mais longo

**Meta**: Taxa de sucesso >60%

---

## ✅ Melhorias Implementadas

### 1. Timeouts Aumentados por Site

**Problema**: Timeouts genéricos (25s) insuficientes para Cloudflare e sites lentos.

**Solução**: Timeouts personalizados por site baseados em observações reais.

```python
# scraper.py - linhas 733-741
timeout_map = {
    "Worten": 40000,        # Cloudflare → 40s
    "Darty": 40000,         # Cloudflare → 40s
    "Rádio Popular": 35000, # Site lento → 35s
    "MEO": 30000,           # JS-heavy → 30s
    "Vodafone": 30000,      # JS-heavy → 30s
    "NOS": 30000,           # JS-heavy → 30s
}
page_timeout = timeout_map.get(site, 25000)
```

**Impacto**:
- Worten/Darty: 25s → 40s (+60%)
- Rádio Popular: 25s → 35s (+40%)
- MEO/Vodafone/NOS: 25s → 30s (+20%)

---

### 2. Espera Extra Aumentada

**Problema**: Sites JS-heavy precisam de mais tempo para renderizar conteúdo.

**Solução**: Espera extra personalizada por site.

```python
# scraper.py - linha 749
extra_wait = 7000 if site in ("Rádio Popular", "MEO") else 5000 if site in ("Vodafone", "NOS") else 3000
```

**Impacto**:
- Rádio Popular/MEO: 5s → 7s (+40%)
- Vodafone/NOS: 3s → 5s (+67%)
- Worten/Darty: mantém 3s

---

### 3. Cloudflare Wait Aumentado

**Problema**: Cloudflare challenge demora >15s a resolver.

**Solução**: Wait de 30s com feedback visual.

```python
# scraper.py - linhas 764-776
if is_cloudflare_blocked(html):
    stats["cloudflare_blocks"] += 1
    print(f"⏳ Cloudflare detectado, aguardando 30s...", end=" ", flush=True)
    await page.wait_for_timeout(30000)  # 15s → 30s
    html = await page.content()
    if is_cloudflare_blocked(html):
        print(f"⛔  Cloudflare (bloqueado)")
        stats["failed"] += 1
        continue
    else:
        print(f"✅ Cloudflare resolvido", end=" ")
```

**Impacto**:
- Wait: 15s → 30s (+100%)
- Feedback visual melhorado
- Retry automático após wait

---

### 4. Seletores de Preço Melhorados

**Problema**: MEO, NOS e Vodafone com estruturas HTML diferentes.

**Solução**: Múltiplos padrões por site.

#### MEO (linhas 370-380)
```python
meo_patterns = [
    r'class=["\']price no-translate["\'][^>]*>\s*<span>€?([\d.,]+)\s*€?</span>',
    r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>€?\s*([\d.,]+)\s*€?</span>',
    r'data-price=["\'](\d+\.?\d*)["\']',
    r'"price"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
    r'<div[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?',
]
```

#### NOS (linhas 384-391)
```python
nos_patterns = [
    r'<p[^>]*class=["\'][^"\']*full-price[^"\']*["\'][^>]*>\s*([\d.,]+)\s*</p>',
    r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?</span>',
    r'data-price=["\'](\d+\.?\d*)["\']',
]
```

#### Vodafone (linhas 394-402)
```python
voda_patterns = [
    r'<span[^>]*basket-toaster__price--value[^>]*>\s*€?([\d.,]+)\s*€?\s*</span>',
    r'<span[^>]*class=["\'][^"\']*price[^"\']*["\'][^>]*>\s*€?\s*([\d.,]+)\s*€?</span>',
    r'data-price=["\'](\d+\.?\d*)["\']',
    r'"finalPrice"\s*:\s*"?(\d{2,5}(?:[.,]\d{1,3})*)"?',
]
```

**Impacto**:
- MEO: 1 padrão → 5 padrões (+400%)
- NOS: 1 padrão → 3 padrões (+200%)
- Vodafone: 1 padrão → 4 padrões (+300%)

---

### 5. Padrões Genéricos Adicionais

**Problema**: Alguns preços não capturados por padrões específicos.

**Solução**: Padrões genéricos para atributos data-* e classes comuns.

```python
# scraper.py - linhas 404-418
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
```

**Impacto**:
- +4 atributos data-* monitorizados
- +2 padrões de classes genéricas
- Cobertura aumentada para sites desconhecidos

---

### 6. Documentação Atualizada

**Ficheiros atualizados**:
- [`scraper.py`](scraper.py:1-30) - Cabeçalho com Sprint 3
- [`SPRINT3_CHANGES.md`](SPRINT3_CHANGES.md) - Este documento
- [`README.md`](README.md) - Secção Sprint 3 (pendente)

---

## 📊 Resultados Esperados

### Antes do Sprint 3
```
Taxa de sucesso:      ~0-20%
Cloudflare blocks:    Alta (>50%)
Timeouts:             Frequentes
Preços encontrados:   Baixo
```

### Depois do Sprint 3
```
Taxa de sucesso:      >60%
Cloudflare blocks:    Média (~20%)
Timeouts:             Raros (<10%)
Preços encontrados:   Alto
```

### Melhorias por Site

| Site | Antes | Depois | Melhoria |
|------|-------|--------|----------|
| Worten | 0% (Cloudflare) | >70% | ✅ +70pp |
| Rádio Popular | 0% (Timeout) | >60% | ✅ +60pp |
| MEO | 0% (Sem preços) | >70% | ✅ +70pp |
| Vodafone | ~30% | >70% | ✅ +40pp |
| NOS | ~30% | >70% | ✅ +40pp |
| Darty | 0% (Cloudflare) | >60% | ✅ +60pp |

---

## 🧪 Como Testar

### Teste Individual (Rápido)
```bash
cd "/Users/denysa_/Documents/enchanté/conversations/9B1EF1BB-F107-4D91-974B-D026CB3CD0DB"

# Testar MEO (problema identificado)
python3 tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site MEO

# Testar Worten (Cloudflare)
python3 tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site Worten

# Testar Rádio Popular (timeout)
python3 tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site "Rádio Popular"
```

### Teste Completo (15-20 minutos)
```bash
python3 scraper.py
```

### Verificar Logs
```bash
# Ver log do dia
cat logs/scraper_$(date +%Y%m%d).log

# Ver estatísticas
tail -20 logs/scraper_$(date +%Y%m%d).log

# Ver debug info (se houver erros)
ls -la debug/
```

---

## 📝 Notas Técnicas

### Timeouts Explicados

**Por que 40s para Cloudflare?**
- Cloudflare challenge: ~5-10s
- Render JavaScript: ~5-10s
- Network latency: ~2-5s
- Buffer de segurança: ~15-20s
- **Total**: ~40s

**Por que 35s para Rádio Popular?**
- Site muito lento (servidor)
- Múltiplos requests AJAX
- Imagens pesadas
- **Total**: ~35s

### Padrões de Extração

**Ordem de prioridade**:
1. JSON-LD schema.org (mais confiável)
2. __NEXT_DATA__ (Next.js apps)
3. itemprop="price" (microdata)
4. JSON embebido (SPAs)
5. Padrões inline (HTML)
6. Padrões específicos por site
7. Padrões genéricos (fallback)

**Por que múltiplos padrões?**
- Sites mudam estrutura frequentemente
- A/B testing altera HTML
- Diferentes páginas (pesquisa vs produto)
- Fallback aumenta robustez

---

## 🔄 Próximos Passos (Sprint 4 - Opcional)

Se taxa de sucesso < 60% após Sprint 3:

### 1. Proxies Rotativos
- Evitar bloqueios por IP
- Distribuir requests
- Custo: ~$10-20/mês

### 2. Melhorar find_product_url()
- Scoring mais inteligente
- Considerar posição na página
- Penalizar "usado", "recondicionado"

### 3. Captcha Solving
- 2captcha ou similar
- Apenas se Cloudflare persistir
- Custo: ~$3/1000 captchas

### 4. Monitorização
- Dashboard de health check
- Alertas automáticos
- Métricas de performance

---

## 🐛 Problemas Conhecidos

### 1. MEO - Preço Incorreto
**Sintoma**: Encontra 909.99€ em vez de 1499.99€  
**Causa**: Página de pesquisa com vários produtos  
**Solução**: Melhorar `find_product_url()` para navegar ao produto correto  
**Status**: 🔄 Em investigação

### 2. Worten - Cloudflare Intermitente
**Sintoma**: Às vezes bloqueia, às vezes passa  
**Causa**: Cloudflare detecta padrões de bot  
**Solução**: Implementado wait de 30s + anti-bot Sprint 2  
**Status**: ✅ Melhorado (mas não 100%)

### 3. Darty - Override Inválido
**Sintoma**: Override falha 1/3 vezes  
**Causa**: URL mudou ou produto descontinuado  
**Solução**: Sistema automático remove após 3 falhas  
**Status**: ✅ Resolvido (auto-cleanup)

---

## 📚 Referências

- [Playwright Timeouts](https://playwright.dev/docs/api/class-page#page-goto)
- [Cloudflare Challenge](https://developers.cloudflare.com/fundamentals/get-started/concepts/how-cloudflare-works/)
- [Regex Price Patterns](https://regex101.com/)
- [BeautifulSoup Selectors](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

---

## ✅ Checklist de Implementação

- [x] Aumentar timeouts por site (40s/35s/30s)
- [x] Aumentar espera extra (7s/5s/3s)
- [x] Cloudflare wait 30s com feedback
- [x] Seletores MEO (5 padrões)
- [x] Seletores NOS (3 padrões)
- [x] Seletores Vodafone (4 padrões)
- [x] Padrões genéricos data-*
- [x] Padrões genéricos classes
- [x] Atualizar cabeçalho scraper.py
- [x] Criar SPRINT3_CHANGES.md
- [ ] Atualizar README.md
- [ ] Testar em produção
- [ ] Commit e push

---

**Data**: 2026-03-17  
**Autor**: Roo (AI Assistant)  
**Versão**: 1.0
