import random
import time
import aiohttp
import asyncio
import json
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

API_TOKEN = '8114029445:AAEz00_sHv9VhtfgdT2S3cK6hbJtiJ9dxSM'
DONATEPAY_API_KEY = 'MvZrwKfTVfiFWIIYZVptsNgAXMCWh698NkvLBKzBOiIfLbBZyatrEKV4uYv9'
ADMIN_ID = 1284710177  # Твой Telegram ID

DATA_FILE = 'orders_data.json'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {'cozyfan': 20}
user_states = {}
orders = []

# --- Работа с сохранением/загрузкой данных ---

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({'orders': orders, 'user_states': user_states}, f, ensure_ascii=False, indent=2)

def load_data():
    global orders, user_states
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            orders = data.get('orders', [])
            user_states = data.get('user_states', {})
    except FileNotFoundError:
        orders = []
        user_states = {}

load_data()

def generate_unique_code():
    return str(random.randint(1000, 9999))

# --- Команды ---

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
        return await msg.reply("❌ Нет доступа.")
    await send_admin_orders_list(msg.from_user.id)

async def send_admin_orders_list(admin_id):
    if not orders:
        await bot.send_message(admin_id, "📦 Заказов пока нет.")
        return
    kb = InlineKeyboardMarkup(row_width=2)
    for i, o in enumerate(orders, 1):
        paid_status = "✅" if o['paid'] else "❌"
        text = f"Заказ {i} {paid_status}"
        kb.insert(InlineKeyboardButton(text, callback_data=f"admin_order_{i-1}"))
    await bot.send_message(admin_id, "📦 Список заказов:", reply_markup=kb)

# --- Обработка заказа ---

@dp.callback_query_handler(lambda c: c.data in ['order', 'history', 'help'])
async def main_menu(c: types.CallbackQuery):
    await c.message.delete()
    if c.data == 'order':
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("cozzych", callback_data='from_cozzych'))
        await bot.send_message(c.from_user.id, "Выберите от кого хотите сигну 👇", reply_markup=kb)
    elif c.data == 'history':
        user_orders = [o for o in orders if o['user_id'] == c.from_user.id]
        if not user_orders:
            await bot.send_message(c.from_user.id, "У тебя пока нет заказов.")
            await c.answer()
            return
        text = "📝 Твои заказы:\n\n"
        for i, o in enumerate(user_orders, 1):
            paid = "✅ Оплачен" if o['paid'] else "❌ Не оплачен"
            text += f"{i}. Стиль: {o['style']}, Цена: {o['price']}₽, Статус: {paid}\n"
        await bot.send_message(c.from_user.id, text)
    else:
        await bot.send_message(c.from_user.id, "Нажми 'Заказать сигну' и следуй инструкциям.")
    await c.answer()

@dp.callback_query_handler(lambda c: c.data == 'from_cozzych')
async def choose_variant(c: types.CallbackQuery):
    await c.message.delete()
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Освещение 1 — 100₽", callback_data='style_1'),
        InlineKeyboardButton("Освещение 2 — 120₽", callback_data='style_2')
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

@dp.message_handler(lambda m: user_states.get(m.from_user.id, {}).get('stage') == 'waiting_text', content_types=['text', 'photo'])
async def handle_content(m: types.Message):
    uid = m.from_user.id
    st = user_states[uid]
    if m.text and len(m.text) > 64:
        return await m.reply("⚠️ Слишком много символов.")
    if m.photo:
        photo = m.photo[-1]
        st['content'] = {'type': 'photo', 'file_id': photo.file_id}
    else:
        st['content'] = {'type': 'text', 'text': m.text}
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
    name = "Освещение 1" if st['style'] == 'style_1' else "Освещение 2"
    cont = "Текст" if st['content']['type'] == 'text' else "Изображение"
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
    username = (await bot.get_chat(uid)).username or uid
    orders.append({
        'user_id': uid,
        'username': username,
        'style': "Освещение 1" if st['style'] == 'style_1' else "Освещение 2",
        'content': st['content'],
        'price': amount,
        'code': code,
        'paid': False,
        'done': False,
        'timestamp': int(time.time())
    })
    save_data()

    donate_url = f"https://donatepay.ru/checkout/{code}"

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Готово", callback_data='confirm_manual')
    )
    text = (
        f"💸 Оплатите {amount}₽ на "
        f'<a href="{donate_url}">DonatePay</a>\n'
        f"Комментарий: {code}\n⏳ 10 мин"
    )
    await bot.send_message(
    uid,
    f"💸 Оплатите <b>{amount}₽</b> на платформу:\n\n"
    f"<a href='https://new.donatepay.ru/@1393914'>DonatePay</a>\n\n"
    f"📝 В комментарий к донату обязательно вставьте этот уникальный код: ⚠️ <b>{code}</b> ⚠️\n\n"
    f"⏳ На оплату дается 10 минут. После 10 минут заявка будет сброшена.\n"
    f"⏰ Я буду автоматически проверять оплату каждые 30 секунд.",
    parse_mode='HTML'
)



@dp.callback_query_handler(lambda c: c.data == 'confirm_manual')
async def manual_confirm(c: types.CallbackQuery):
    await c.answer("Пожалуйста, ожидайте автоматической проверки.")
    await c.message.delete()

# --- Автоматическая проверка оплаты ---

