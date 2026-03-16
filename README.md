# 🍎 Apple Price Tracker

Monitoriza automaticamente os preços de **AirPods, iPhone e Apple Watch** nos principais
retalhistas portugueses, 4× por dia, e publica o dashboard no **GitHub Pages**.

| Retalhista | País |
|---|---|
| Worten | 🇵🇹 |
| Rádio Popular | 🇵🇹 |
| Darty | 🇫🇷/🇵🇹 |
| MEO | 🇵🇹 |
| Vodafone | 🇵🇹 |
| NOS | 🇵🇹 |

## 📊 Dashboard

> **[Ver dashboard ao vivo →](https://SEU_USERNAME.github.io/SEU_REPO/dashboard.html)**

## 🚀 Setup (5 minutos)

### 1. Criar repositório no GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/SEU_USERNAME/apple-price-tracker.git
git push -u origin main
```

### 2. Activar GitHub Pages

1. Vai a **Settings → Pages**
2. Em *Source*, selecciona **GitHub Actions**
3. Guarda

### 3. Activar permissões do workflow

1. Vai a **Settings → Actions → General**
2. Em *Workflow permissions*, selecciona **Read and write permissions**
3. Guarda

### 4. Primeiro run manual

1. Vai a **Actions → 🍎 Apple Price Tracker**
2. Clica **Run workflow**
3. Aguarda ~5 minutos

O dashboard fica disponível em:
`https://SEU_USERNAME.github.io/SEU_REPO/dashboard.html`

## 🕐 Agendamento

O scraper corre automaticamente às **07:00, 12:00, 18:00 e 23:00 UTC** todos os dias.
Podes alterar o horário no ficheiro `.github/workflows/scraper.yml`.

## 🗂 Estrutura

```
├── scraper.py          # Recolhe preços com Playwright (Chromium headless)
├── build_dashboard.py  # Gera dashboard.html com dados embutidos
├── prices.json         # Histórico de preços (actualizado automaticamente)
├── dashboard.html      # Dashboard gerado (não editar manualmente)
├── requirements.txt    # Dependências Python
└── .github/
    └── workflows/
        └── scraper.yml # Workflow GitHub Actions
```

## 💻 Uso local

```bash
# Instalar dependências
pip install -r requirements.txt
python -m playwright install chromium

# Scraping real
python scraper.py

# Modo demo (sem scraping, usa preços de referência)
python scraper.py --demo

# Gerar dashboard
python build_dashboard.py

# Abrir dashboard
open dashboard.html
```
