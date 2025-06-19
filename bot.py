import random
import time
import aiohttp
import asyncio
import json
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

API_TOKEN = '...'  # вставь свой токен
DONATEPAY_API_KEY = '...'  # вставь свой ключ
ADMIN_ID = 123456789  # твой Telegram ID

DATA_FILE = 'orders_data.json'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

PROMOCODES = {'cozyfan': 20}
user_states = {}
orders = []
sending_signs = {}


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
        kb.insert(InlineKeyboardButton(text, callback_data=f"admin_order_{i - 1}"))
    await bot.send_message(admin_id, "📦 Список заказов:", reply_markup=kb)


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
        f"Код: {order['code']}\n"
        f"Контент:\n"
    )
    if cont['type'] == 'text':
        text += cont['text']
        media = None
    else:
        text += "[Фото]"
        media = InputMediaPhoto(media=cont['file_id'])

    kb = InlineKeyboardMarkup(row_width=2)
    if order['paid'] and not order.get('done', False):
        kb.add(InlineKeyboardButton("✉️ Отправить сигну", callback_data=f"admin_send_{idx}"))
        kb.add(InlineKeyboardButton("✅ Отметить выполненным", callback_data=f"admin_done_{idx}"))
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
    if idx >= len(orders):
        return await c.answer("Не найдено", show_alert=True)
    orders[idx]['done'] = True
    save_data()
    await c.answer("✅ Отмечено как выполненное")
    await send_admin_orders_list(c.from_user.id)


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
    idx = sending_signs.pop(admin_id)
    order = orders[idx]

    try:
        if m.photo:
            file_id = m.photo[-1].file_id
            await bot.send_photo(order['user_id'], file_id, caption="Ваша сигна от администратора")
            await m.reply("Сигна с фото отправлена.")
        elif m.text:
            await bot.send_message(order['user_id'], f"Ваша сигна от администратора:\n\n{m.text}")
            await m.reply("Текстовая сигна отправлена.")
        else:
            await m.reply("Отправьте текст или фото.")
            return
        order['done'] = True
        save_data()
    except Exception as e:
        await m.reply(f"Ошибка при отправке сигны: {e}")


@dp.callback_query_handler(lambda c: c.data == 'confirm_manual')
async def manual_confirm(c: types.CallbackQuery):
    await c.answer("Пожалуйста, ожидайте автоматической проверки.")
    await c.message.delete()


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
            if not o['paid'] and o['code'] in com and amt >= o['price'] and tstamp >= o['timestamp']:
                o['paid'] = True
                st['paid'] = True
                st['stage'] = 'paid'
                save_data()
                await bot.send_message(uid, "✅ Оплата получена! В ближайшее время отправлю сигну.")
                await bot.send_message(ADMIN_ID, f"⚡ Заказ #{orders.index(o) + 1} оплачен пользователем @{o['username']}.")
                break

    now = int(time.time())
    to_remove = []
    for i, o in enumerate(orders):
        if not o['paid'] and now - o['timestamp'] > 600:
            uid = o['user_id']
            user_states.pop(uid, None)
            to_remove.append(i)

    for i in reversed(to_remove):
        del orders[i]

    if to_remove:
        save_data()


async def payment_loop():
    while True:
        await check_all_payments()
        await asyncio.sleep(30)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(payment_loop())
    executor.start_polling(dp, skip_updates=True)
