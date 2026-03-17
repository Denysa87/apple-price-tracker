# 📝 Guia: Como Adicionar URL Overrides

## 🎯 Objetivo

URL overrides permitem especificar URLs diretos dos produtos, evitando:
- ❌ Cloudflare challenges
- ❌ Timeouts em pesquisas
- ❌ Problemas de navegação automática
- ✅ Garante 100% taxa de sucesso

## 📋 Passo a Passo

### 1. Encontrar URL do Produto

Navegue manualmente no site e copie o URL da página do produto:

**Exemplo - Worten (iPhone 17 Pro Max 256GB):**
1. Ir a https://www.worten.pt
2. Pesquisar "iPhone 17 Pro Max 256GB"
3. Clicar no produto desejado
4. Copiar URL da barra de endereço
   - Exemplo: `https://www.worten.pt/produtos/apple-iphone-17-pro-max-256gb-titanio-natural-8888888888888`

### 2. Adicionar ao url_overrides.json

Abrir [`url_overrides.json`](url_overrides.json) e adicionar:

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/apple-iphone-17-pro-max-256gb-titanio-natural-8888888888888"
  }
}
```

**Formato:**
```json
{
  "Nome Produto Variante": {
    "Nome Site": "URL completo"
  }
}
```

### 3. Testar Override

```bash
cd "/Users/denysa_/Documents/enchanté/conversations/9B1EF1BB-F107-4D91-974B-D026CB3CD0DB"

# Testar produto específico
python3 tests/test_single_product.py "iPhone 17 Pro Max 256GB" --site Worten

# Deve mostrar: "🔗 Worten [override]..."
```

### 4. Adicionar Mais Sites

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/...",
    "MEO": "https://loja.meo.pt/telemoveis/iphone-17-pro-max-256gb",
    "Rádio Popular": "https://www.radiopopular.pt/produto/iphone-17-pro-max-256gb",
    "Vodafone": "https://www.vodafone.pt/loja/telemoveis/iphone-17-pro-max-256gb.html",
    "NOS": "https://www.nos.pt/particulares/equipamentos/telemovel/iphone-17-pro-max-256gb",
    "Darty": "https://www.darty.com/nav/achat/telephonie/telephone_mobile/iphone-17-pro-max-256gb.html"
  }
}
```

## 📚 Exemplos Completos

### Exemplo 1: iPhone com Múltiplas Variantes

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": "https://www.worten.pt/produtos/apple-iphone-17-pro-max-256gb-8888888888888",
    "MEO": "https://loja.meo.pt/telemoveis/iphone-17-pro-max-256gb"
  },
  "iPhone 17 Pro Max 512GB": {
    "Worten": "https://www.worten.pt/produtos/apple-iphone-17-pro-max-512gb-8888888888889",
    "MEO": "https://loja.meo.pt/telemoveis/iphone-17-pro-max-512gb"
  },
  "iPhone 17 Pro Max 1TB": {
    "Worten": "https://www.worten.pt/produtos/apple-iphone-17-pro-max-1tb-8888888888890",
    "MEO": "https://loja.meo.pt/telemoveis/iphone-17-pro-max-1tb"
  }
}
```

### Exemplo 2: AirPods

```json
{
  "AirPods 4": {
    "Worten": "https://www.worten.pt/produtos/apple-airpods-4-7777777777777",
    "Rádio Popular": "https://www.radiopopular.pt/produto/airpods-4"
  },
  "AirPods Pro 3": {
    "Worten": "https://www.worten.pt/produtos/apple-airpods-pro-3-7777777777778",
    "MEO": "https://loja.meo.pt/acessorios/airpods-pro-3"
  }
}
```

### Exemplo 3: Apple Watch

```json
{
  "Apple Watch SE 3 40mm": {
    "Worten": "https://www.worten.pt/produtos/apple-watch-se-3-40mm-6666666666666",
    "NOS": "https://www.nos.pt/particulares/equipamentos/smartwatch/apple-watch-se-3-40mm"
  }
}
```

## ⚠️ Notas Importantes

### 1. Nome do Produto Deve Ser Exato

O nome no override deve corresponder **exatamente** ao nome no catálogo:

```python
# scraper.py - CATALOGUE
"iPhone 17 Pro Max": {"variants": {
    "256GB": "Apple iPhone 17 Pro Max 256GB",  # ← Nome completo
    "512GB": "Apple iPhone 17 Pro Max 512GB",
    "1TB":   "Apple iPhone 17 Pro Max 1TB",
}}
```

**No url_overrides.json:**
```json
{
  "iPhone 17 Pro Max 256GB": { ... }  // ✅ Correto
  "iPhone 17 Pro Max 256":   { ... }  // ❌ Errado (falta "GB")
  "iphone 17 pro max 256gb": { ... }  // ❌ Errado (case-sensitive)
}
```

### 2. URLs Podem Mudar

Sites podem alterar URLs dos produtos. Se override falhar 3x consecutivas, é **automaticamente removido**.

**Verificar logs:**
```bash
cat logs/scraper_$(date +%Y%m%d).log | grep "override falhou"
```

### 3. Comentários São Ignorados

Linhas começando com `_` são ignoradas pelo scraper:

```json
{
  "_comment": "Isto é um comentário",
  "_instructions": "Adicione URLs aqui",
  "iPhone 17 Pro Max 256GB": {
    "_note": "URL atualizado em 2026-03-17",
    "Worten": "https://..."
  }
}
```

## 🔍 Como Verificar se Override Está a Funcionar

### 1. Logs do Scraper

```bash
python3 scraper.py

