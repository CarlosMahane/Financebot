# 💰 FinanceBot — Bot Telegram de Organização Financeira

## Stack
- **Python** + python-telegram-bot
- **Claude Vision** (Anthropic) para ler comprovantes
- **Supabase** (PostgreSQL grátis) para armazenar dados
- **Railway** para deploy

## Setup em 5 passos

### 1. Criar o bot no Telegram
1. Abra @BotFather no Telegram
2. `/newbot` → siga as instruções
3. Copie o token

### 2. Criar banco no Supabase
1. Crie projeto em supabase.com (grátis)
2. Vá em SQL Editor
3. Cole e execute o conteúdo de `database.py` (variável `SCHEMA_SQL`)

### 3. Configurar variáveis de ambiente
```bash
cp .env.example .env
# Preencha o .env com seus tokens
```

### 4. Deploy no Railway
1. Suba o código no GitHub
2. New Project → Deploy from GitHub
3. Adicione as variáveis de ambiente no Railway
4. Deploy automático!

### 5. Testar
Abra seu bot no Telegram e mande `/start`

## Como usar
- `/start` — boas-vindas
- `/resumo` — gráfico do mês atual
- `/ultimos` — últimas 5 transações
- `/limite 2000` — define alerta de limite
- Mande **foto** de qualquer comprovante
- Escreva em português livre: `gastei 50 no mercado`
