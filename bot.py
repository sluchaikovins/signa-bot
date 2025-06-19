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

@dp.message_handler(commands=['start'])
async def cmd_start(msg: types.Message):
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🔹 Заказать сигну", callback_data='order'),
        InlineKeyboardButton("📜 История заказов", callback_data='history'),
        InlineKeyboardButton("❓ Помощь", callback_data='help')
    )
    await msg.answer("Кликай кнопочки 👇", reply_markup=kb)

@dp.message_handler(commands=['admin'])
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return await msg.reply("Нет доступа.")
    if not orders:
        return await msg.reply("Нет заказов.")
    text = "📦 Заказы:\n\n"
    for i, o in enumerate(orders, 1):
        text += (
            f"{i}. ✉ @{o['username']}  | Стиль: {o['style']}  | "
            f"Цена: {o['price']}₽  | Оплачено: {'✅' if o['paid'] else '❌'}\n"
            f"   • Код: {o['code']}\n   • Контент: {o['content']}\n\n"
        )
    await msg.reply(text)

@dp.callback_query_handler(lambda c: c.data in ['order', 'history', 'help'])
async def main_menu(c: types.CallbackQuery):
    await c.message.delete()
    if c.data == 'order':
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("cozzych", callback_data='from_cozzych'))
        await bot.send_message(c.from_user.id, "Выберите от кого хотите сигну 👇", reply_markup=kb)
    elif c.data == 'history':
        await bot.send_message(c.from_user.id, "У тебя пока нет заказов.")
    else:
        await bot.send_message(c.from_user.id, "Нажми 'Заказать сигну' и следуй инструкциям.")
    await c.answer()

@dp.callback_query_handler(lambda c: c.data == 'from_cozzych')
async def choose_variant(c: types.CallbackQuery):
    await c.message.delete()
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🧥 Освещение 1 — 100₽", callback_data='style_1'),
        InlineKeyboardButton("👕 Освещение 2 — 120₽", callback_data='style_2')
    )
    await bot.send_message(c.from_user.id, "Выберите стиль 👇", reply_markup=kb)
    await c.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('style_'))
async def ask_for_text(c: types.CallbackQuery):
    await c.message.delete()
    uid = c.from_user.id
    style = c.data
    price = 100 if style == 'style_1' else 120
    user_states[uid] = {'stage': 'waiting_text', 'style': style, 'price': price}
    await bot.send_message(uid, "Отправь текст (≤64 символов) или фото.")
    await c.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get('stage') == 'waiting_text', content_types=['text','photo'])
async def handle_content(m: types.Message):
    uid = m.from_user.id
    st = user_states[uid]
    if m.text and len(m.text) > 64:
        return await m.reply("⚠️ Слишком много символов.")
    st['content'] = m.text if m.text else 'image'
    st['stage'] = 'promo'
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Ввести промокод", callback_data='enter_promo'),
        InlineKeyboardButton("❌ Пропустить", callback_data='skip_promo')
    )
    await m.reply("Есть промокод?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ['enter_promo', 'skip_promo'])
async def promo_step(c: types.CallbackQuery):
    await c.message.delete()
    uid = c.from_user.id
    if c.data == 'enter_promo':
        user_states[uid]['stage'] = 'waiting_promo'
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_promo'))
        await bot.send_message(uid, "Введите промокод:", reply_markup=kb)
    else:
        price = user_states[uid]['price']
        await show_summary(uid, price)
        await ask_payment(uid, price)
    await c.answer()

@dp.callback_query_handler(lambda c: c.data == 'back_to_promo')
async def back_to_promo(c: types.CallbackQuery):
    await c.message.delete()
    uid = c.from_user.id
    user_states[uid]['stage'] = 'promo'
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Ввести промокод", callback_data='enter_promo'),
        InlineKeyboardButton("❌ Пропустить", callback_data='skip_promo')
    )
    await bot.send_message(uid, "Есть промокод?", reply_markup=kb)
    await c.answer()

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get('stage') == 'waiting_promo')
async def apply_promo(m: types.Message):
    uid = m.from_user.id
    st = user_states[uid]
    promo = m.text.strip().lower()
    disc = PROMOCODES.get(promo)
    if disc:
        final_price = max(st['price'] - disc, 0)
        st['final_price'] = final_price
        await m.reply(f"✅ Промокод: −{disc}₽ → {final_price}₽")
        st['stage'] = 'waiting_payment'
        await show_summary(uid, final_price)
        await ask_payment(uid, final_price)
    else:
        await m.reply("❌ Неверный промокод.")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_promo'))
        await m.reply("У тебя есть кнопка назад:", reply_markup=kb)

async def show_summary(uid, price):
    st = user_states[uid]
    name = "Освещение 1" if st['style']=='style_1' else "Освещение 2"
    cont = "Текст" if st['content']!='image' else "Изображение"
    await bot.send_message(uid,
        f"✅ Заказ:\n• Стиль: {name}\n• Контент: {cont}\n• Цена: {price}₽")

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
        'style': "Освещение 1" if st['style']=='style_1' else "Освещение 2",
        'content': st['content'],
        'price': amount,
        'code': code,
        'paid': False
    })

    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Готово", callback_data='confirm_manual'))
    await bot.send_message(uid,
        f"💸 Оплатите {amount}₽ на DonatePay\nКомментарий: {code}\n⏳ 10 мин",
        reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == 'confirm_manual')
async def manual_confirm(c: types.CallbackQuery):
    await c.answer("Пожалуйста, ожидайте автоматической проверки.")
    await c.message.delete()

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
            if st.get('stage')=='waiting_payment' and o['code'] in com and amt >= o['price'] and tstamp >= st['payment_start']:
                o['paid'] = True
                st['paid'] = True
                st['stage'] = 'paid'
                await bot.send_message(uid, "✅ Оплата получена! В ближайшее время отправлю сигну.")
                break

async def payment_loop():
    while True:
        await check_all_payments()
        await asyncio.sleep(30)

if __name__ == '__main__':
    
    loop = asyncio.get_event_loop()
    loop.create_task(payment_loop())
    executor.start_polling(dp, skip_updates=True)
