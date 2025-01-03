from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import os

# Admin username for contact button
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "echoFluxxx")

# Crypto payment options with placeholder addresses
CRYPTO_PAYMENTS = {
    "USDT (BEP20)": "0x792634EC84658D29A3Dd4cC1A5388dbdB8466765",
    "USDT (POL)": "0x106107F682D7CbD6B2eeb7c2B257df3C8020dbd6",
    "ETH": "0x792634EC84658D29A3Dd4cC1A5388dbdB8466765",
    "Solana": "EsjgHjpKap3GS2FZ2yNVfasnioqd2jvFbuYpsLfsrY1o",
    "TON": "UQBbbNgj8jF3y_A7jLUUR3pIFbsjj2KKeE9WjLGtZSvpdz3i"
}

async def show_payment_options(update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(crypto, callback_data=f"pay_{crypto}")]
        for crypto in CRYPTO_PAYMENTS.keys()
    ]
    keyboard.append([InlineKeyboardButton("Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💼 𝗖𝗵𝗼𝗼𝘀𝗲 𝗮 𝗽𝗮𝘆𝗺𝗲𝗻𝘁 𝗺𝗲𝘁𝗵𝗼𝗱:\n\n"
        "*Select one of the available cryptocurrencies to proceed with your payment*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_payment_selection(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_crypto = query.data.split('_')[1]
    address = CRYPTO_PAYMENTS[selected_crypto]

    payment_info = (
        f"🔐 𝗦𝗲𝗰𝘂𝗿𝗲 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗚𝗮𝘁𝗲𝘄𝗮𝘆\n\n"
        f"💱 𝗦𝗲𝗹𝗲𝗰𝘁𝗲𝗱 𝗖𝘂𝗿𝗿𝗲𝗻𝗰𝘆: {selected_crypto}\n\n"
        f"📋 𝗔𝗱𝗱𝗿𝗲𝘀𝘀:\n`{address}`\n\n"
        f"📝 𝗜𝗻𝘀𝘁𝗿𝘂𝗰𝘁𝗶𝗼𝗻𝘀:\n"
        f"1. Copy the address above\n"
        f"2. Send the exact amount to this address\n"
        f"3. After sending, click *'I've Paid'* button\n\n"
        f"⚠️ 𝗜𝗺𝗽𝗼𝗿𝘁𝗮𝗻𝘁: Ensure you're sending to the correct network!"
    )

    keyboard = [
        [InlineKeyboardButton("I've Paid", callback_data="payment_sent")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_payment")],
        [InlineKeyboardButton("Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=payment_info,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_payment_sent(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✅ 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗡𝗼𝘁𝗶𝗳𝗶𝗰𝗮𝘁𝗶𝗼𝗻 𝗦𝗲𝗻𝘁\n\n"
        "Thank you for your payment! Our admin will verify it shortly.\n"
        "Your subscription will be activated once the payment is confirmed.\n\n"
        f"If you have any questions, please contact `@{ADMIN_USERNAME}`",
        parse_mode='Markdown'
    )

async def handle_payment_cancel(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "❌ 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗖𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱\n\n"
        "You've cancelled the payment process.\n"
        "If you change your mind, you can always start over.\n\n"
        f"For any questions, please contact @{ADMIN_USERNAME}.",
        parse_mode='Markdown'
    )