async def check_all_payments():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://donatepay.ru/api/v1/donates", params={'token': DONATEPAY_API_KEY}) as resp:
            if resp.status != 200:
                print("Ошибка DonatePay:", resp.status)
                return
            data = await resp.json()
    for donation in data.get('data', []):
        com = donation.get('comment') or ''
        amt = float(donation.get('sum', 0))
        tstamp = int(donation.get('created_at', 0))
        for o in orders:
            uid = o['user_id']
            st = user_states.get(uid, {})
            if (not o['paid'] and
                o['code'] in com and
                amt >= o['price'] and
                tstamp >= o['timestamp']):
                o['paid'] = True
                st['paid'] = True
                st['stage'] = 'paid'
                save_data()
                await bot.send_message(uid, "✅ Оплата получена! В ближайшее время отправлю сигну.")
                await bot.send_message(ADMIN_ID, f"⚡ Заказ #{orders.index(o)+1} оплачен пользователем @{o['username']}.")
                break

# --- Админ: Просмотр и управление заказами ---

@dp.callback_query_handler(lambda c: c.data.startswith('admin_order_'))
async def admin_order_detail(c: types.CallbackQuery):
    await c.message.delete()
    admin_id = c.from_user.id
    if admin_id != ADMIN_ID:
        return await c.answer("Нет доступа", show_alert=True)
    idx = int(c.data.split('_')[-1])
    if idx < 0 or idx >= len(orders):
        return await c.answer("Заказ не найден", show_alert=True)
    order = orders[idx]

    paid = "✅ Оплачен" if order['paid'] else "❌ Не оплачен"
    done = "✅ Выполнен" if order.get('done', False) else "❌ Не выполнен"
    cont = order['content']

    text = (
        f"Заказ #{idx+1}\n"
        f"Пользователь: @{order['username']}\n"
        f"Стиль: {order['style']}\n"
        f"Цена: {order['price']}₽\n"
        f"Оплата: {paid}\n"
        f"Выполнение: {done}\n"
        f"Код для оплаты: {order['code']}\n"
        f"Контент:\n"
    )
    if cont['type'] == 'text':
        text += cont['text']
        media = None
    else:
        text += "[Фото]"
        media = InputMediaPhoto(media=cont['file_id'])

    kb = InlineKeyboardMarkup(row_width=2)
    if not order['paid']:
        kb.add(InlineKeyboardButton("❌ Отменить заказ", callback_data=f"admin_cancel_{idx}"))
    else:
        if not order.get('done', False):
            kb.add(InlineKeyboardButton("✅ Отметить выполненным", callback_data=f"admin_done_{idx}"))
        kb.add(InlineKeyboardButton("✉️ Отправить сигну", callback_data=f"admin_send_{idx}"))
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data='admin_back'))

    if media:
        await bot.send_photo(admin_id, cont['file_id'], caption=text, reply_markup=kb)
    else:
        await bot.send_message(admin_id, text, reply_markup=kb)
    await c.answer()

@dp.callback_query_handler(lambda c: c.data == 'admin_back')
async def admin_back(c: types.CallbackQuery):
    await c.message.delete()
    await send_admin_orders_list(c.from_user.id)
    await c.answer()

@dp.callback_query_handler(lambda c: c.data.startswith('admin_done_'))
async def admin_mark_done(c: types.CallbackQuery):
    idx = int(c.data.split('_')[-1])
    order = orders[idx]
    if order.get('done', False):
        await c.answer("Уже отмечен выполненным", show_alert=True)
        return
    orders[idx]['done'] = True
    save_data()
    await c.answer("Отметил как выполненный")
    await c.message.delete()
    await send_admin_orders_list(c.from_user.id)

@dp.callback_query_handler(lambda c: c.data.startswith('admin_cancel_'))
async def admin_cancel_order(c: types.CallbackQuery):
    idx = int(c.data.split('_')[-1])
    order = orders[idx]
    if order['paid']:
        await c.answer("Нельзя отменить оплаченный заказ", show_alert=True)
        return
    orders.pop(idx)
    save_data()
    await c.answer("Заказ отменён")
    await c.message.delete()
    await send_admin_orders_list(c.from_user.id)

# --- Отправка сигн пользователю от имени бота ---

sending_signs = {}  # user_id -> order_idx

@dp.callback_query_handler(lambda c: c.data.startswith('admin_send_'))
async def admin_send_sign_request(c: types.CallbackQuery):
    idx = int(c.data.split('_')[-1])
    sending_signs[c.from_user.id] = idx
    await c.message.delete()
    await bot.send_message(c.from_user.id, "Введите текст сигны или отправьте фото для пользователя:")
    await c.answer()

@dp.message_handler(lambda m: m.from_user.id in sending_signs)
async def admin_send_sign_handle(m: types.Message):
    admin_id = m.from_user.id
    idx = sending_signs[admin_id]
    order = orders[idx]

    try:
        if m.photo:
            photo = m.photo[-1]
            await bot.send_photo(order['user_id'], photo.file_id, caption="Ваша сигна от администратора")
            await m.reply("Сигна с фото отправлена пользователю.")
        elif m.text:
            await bot.send_message(order['user_id'], f"Ваша сигна от администратора:\n\n{m.text}")
            await m.reply("Текстовая сигна отправлена пользователю.")
        else:
            await m.reply("Отправьте текст или фото.")
            return
        orders[idx]['done'] = True
        save_data()
    except Exception as e:
        await m.reply(f"Ошибка при отправке пользователю: {e}")

    sending_signs.pop(admin_id)
    await send_admin_orders_list(admin_id)

# --- Запуск проверки оплаты в фоне ---

async def payment_loop():
    while True:
        await check_all_payments()
        await asyncio.sleep(30)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(payment_loop())
    executor.start_polling(dp, skip_updates=True)
