import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (получите у @BotFather)
BOT_TOKEN = "8382779303:AAEw2EMcmprtXBFKN2TusH6CWqksTDk_Dk0"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT,
            pvz TEXT,
            code TEXT UNIQUE,
            registration_date TEXT
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            track_code TEXT,
            status TEXT,
            date_added TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Получение следующего кода для ПВЗ
def get_next_code(pvz):
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    
    if pvz == 'Жийдалик УПТК':
        cursor.execute("SELECT COUNT(*) FROM users WHERE pvz = 'Жийдалик УПТК'")
        count = cursor.fetchone()[0] + 1
        code = f"YX{count}"
    else:
        cursor.execute("SELECT COUNT(*) FROM users WHERE pvz IN ('Нариман', 'Достук')")
        count = cursor.fetchone()[0] + 1
        code = f"YQ{count}"
    
    conn.close()
    return code

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, зарегистрирован ли пользователь
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        # Пользователь уже зарегистрирован
        await show_main_menu(update, context)
    else:
        # Новый пользователь - предлагаем регистрацию
        keyboard = [
            [InlineKeyboardButton("📝 Зарегистрироваться", callback_data="register")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Добро пожаловать в Abu Cargo!\n\n"
            "Для использования бота необходимо зарегистрироваться.",
            reply_markup=reply_markup
        )

# Показать главное меню
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        keyboard = [
            [InlineKeyboardButton("📃 Мой профиль", callback_data="profile")],
            [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
            [InlineKeyboardButton("➕ Добавить заказ", callback_data="add_order")],
            [InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "🏠 Главное меню:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "🏠 Главное меню:",
                reply_markup=reply_markup
            )

# Обработка callback запросов
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "register":
        await start_registration(update, context)
    elif data == "profile":
        await show_profile(update, context)
    elif data == "my_orders":
        await show_orders(update, context)
    elif data == "add_order":
        await add_order(update, context)
    elif data == "edit_profile":
        await edit_profile(update, context)
    elif data == "back_to_menu":
        await show_main_menu(update, context)
    elif data.startswith("pvz_"):
        pvz = data[4:]
        context.user_data['pvz'] = pvz
        await ask_phone(update, context)

# Начало регистрации
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Нариман", callback_data="pvz_Нариман")],
        [InlineKeyboardButton("Жийдалик УПТК", callback_data="pvz_Жийдалик УПТК")],
        [InlineKeyboardButton("Достук", callback_data="pvz_Достук")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📍 Выберите ваш ПВЗ:",
        reply_markup=reply_markup
    )

# Запрос номера телефона
async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📱 Отправить номер", request_contact=True)],
        [InlineKeyboardButton("🔙 Назад", callback_data="register")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📱 Пожалуйста, поделитесь вашим номером телефона:",
        reply_markup=reply_markup
    )

# Обработка номера телефона
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
        context.user_data['phone'] = phone
        await ask_name(update, context)

# Запрос имени
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👤 Введите ваше ФИО:"
    )
    context.user_data['awaiting_name'] = True

# Завершение регистрации
async def complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_name'):
        name = update.message.text
        user_id = update.effective_user.id
        phone = context.user_data.get('phone')
        pvz = context.user_data.get('pvz')
        
        if not all([name, phone, pvz]):
            await update.message.reply_text("❌ Ошибка регистрации. Попробуйте снова.")
            return
        
        # Генерируем код
        code = get_next_code(pvz)
        
        # Сохраняем пользователя в базу
        conn = sqlite3.connect('abucargo.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, name, phone, pvz, code, registration_date) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, phone, pvz, code, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Очищаем временные данные
        context.user_data.clear()
        
        # Показываем профиль
        await show_profile_from_message(update, context, user_id)

# Показать профиль
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await show_profile_from_message(update, context, user_id)

async def show_profile_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        user_id, telegram_id, name, phone, pvz, code, reg_date = user
        
        # Информация о ПВЗ
        pvz_info = get_pvz_info(pvz)
        
        profile_text = f"""📃 Ваш профиль📃

🪪 Персональный КОД: {code}
👤 ФИО: {name}
📞 Номер: {phone}
🏡 Адрес: 

📍 ПВЗ: {pvz_info['address']}
📍 ПВЗ телефон: {pvz_info['phone']}
📍 Часы работы: {pvz_info['hours']}
📍 Локация на Карте: {pvz_info['map']}

Адрес в Китае:
御玺({code})
15727306315
浙江省金华市义乌市北苑街道春晗二区36栋好运国际货运5697库入仓号:御玺({code})"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")],
            [InlineKeyboardButton("📤 Поделиться профилем", callback_data="share_profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(profile_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(profile_text, reply_markup=reply_markup)

# Показать заказы
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('abucargo.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        user_db_id = user[0]
        cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY date_added DESC", (user_db_id,))
        orders = cursor.fetchall()
    
    conn.close()
    
    if not orders:
        text = "📦 У вас пока нет заказов."
    else:
        text = "📦 Ваши заказы:\n\n"
        for order in orders:
            order_id, user_id, track_code, status, date_added = order
            date = datetime.fromisoformat(date_added).strftime("%d.%m.%Y")
            text += f"📮 Трек: {track_code}\n"
            text += f"📊 Статус: {status}\n"
            text += f"📅 Дата: {date}\n"
            text += "─" * 20 + "\n"
    
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# Добавить заказ
async def add_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(
        "📦 Введите трек код заказа:"
    )
    context.user_data['awaiting_track'] = True

# Обработка трек кода
async def handle_track_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_track'):
        track_code = update.message.text
        user_id = update.effective_user.id
        
        conn = sqlite3.connect('abucargo.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user:
            user_db_id = user[0]
            cursor.execute(
                "INSERT INTO orders (user_id, track_code, status, date_added) VALUES (?, ?, ?, ?)",
                (user_db_id, track_code, "Ожидает получения", datetime.now().isoformat())
            )
            conn.commit()
        
        conn.close()
        
        context.user_data.clear()
        
        await update.message.reply_text(
            "✅ Заказ добавлен со статусом 'Ожидает получения'!\n"
            "Администратор изменит статус когда заказ будет в пути."
        )
        await show_main_menu(update, context)

# Информация о ПВЗ
def get_pvz_info(pvz):
    pvz_info = {
        'Нариман': {
            'phone': '+996997111118',
            'address': 'Нариман',
            'hours': '9:00 ДО 18:00',
            'map': 'https://2gis.kg/bishkek/'
        },
        'Жийдалик УПТК': {
            'phone': '+996997111118',
            'address': 'Жийделик УПТК, Улица Наби Ходжа, 28/3',
            'hours': '9:00 ДО 18:00',
            'map': 'https://2gis.kg/bishkek/geo/70030076876455182/72.781486,40.555853'
        },
        'Достук': {
            'phone': '+996997111118',
            'address': 'Достук',
            'hours': '9:00 ДО 18:00',
            'map': 'https://2gis.kg/bishkek/'
        }
    }
    return pvz_info.get(pvz, pvz_info['Жийдалик УПТК'])

# Редактирование профиля
async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить ФИО", callback_data="edit_name")],
        [InlineKeyboardButton("📱 Изменить телефон", callback_data="edit_phone")],
        [InlineKeyboardButton("📍 Изменить ПВЗ", callback_data="edit_pvz")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "✏️ Что вы хотите изменить?",
        reply_markup=reply_markup
    )

# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, complete_registration))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_track_code))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
