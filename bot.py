import random
import time
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8114029445:AAEz00_sHv9VhtfgdT2S3cK6hbJtiJ9dxSM'  # ⚠️ Замени на реальный

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {
    'cozyfan': 20
}

user_states = {}
orders = []
ADMIN_ID = 1284710177  # ⚠️ Замени на свой Telegram ID

def generate_unique_code():
    return str(random.randint(1000, 9999))

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🔹 Заказать сигну", callback_data='order'),
        InlineKeyboardButton("📜 История заказов", callback_data='history'),
        InlineKeyboardButton("❓ Помощь", callback_data='help')
    )
    await message.answer("Кликай кнопочки 👇", reply_markup=keyboard)

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("Нет доступа.")
    
    if not orders:
        return await message.reply("Нет заказов.")
    
    text = "📦 Заказы:\n\n"
    for i, order in enumerate(orders, 1):
        text += (
            f"{i}) 👤 @{order['username']}\n"
            f"• Стиль: {order['style']}\n"
            f"• Контент: {order['content']}\n"
            f"• Цена: {order['price']}₽\n"
            f"• Оплачено: {'✅ Да' if order['paid'] else '❌ Нет'}\n"
            f"• Код: {order['code']}\n\n"
        )
    await message.reply(text)

@dp.callback_query_handler(lambda c: c.data in ['order', 'history', 'help'])
async def main_menu(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    action = callback_query.data
    if action == 'order':
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("cozzych", callback_data='from_cozzych')
        )
        await bot.send_message(callback_query.from_user.id, "Выберите от кого хотите сигну 👇", reply_markup=keyboard)
    elif action == 'history':
        await bot.send_message(callback_query.from_user.id, "У тебя пока нет заказов. Закажи первую сигну!")
    elif action == 'help':
        await bot.send_message(callback_query.from_user.id, "Этот бот делает сигны. Нажми 'Заказать сигну' и введи имя.")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'from_cozzych')
async def choose_variant(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🧥 Освещение с одеждой 1 — 100₽", callback_data='style_1'),
        InlineKeyboardButton("👕 Освещение с одеждой 2 — 120₽", callback_data='style_2')
    )
    await bot.send_message(callback_query.from_user.id, "Выберите освещение с одеждой 👇", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('style_'))
async def ask_for_text(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    style = callback_query.data
    price = 100 if style == 'style_1' else 120

    user_states[user_id] = {
        'stage': 'waiting_text',
        'style': style,
        'price': price
    }

    warning = (
        "Отправь текст для сигны (макс. 64 символа) или изображение в формате A4.\n\n"
        "❗️ Убедись, что текст не нарушает законы и не содержит запрещённой символики."
    )
    await bot.send_message(user_id, warning)
    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get('stage') == 'waiting_text', content_types=['text', 'photo'])
async def handle_text_or_photo(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]

    if message.text and len(message.text) > 64:
        return await message.reply("⚠️ Текст слишком длинный! Максимум 64 символа.")

    user_states[user_id]['stage'] = 'promo'
    user_states[user_id]['content'] = message.text if message.text else 'image'

    promo_keyboard = InlineKeyboardMarkup(row_width=2)
    promo_keyboard.add(
        InlineKeyboardButton("✅ Ввести промокод", callback_data='enter_promo'),
        InlineKeyboardButton("❌ Пропустить", callback_data='skip_promo')
    )
    await message.reply("Есть промокод?", reply_markup=promo_keyboard)

@dp.callback_query_handler(lambda c: c.data in ['enter_promo', 'skip_promo'])
async def handle_promo_decision(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    state = user_states[user_id]

    if callback_query.data == 'enter_promo':
        user_states[user_id]['stage'] = 'waiting_promo'
        back_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад", callback_data='back_to_promo_choice')
        )
        await bot.send_message(user_id, "Введите промокод:", reply_markup=back_btn)
    elif callback_query.data == 'skip_promo':
        await show_final_summary(user_id, state['price'])
        await ask_for_payment(user_id, state['price'])

@dp.callback_query_handler(lambda c: c.data == 'back_to_promo_choice')
async def back_to_promo_menu(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_states[callback_query.from_user.id]['stage'] = 'promo'
    promo_keyboard = InlineKeyboardMarkup(row_width=2)
    promo_keyboard.add(
        InlineKeyboardButton("✅ Ввести промокод", callback_data='enter_promo'),
        InlineKeyboardButton("❌ Пропустить", callback_data='skip_promo')
    )
    await bot.send_message(callback_query.from_user.id, "Есть промокод?", reply_markup=promo_keyboard)

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get('stage') == 'waiting_promo')
async def apply_promo(msg: types.Message):
    user_id = msg.from_user.id
    state = user_states[user_id]
    promo = msg.text.strip().lower()
    discount = PROMOCODES.get(promo)

    if discount:
        final_price = max(state['price'] - discount, 0)
        await msg.reply(f"✅ Промокод подтверждён! (–{discount}₽)")
    else:
        await msg.reply("❌ Промокод не найден.")

        # Оставим кнопку "Назад"
        back_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад", callback_data='back_to_promo_choice')
        )
        await msg.reply("Попробуй ещё раз или вернись назад:", reply_markup=back_btn)
        return

    await show_final_summary(user_id, final_price)
    await ask_for_payment(user_id, final_price)
    user_states[user_id]['stage'] = 'done'

async def show_final_summary(user_id, final_price):
    content = user_states[user_id]['content']
    style = user_states[user_id]['style']
    style_name = "🧥 Освещение 1" if style == 'style_1' else "👕 Освещение 2"
    await bot.send_message(user_id,
        f"✅ Заказ принят!\n"
        f"• Стиль: {style_name}\n"
        f"• Контент: {'Текст' if content != 'image' else 'Изображение'}\n"
        f"• Итоговая цена: {final_price}₽\n\n"
        f"🔜 Ожидай выполнения сигны."
    )

async def ask_for_payment(user_id, amount):
    code = generate_unique_code()
    user_states[user_id]['payment_code'] = code
    user_states[user_id]['payment_amount'] = amount
    user_states[user_id]['payment_start'] = int(time.time())
    user_states[user_id]['stage'] = 'waiting_payment'

    # Сохраняем заказ
    orders.append({
        'user_id': user_id,
        'username': (await bot.get_chat(user_id)).username or 'нет username',
        'style': "Освещение 1" if user_states[user_id]['style'] == 'style_1' else "Освещение 2",
        'content': user_states[user_id]['content'],
        'price': amount,
        'code': code,
        'paid': False
    })

    pay_keyboard = InlineKeyboardMarkup(row_width=1)
    pay_keyboard.add(
        InlineKeyboardButton("✅ Готово", callback_data='confirm_payment')
    )

    await bot.send_message(user_id,
        f"💸 Оплатите {amount}₽ на DonatePay\n\n"
        f"⚠️ В комментарий укажите код: {code}\n\n"
        f"⏳ У тебя 10 минут. Проверка каждые 30 секунд.",
        reply_markup=pay_keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'confirm_payment')
async def confirm_payment(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    state = user_states.get(user_id)

    # Считаем оплату всегда успешной
    for order in orders:
        if order['user_id'] == user_id and order['code'] == state['payment_code']:
            order['paid'] = True
            break

    await bot.send_message(user_id, "✅ Оплата принята! Спасибо за заказ.")
    await callback_query.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
