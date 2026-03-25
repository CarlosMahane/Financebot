"""
Bot Telegram de organização financeira.
Comandos:
  /start       - boas-vindas
  /resumo      - resumo do mês atual
  /ultimos     - últimas 5 transações
  /limite 2000 - define limite mensal
  /ajuda       - lista de comandos
  Texto livre  - registra transação
  Foto         - lê comprovante
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
import uuid

# Armazena transações pendentes em memória
pending_transactions = {}

import database as db
import claude_parser as parser

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://seu-dashboard.railway.app")


# ── helpers ──────────────────────────────────────────────────────────────────

def fmt_amount(amount: float) -> str:
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def category_emoji(cat: str) -> str:
    emojis = {
        "Alimentação": "🍽️", "Transporte": "🚗", "Saúde": "💊",
        "Moradia": "🏠", "Lazer": "🎮", "Educação": "📚",
        "Vestuário": "👕", "Mercado": "🛒", "Restaurante": "🍕",
        "Combustível": "⛽", "Farmácia": "💉", "Serviços": "🔧",
        "Receita": "💰", "Outros": "📌"
    }
    return emojis.get(cat, "📌")


async def confirm_transaction(update: Update, parsed: dict, raw_input: str, source: str):
    """Envia confirmação com botões Salvar / Cancelar."""
    user = update.effective_user
    emoji = category_emoji(parsed["category"])
    type_label = "💸 Gasto" if parsed["type"] == "expense" else "💰 Receita"

    text = (
        f"*Confirmar registro?*\n\n"
        f"{type_label}\n"
        f"{emoji} {parsed['category']}\n"
        f"💵 {fmt_amount(parsed['amount'])}\n"
        f"📝 {parsed['description']}\n"
        f"📅 {parsed['date']}"
    )

    # Salva dados em memória, usa UUID curto no callback
    tx_id = str(uuid.uuid4())[:8]
    pending_transactions[tx_id] = {
        "a": parsed["amount"],
        "c": parsed["category"],
        "d": parsed["description"],
        "dt": parsed["date"],
        "t": parsed["type"],
        "s": source
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Salvar", callback_data=f"save|{tx_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel|{tx_id}")
        ]
    ])

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


# ── command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username)

    text = (
        f"👋 Olá, *{user.first_name}*! Sou seu bot financeiro.\n\n"
        "Como usar:\n"
        "• Mande uma *foto* de comprovante ou nota\n"
        "• Escreva algo como `gastei 45 no almoço`\n"
        "• Use /resumo para ver seus gastos\n\n"
        "Tudo fica salvo e organizado pra você! 🗂️"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_resumo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username)

    transactions = db.get_monthly_summary(user.id)
    month_label = datetime.now().strftime("%B/%Y")
    summary = parser.build_summary_text(transactions, month_label)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Ver dashboard completo", url=f"{DASHBOARD_URL}?uid={user.id}")
    ]])
    await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def cmd_ultimos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username)
    txs = db.get_recent_transactions(user.id, limit=5)

    if not txs:
        await update.message.reply_text("Nenhuma transação ainda. Manda uma foto ou escreve um gasto!")
        return

    lines = ["*Últimas transações:*\n"]
    for t in txs:
        emoji = category_emoji(t["category"])
        sign = "+" if t["type"] == "income" else "-"
        lines.append(f"{emoji} {sign}{fmt_amount(t['amount'])} — {t['description']} _{t['transaction_date']}_")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_limite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args
    if not args or not args[0].replace(".", "").replace(",", "").isdigit():
        await update.message.reply_text("Use: /limite 2000 (valor em reais)")
        return

    value = float(args[0].replace(",", "."))
    db.get_client().table("users").update({"monthly_limit": value}).eq("id", user.id).execute()
    await update.message.reply_text(f"✅ Limite mensal definido: {fmt_amount(value)}")


async def cmd_ajuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Comandos disponíveis:*\n\n"
        "/start — boas-vindas\n"
        "/resumo — resumo do mês\n"
        "/ultimos — últimas 5 transações\n"
        "/limite 2000 — define limite mensal\n"
        "/ajuda — esta mensagem\n\n"
        "Ou simplesmente manda:\n"
        "• Uma *foto* de comprovante\n"
        "• Texto: `paguei 32 de Uber`\n"
        "• Áudio: fala o que gastou"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── message handlers ──────────────────────────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Processa mensagem de texto livre."""
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username)
    text = update.message.text

    msg = await update.message.reply_text("⏳ Analisando...")
    try:
        parsed = parser.parse_text(text)
        if "error" in parsed:
            await msg.edit_text(
                f"🤔 {parsed['error']}\n\nTente: gastei 50 no mercado ou /ajuda"
            )
        else:
            await msg.delete()
            await confirm_transaction(update, parsed, text, "text")
    except Exception as e:
        logger.error(f"Erro parse_text: {e}")
        try:
            await msg.edit_text("❌ Erro ao processar. Tente novamente.")
        except:
            await update.message.reply_text("❌ Erro ao processar. Tente novamente.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Processa foto de comprovante."""
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username)

    msg = await update.message.reply_text("📸 Lendo comprovante...")
    try:
        photo = update.message.photo[-1]  # maior resolução
        file = await ctx.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        parsed = parser.parse_image(bytes(image_bytes))
        if "error" in parsed:
            await msg.edit_text(f"🤔 Não identifiquei um comprovante.\n{parsed['error']}")
        else:
            await msg.delete()
            await confirm_transaction(update, parsed, "[foto]", "photo")
    except Exception as e:
        logger.error(f"Erro handle_photo: {e}")
        try:
            await msg.edit_text("❌ Erro ao ler imagem. Tente novamente.")
        except:
            await update.message.reply_text("❌ Erro ao ler imagem. Tente novamente.")


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Processa áudio — Whisper via Telegram não disponível sem API extra.
    Por ora pede que use texto."""
    await update.message.reply_text(
        "🎤 Para áudio, o Telegram ainda não fornece transcrição automática neste bot.\n\n"
        "Escreva o gasto em texto: `gastei 40 no restaurante` 😊"
    )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Botões inline — Salvar ou Cancelar."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if query.data == "cancel":
        await query.edit_message_text("❌ Cancelado.")
        return

    if query.data.startswith("save|"):
        tx_id = query.data[5:]
        data = pending_transactions.pop(tx_id, None)
        if not data:
            await query.edit_message_text("❌ Transação expirada. Manda de novo!")
            return
        try:
            tx = db.save_transaction(
                user_id=user.id,
                amount=data["a"],
                category=data["c"],
                description=data["d"],
                transaction_date=data["dt"],
                type_=data["t"],
                source=data["s"]
            )
            emoji = category_emoji(data["c"])
            type_label = "Gasto" if data["t"] == "expense" else "Receita"
            await query.edit_message_text(
                f"✅ {type_label} salvo!\n\n"
                f"{emoji} {data['c']} — {fmt_amount(data['a'])}\n"
                f"📝 {data['d']}\n\n"
                f"Use /resumo para ver seus gastos",
            )
        except Exception as e:
            logger.error(f"Erro save: {e}")
            await query.edit_message_text("❌ Erro ao salvar. Tente novamente.")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não definido!")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("ultimos", cmd_ultimos))
    app.add_handler(CommandHandler("limite", cmd_limite))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))

    start_dashboard()
    logger.info("Bot iniciado! 🤖")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()


def start_dashboard():
    """Inicia o servidor do dashboard em background."""
    import threading
    from server import start_server
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
