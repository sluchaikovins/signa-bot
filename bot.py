import json
import random
import time
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8114029445:AAEz00_sHv9VhtfgdT2S3cK6hbJtiJ9dxSM'
DONATEPAY_API_KEY = 'MvZrwKfTVfiFWIIYZVptsNgAXMCWh698NkvLBKzBOiIfLbBZyatrEKV4uYv9'
ADMIN_ID = 1284710177  # Твой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {'cozyfan': 20}
user_states = {}
orders = []


def generate_unique_code():
    return str(random.randint(1000, 9999))


@dp.message_handler(commands=['admin'])
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return await msg.reply("Нет доступа.")
    if not orders:
        return await msg.reply("Нет заказов.")

    kb = InlineKeyboardMarkup(row_width=2)
    for i, o in enumerate(orders):
        text = f"Заказ {i + 1}"
        callback = f"order_{i}"
        kb.add(InlineKeyboardButton(text, callback_data=callback))
    await msg.reply("📦 Заказы:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith('order_'))
async def order_details(c: types.CallbackQuery):
    idx = int(c.data.split('_')[1])
    o = orders[idx]
    text = (
        f"📦 Заказ {idx + 1} от @{o['username'] or o['user_id']}\n"
        f"• Стиль: {o['style']}\n"
        f"• Контент: {o['content']}\n"
        f"• Цена: {o['price']}₽\n"
        f"• Код: {o['code']}\n"
        f"• Оплачен: {'✅ Да' if o['paid'] else '❌ Нет'}\n"
    )
    await c.message.edit_text(text)
    await c.answer()


async def ask_payment(uid, amount):
    st = user_states[uid]
    code = generate_unique_code()
    st.update({
        'payment_code': code,
        'payment_amount': amount,
        'payment_start': int(time.time()),
        'stage': 'waiting_payment',
        'paid': False
    })
    orders.append({
        'user_id': uid,
        'username': (await bot.get_chat(uid)).username or uid,
        'style': "Освещение 1" if st['style'] == 'style_1' else "Освещение 2",
        'content': st['content'],
        'price': amount,
        'code': code,
        'paid': False
    })

    await bot.send_message(uid,
        f"💸 Оплатите {amount}₽ на DonatePay\nКомментарий: {code}\n⏳ 10 минут. Оплата проверяется каждые 30 секунд.")


async def check_all_payments():
    async with aiohttp.ClientSession() as s:
        async with s.get("https://donatepay.ru/api/v1/donates", params={'token': DONATEPAY_API_KEY}) as r:
            if r.status != 200:
                print("Ошибка DonatePay:", r.status)
                return
            data = await r.json()
    for donation in data.get('data', []):
        com = donation.get('comment') or ''
        amt = float(donation.get('sum', 0))
        tstamp = int(donation.get('created_at', 0))
        for o in orders:
            uid = o['user_id']
            st = user_states.get(uid, {})
            if st.get('stage') == 'waiting_payment' and o['code'] in com and amt >= o['price'] and tstamp >= st['payment_start'] and not o['paid']:
                o['paid'] = True
                st['paid'] = True
                st['stage'] = 'paid'
                await bot.send_message(uid, "✅ Оплата получена! Заказ будет выполнен в течение 96 часов.\n\nСпасибо за заказ!")


async def payment_loop():
    while True:
        await check_all_payments()
        await asyncio.sleep(30)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(payment_loop())
    executor.start_polling(dp, skip_updates=True)
