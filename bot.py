import random
import time
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8114029445:AAEz00_sHv9VhtfgdT2S3cK6hbJtiJ9dxSM'  # Вставь сюда токен

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {
    'cozyfan': 20  # скидка 20 рублей
}

user_states = {}

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🔹 Заказать сигну", callback_data='order'),
        InlineKeyboardButton("📜 История заказов", callback_data='history'),
        InlineKeyboardButton("📞 Помощь", callback_data='help')
    )
    await message.answer("Кликай кнопочки 👇", reply_markup=keyboard)

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
        "❗️ Перед отправкой убедись, что текст не нарушает законы и не содержит запрещённой символики. "
        "При сомнениях обратись в 📞Помощь. В противном случае в выполнении сигны может быть отказано без возврата."
    )
    await bot.send_message(user_id, warning)
    await callback_query.answer()

@dp.message_handler(content_types=['text', 'photo'])
async def handle_text_or_photo(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if not state or state.get('stage') != 'waiting_text':
        return await message.reply("❗️ Сначала начни заказ через кнопку 'Заказать сигну'.")

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
    state = user_states.get(user_id)

    if callback_query.data == 'enter_promo':
        user_states[user_id]['stage'] = 'waiting_promo'
        await bot.send_message(user_id, "Введите промокод:")
    elif callback_query.data == 'skip_promo':
        final_price = state['price']
        await show_final_summary(user_id, final_price)
        await ask_for_payment(user_id, final_price)

    await callback_query.answer()

@dp.message_handler(lambda msg: user_states.get(msg.from_user.id, {}).get('stage') == 'waiting_promo')
async def apply_promo(msg: types.Message):
    user_id = msg.from_user.id
    promo = msg.text.strip().lower()
    state = user_states[user_id]
    discount = PROMOCODES.get(promo)

    if discount:
        final_price = max(state['price'] - discount, 0)
        await msg.reply(f"✅ Промокод применён! Скидка {discount}₽")
    else:
        final_price = state['price']
        await msg.reply("❌ Промокод не найден. Цена без скидки.")

    await show_final_summary(user_id, final_price)
    await ask_for_payment(user_id, final_price)
    user_states[user_id]['stage'] = 'done'

async def show_final_summary(user_id, final_price):
    content = user_states[user_id].get('content')
    style = user_states[user_id].get('style')
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

    pay_keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💳 Оплатить", callback_data='pay_now')
    )

    await bot.send_message(user_id, f"Итоговая стоимость: {amount}₽\n\nПодтвердите оплату:", reply_markup=pay_keyboard)

def generate_unique_code():
    return str(random.randint(1000, 9999))

@dp.callback_query_handler(lambda c: c.data == 'pay_now')
async def send_payment_instructions(callback_query: types.CallbackQuery):
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    state = user_states.get(user_id)

    if not state or state.get('stage') != 'waiting_payment':
        await callback_query.answer("Нет активной оплаты", show_alert=True)
        return

    code = state['payment_code']
    amount = state['payment_amount']

    text = (
        f"💸 Оплатите {amount} рублей на платформу:\n\n"
        f"🔗 DonatePay\n\n"
        f"📝 В комментарий к донату обязательно вставьте этот уникальный код: ⚠️ {code} ⚠️\n\n"
        f"⏳ На оплату дается 10 минут. После 10 минут заявка будет сброшена.\n"
        f"⏰ Я буду автоматически проверять оплату каждые 30 секунд."
    )
    await bot.send_message(user_id, text)
    await callback_query.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
