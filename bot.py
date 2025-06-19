import json
import random
import time
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8114029445:AAEz00_sHv9VhtfgdT2S3cK6hbJtiJ9dxSM'
ADMIN_ID = 1284710177 # ← Твой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {'cozyfan': 20}
user_states = {}
ORDERS_FILE = 'orders.json'

# Загрузка заказов
try:
    with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
        orders = json.load(f)
except FileNotFoundError:
    orders = []

# /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("🔹 Заказать сигну", callback_data='order'),
        InlineKeyboardButton("📜 История заказов", callback_data='history'),
        InlineKeyboardButton("❓ Помощь", callback_data='help')
    )
    await message.answer("Кликай кнопочки 👇", reply_markup=keyboard)

# /admin
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not orders:
        await message.answer("❌ Нет заказов.")
        return

    text = "📦 Последние заказы:\n"
    for i, order in enumerate(reversed(orders[-10:]), 1):
        text += (
            f"\n🔹 Заказ #{i}\n"
            f"👤 User: {order['user_id']}\n"
            f"• Стиль: {order['style']}\n"
            f"• Контент: {order['content']}\n"
            f"• Цена: {order['price']}₽\n"
            f"• Статус: {'✅ Оплачено' if order['paid'] else '❌ Не оплачено'}\n"
        )
    await message.answer(text)

# Главное меню
@dp.callback_query_handler(lambda c: c.data in ['order', 'history', 'help'])
async def main_menu(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    if c := callback_query.data == 'order':
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("cozzych", callback_data='from_cozzych')
        )
        await bot.send_message(callback_query.from_user.id, "Выберите от кого хотите сигну 👇", reply_markup=keyboard)
    elif c == 'history':
        await bot.send_message(callback_query.from_user.id, "У тебя пока нет заказов.")
    elif c == 'help':
        await bot.send_message(callback_query.from_user.id, "Нажми 'Заказать сигну' и следуй инструкциям.")
    await callback_query.answer()

# Выбор одежды
@dp.callback_query_handler(lambda c: c.data == 'from_cozzych')
async def choose_style(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🧥 Освещение с одеждой 1 — 100₽", callback_data='style_1'),
        InlineKeyboardButton("👕 Освещение с одеждой 2 — 120₽", callback_data='style_2')
    )
    await bot.send_message(callback_query.from_user.id, "Выбери стиль 👇", reply_markup=keyboard)

# Ввод текста или фото
@dp.callback_query_handler(lambda c: c.data.startswith('style_'))
async def ask_for_text(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    style = callback_query.data
    price = 100 if style == 'style_1' else 120
    user_states[user_id] = {'stage': 'waiting_text', 'style': style, 'price': price}
    await bot.send_message(user_id, (
        "Отправь текст для сигны (до 64 символов) или изображение формата A4.\n"
        "❗️ Запрещённый контент не принимается."
    ))

@dp.message_handler(content_types=['text', 'photo'])
async def handle_content(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not state or state.get('stage') != 'waiting_text':
        return await message.reply("Сначала начни заказ через кнопку 'Заказать сигну'.")
    if message.text and len(message.text) > 64:
        return await message.reply("⚠️ Текст слишком длинный! До 64 символов.")
    user_states[user_id]['stage'] = 'promo'
    user_states[user_id]['content'] = message.text if message.text else 'image'
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Ввести промокод", callback_data='enter_promo'),
        InlineKeyboardButton("❌ Пропустить", callback_data='skip_promo')
    )
    await message.reply("Есть промокод?", reply_markup=keyboard)

# Ввод промокода
@dp.callback_query_handler(lambda c: c.data in ['enter_promo', 'skip_promo'])
async def promo_flow(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    if callback_query.data == 'enter_promo':
        user_states[user_id]['stage'] = 'waiting_promo'
        back_keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад", callback_data='skip_promo')
        )
        await bot.send_message(user_id, "Введите промокод:", reply_markup=back_keyboard)
    else:
        price = user_states[user_id]['price']
        await show_summary(user_id, price)
        await ask_payment(user_id, price)
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get('stage') == 'waiting_promo')
async def apply_promo(msg: types.Message):
    user_id = msg.from_user.id
    promo = msg.text.strip().lower()
    discount = PROMOCODES.get(promo)
    if discount:
        new_price = max(user_states[user_id]['price'] - discount, 0)
        await msg.reply(f"✅ Промокод подтверждён. Скидка {discount}₽ (−{discount})")
        await show_summary(user_id, new_price)
        await ask_payment(user_id, new_price)
    else:
        await msg.reply("❌ Неверный промокод. Попробуй ещё или нажми 'Назад'.")

# Вывод заказа
async def show_summary(user_id, final_price):
    content = user_states[user_id]['content']
    style = user_states[user_id]['style']
    style_name = "🧥 Освещение 1" if style == 'style_1' else "👕 Освещение 2"
    await bot.send_message(user_id,
        f"✅ Заказ принят!\n"
        f"• Стиль: {style_name}\n"
        f"• Контент: {'Текст' if content != 'image' else 'Изображение'}\n"
        f"• Цена: {final_price}₽")

# Оплата
async def ask_payment(user_id, amount):
    code = str(random.randint(1000, 9999))
    user_states[user_id].update({
        'stage': 'waiting_payment',
        'payment_code': code,
        'payment_amount': amount,
        'payment_start': int(time.time())
    })
    orders.append({
        'user_id': user_id,
        'style': user_states[user_id]['style'],
        'content': user_states[user_id]['content'],
        'price': amount,
        'paid': False,
        'code': code
    })
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💳 Оплатить", callback_data='pay_now')
    )
    await bot.send_message(user_id, f"Итог: {amount}₽. Подтверди оплату:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'pay_now')
async def payment_instructions(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    code = user_states[user_id]['payment_code']
    amount = user_states[user_id]['payment_amount']
    await bot.send_message(user_id,
        f"💸 Оплатите {amount}₽ на DonatePay\n\n"
        f"⚠️ В комментарий укажите код: {code}\n\n"
        f"⏳ У тебя 10 минут. Проверка каждые 30 секунд.")
    await callback_query.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
