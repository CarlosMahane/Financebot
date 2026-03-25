"""
Usa Claude Vision para extrair dados financeiros de imagens e textos.
"""
import anthropic
import base64
import os
import json
import re
from datetime import date


client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CATEGORIES = [
    "Alimentação", "Transporte", "Saúde", "Moradia",
    "Lazer", "Educação", "Vestuário", "Mercado",
    "Restaurante", "Combustível", "Farmácia", "Serviços",
    "Receita", "Outros"
]

PARSE_PROMPT = """Você é um extrator de dados financeiros. Analise a mensagem/imagem e extraia:
- amount: valor em reais (número float, ex: 45.90)
- category: uma das categorias: {categories}
- description: descrição curta do gasto (máx 50 chars)
- date: data no formato YYYY-MM-DD (se não informada, use hoje: {today})
- type: "expense" para gasto ou "income" para receita/entrada

Responda APENAS com JSON válido, sem texto extra. Exemplo:
{{"amount": 45.90, "category": "Alimentação", "description": "Almoço no restaurante", "date": "{today}", "type": "expense"}}

Se não conseguir extrair dados financeiros, responda:
{{"error": "Não entendi como um gasto ou receita"}}
""".format(categories=", ".join(CATEGORIES), today=date.today().isoformat())


def parse_text(text: str) -> dict:
    """Extrai dados financeiros de texto livre."""
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"{PARSE_PROMPT}\n\nMensagem do usuário: {text}"
        }]
    )
    
    raw = response.content[0].text.strip()
    # Remove possíveis blocos ```json
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
    return json.loads(raw)


def parse_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Extrai dados financeiros de imagem (comprovante, nota fiscal, etc)."""
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    
    response = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": PARSE_PROMPT + "\n\nAnalise a imagem acima (comprovante, nota fiscal, recibo, etc)."
                }
            ]
        }]
    )
    
    raw = response.content[0].text.strip()
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
    return json.loads(raw)


def parse_voice_transcription(text: str) -> dict:
    """Mesmo que parse_text mas com contexto de voz."""
    return parse_text(f"[Mensagem de voz transcrita]: {text}")


def build_summary_text(transactions: list, month_label: str = None) -> str:
    """Monta texto de resumo mensal para enviar pelo Telegram."""
    if not transactions:
        return "Nenhuma transação registrada ainda."
    
    total_exp = sum(t["amount"] for t in transactions if t["type"] == "expense")
    total_inc = sum(t["amount"] for t in transactions if t["type"] == "income")
    
    # Agrupa por categoria
    cats = {}
    for t in transactions:
        if t["type"] == "expense":
            c = t["category"]
            cats[c] = cats.get(c, 0) + t["amount"]
    
    cats_sorted = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    
    label = month_label or "este mês"
    lines = [
        f"📊 *Resumo — {label}*\n",
        f"💸 Gastos: R$ {total_exp:,.2f}",
        f"💰 Receitas: R$ {total_inc:,.2f}",
        f"📉 Saldo: R$ {total_inc - total_exp:,.2f}\n",
        "📂 *Por categoria:*"
    ]
    
    # Barra visual simples
    max_val = cats_sorted[0][1] if cats_sorted else 1
    for cat, val in cats_sorted[:8]:
        bar_len = int((val / max_val) * 12)
        bar = "▓" * bar_len + "░" * (12 - bar_len)
        pct = (val / total_exp * 100) if total_exp else 0
        lines.append(f"`{bar}` {cat}: R$ {val:.0f} ({pct:.0f}%)")
    
    return "\n".join(lines)