# Output esperado:
# 🔗 Worten [override]... ✅ 1499.99 €
#     ↑ Indica que usou override
```

### 2. Ficheiro url_suggestions.json

Quando override funciona, é registado em [`url_suggestions.json`](url_suggestions.json):

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": {
      "url": "https://www.worten.pt/produtos/...",
      "last_price": 1499.99,
      "last_seen": "2026-03-17",
      "times_worked": 5
    }
  }
}
```

### 3. Ficheiro url_override_failures.json

Se override falhar, é registado em [`url_override_failures.json`](url_override_failures.json):

```json
{
  "iPhone 17 Pro Max 256GB": {
    "Worten": 2  // Falhou 2x (será removido na 3ª falha)
  }
}
```

## 🚀 Workflow Recomendado

### Para Produtos Novos

1. **Tentar scraping automático primeiro:**
   ```bash
   python3 tests/test_single_product.py "iPhone 18 Pro Max 256GB" --site Worten
   ```

2. **Se falhar (Cloudflare/timeout), adicionar override:**
   - Navegar manualmente no site
   - Copiar URL do produto
   - Adicionar a `url_overrides.json`
   - Testar novamente

3. **Repetir para outros sites problemáticos**

### Para Produtos Existentes

1. **Verificar logs de falhas:**
   ```bash
   cat logs/scraper_$(date +%Y%m%d).log | grep "FAILED"
   ```

2. **Adicionar overrides para sites que falham consistentemente**

3. **Remover overrides quando scraping automático voltar a funcionar**

## 📊 Priorização

**Alta prioridade (adicionar overrides):**
- ✅ Worten (Cloudflare frequente)
- ✅ Darty (Cloudflare + site FR)
- ✅ Rádio Popular (timeouts frequentes)

**Média prioridade:**
- ⚠️ MEO (às vezes funciona)
- ⚠️ Vodafone (às vezes funciona)

**Baixa prioridade:**
- ℹ️ NOS (geralmente funciona)

## 🛠️ Troubleshooting

### Problema: Override não está a ser usado

**Verificar:**
1. Nome do produto está exato? (case-sensitive)
2. JSON está válido? (sem vírgulas extra, aspas corretas)
3. URL está completo? (com https://)

**Testar JSON:**
```bash
python3 -m json.tool url_overrides.json
# Se houver erro, mostra linha com problema
```

### Problema: Override funciona mas preço está errado

**Possíveis causas:**
1. URL aponta para variante errada (ex: 512GB em vez de 256GB)
2. URL aponta para produto recondicionado/usado
3. Site mudou estrutura HTML (seletores não funcionam)

**Solução:**
1. Verificar URL manualmente no browser
2. Verificar debug info em `debug/`
3. Atualizar URL se necessário

### Problema: Override foi removido automaticamente

**Causa:** Falhou 3x consecutivas

**Solução:**
1. Verificar se URL ainda é válido
2. Verificar se produto ainda existe no site
3. Atualizar URL e adicionar novamente

## 📝 Template para Copiar

```json
{
  "NOME_PRODUTO_VARIANTE": {
    "Worten": "https://www.worten.pt/produtos/...",
    "Rádio Popular": "https://www.radiopopular.pt/produto/...",
    "Darty": "https://www.darty.com/nav/achat/...",
    "MEO": "https://loja.meo.pt/telemoveis/...",
    "Vodafone": "https://www.vodafone.pt/loja/telemoveis/...",
    "NOS": "https://www.nos.pt/particulares/equipamentos/..."
  }
}
```

## 🎯 Objetivo Final

**Meta:** Ter overrides para produtos que falham consistentemente, garantindo:
- ✅ Taxa de sucesso 100% para produtos com override
- ✅ Scraping automático para produtos que funcionam
- ✅ Manutenção mínima (overrides só quando necessário)

---

**Última atualização:** 2026-03-17  
**Versão:** 1.0
