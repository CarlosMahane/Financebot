"""
Camada de dados usando Upstash Redis.
Variáveis necessárias:
  UPSTASH_REDIS_REST_URL=https://xxxx.upstash.io
  UPSTASH_REDIS_REST_TOKEN=AXxx...
"""
import os
import json
from datetime import date, datetime
from upstash_redis import Redis

def get_client() -> Redis:
    return Redis(
        url=os.getenv("UPSTASH_REDIS_REST_URL"),
        token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
    )


# ── usuários ──────────────────────────────────────────────────────────────────

def ensure_user(user_id: int, name: str, username: str = None):
    """Cria ou atualiza usuário."""
    r = get_client()
    key = f"user:{user_id}"
    existing = r.get(key)
    if existing:
        data = json.loads(existing)
        # Atualiza nome se mudou
        data["name"] = name
        data["username"] = username
    else:
        data = {
            "id": user_id,
            "name": name,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "monthly_limit": None
        }
    r.set(key, json.dumps(data, ensure_ascii=False))


def set_monthly_limit(user_id: int, limit: float):
    r = get_client()
    key = f"user:{user_id}"
    raw = r.get(key)
    data = json.loads(raw) if raw else {"id": user_id}
    data["monthly_limit"] = limit
    r.set(key, json.dumps(data, ensure_ascii=False))


def get_user(user_id: int) -> dict | None:
    r = get_client()
    raw = r.get(f"user:{user_id}")
    return json.loads(raw) if raw else None


# ── transações ────────────────────────────────────────────────────────────────

def save_transaction(
    user_id: int,
    amount: float,
    category: str,
    description: str,
    transaction_date: str = None,
    type_: str = "expense",
    source: str = "text",
    raw_input: str = None
) -> dict:
    """Salva transação no Redis em duas listas: mensal e histórico completo."""
    r = get_client()
    tx_date = transaction_date or date.today().isoformat()
    month = tx_date[:7]  # YYYY-MM

    tx = {
        "id": f"{user_id}-{datetime.now().timestamp()}",
        "user_id": user_id,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_date": tx_date,
        "type": type_,
        "source": source,
        "raw_input": raw_input,
        "created_at": datetime.now().isoformat()
    }
    payload = json.dumps(tx, ensure_ascii=False)

    # Lista mensal (para resumos rápidos)
    r.lpush(f"txs:{user_id}:{month}", payload)
    # Lista histórico completo (para /ultimos)
    r.lpush(f"txs:{user_id}:all", payload)
    # Mantém histórico limitado a 500 entradas
    r.ltrim(f"txs:{user_id}:all", 0, 499)

    return tx


def get_monthly_transactions(user_id: int, month: str = None) -> list[dict]:
    """Retorna todas as transações de um mês (padrão: mês atual)."""
    r = get_client()
    if not month:
        month = datetime.now().strftime("%Y-%m")
    key = f"txs:{user_id}:{month}"
    items = r.lrange(key, 0, -1)
    return [json.loads(i) for i in items] if items else []


def get_recent_transactions(user_id: int, limit: int = 5) -> list[dict]:
    """Retorna as N transações mais recentes."""
    r = get_client()
    items = r.lrange(f"txs:{user_id}:all", 0, limit - 1)
    return [json.loads(i) for i in items] if items else []


# Alias usado pelo bot
get_monthly_summary = get_monthly_transactions
