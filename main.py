import sqlite3
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY'

# Инициализация Gemini 2.0 Flash
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name='gemini-2.0-flash',
    system_instruction=(
        "Ты — карьерный консультант. "
        "Отвечай кратко, структурированно, используй эмодзи для наглядности. "
        "Фокусируйся на практических шагах."
    )
)

# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect('careerquest.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    interests TEXT,
    skills TEXT,
    work_preference TEXT
)''')
conn.commit()

class CareerForm(StatesGroup):
    interests = State()
    skills = State()
    work_preference = State()

# Клавиатуры
main_menu = ReplyKeyboardBuilder().add(
    KeyboardButton(text="🔍 Исследовать карьеру"),
    KeyboardButton(text="📚 Обучение и курсы"),
    KeyboardButton(text="💼 Поиск работы"),
    KeyboardButton(text="🤔 Получить совет")
).adjust(2).as_markup(resize_keyboard=True)

# Обработчик старта
@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer(
        "👋 Привет! Я помогу тебе найти новое направление для развития. Готов начать?",
        reply_markup=main_menu
    )

# Генерация рекомендаций через Gemini 2.0 Flash
@dp.message(F.text == "🔍 Исследовать карьеру")
async def explore_career(message: Message, state: FSMContext):
    await message.answer("Давайте начнем с ваших интересов. Что вам нравится делать?")
    await state.set_state(CareerForm.interests)

@dp.message(CareerForm.interests)
async def process_interests(message: Message, state: FSMContext):
    await state.update_data(interests=message.text)
    await message.answer("Отлично! Теперь расскажите о своих сильных сторонах или навыках:")
    await state.set_state(CareerForm.skills)

@dp.message(CareerForm.skills)
async def process_skills(message: Message, state: FSMContext):
    await state.update_data(skills=message.text)
    await message.answer(
        "Где вы предпочитаете работать?",
        reply_markup=ReplyKeyboardBuilder().add(
            KeyboardButton(text="Офис"),
            KeyboardButton(text="Удаленно"),
            KeyboardButton(text="Фриланс")
        ).adjust(3).as_markup(resize_keyboard=True)
    )
    await state.set_state(CareerForm.work_preference)

@dp.message(CareerForm.work_preference)
async def process_work_preference(message: Message, state: FSMContext):
    await state.update_data(work_preference=message.text)
    data = await state.get_data()

    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, interests, skills, work_preference)
        VALUES (?, ?, ?, ?)
    ''', (message.from_user.id, data['interests'], data['skills'], data['work_preference']))
    conn.commit()

    # Генерация рекомендаций через Gemini 2.0 Flash
    await message.answer("🔮 Анализируем ваши данные с помощью Gemini 2.0 Flash...", reply_markup=main_menu)
    try:
        prompt = f"""
        Пользователь хочет сменить карьеру. 
        Интересы: {data['interests']}.
        Навыки: {data['skills']}.
        Предпочтения: {data['work_preference']}.
        Предложи 3 профессии с:
        - Описанием (1 предложение)
        - Требованиями (2-3 пункта)
        - Ресурсами для старта (ссылки)
        Используй эмодзи для форматирования.
        """
        response = model.generate_content(prompt)
        await message.answer(f"🌟 Вот ваши рекомендации:\n\n{response.text}")

    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}. Попробуйте позже.")

    await state.clear()
@dp.message(F.text == "💼 Поиск работы")
async def job_search(message: Message):
    cursor.execute('SELECT skills, work_preference FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.answer("Сначала пройдите опрос через кнопку 🔍")
        return

    # Генерация вариантов работы через Gemini
    prompt = f"""
    Пользователь ищет работу с навыками: {user_data[0]}.
    Предпочтение: {user_data[1]}.
    Предложи 3 варианта вакансий с:
    - Названием должности
    - Уровнем зарплаты
    - Требованиями
    - Ссылками на платформы (например, hh.ru)
    """
    try:
        response = model.generate_content(prompt)
        await message.answer(f"💼 Рекомендуемые вакансии:\n\n{response.text}")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
        
@dp.message(F.text == "🤔 Получить совет")
async def get_advice(message: Message):
    # Используем Gemini для генерации советов
    prompt = """
    Дай 3 полезных совета для карьерного роста.
    Формат: совет + конкретное действие.
    Используй эмодзи и структурированный список.
    """
    try:
        response = model.generate_content(prompt)
        await message.answer(f"💡 Советы от Gemini:\n\n{response.text}")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
@dp.message(F.text == "📚 Обучение и курсы")
async def education_courses(message: Message):
    # Получаем данные пользователя из БД
    cursor.execute('SELECT interests, skills FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.answer("Сначала пройдите опрос через кнопку 🔍")
        return

    # Генерация курсов через Gemini
    prompt = f"""
    Пользователь хочет развиваться в области: {user_data[0]}.
    Его текущие навыки: {user_data[1]}.
    Предложи 3 подходящих образовательных курса с:
    - Названием платформы
    - Ссылкой
    - Кратким описанием
    - Продолжительностью
    Используй эмодзи для форматирования.
    """
    try:
        response = model.generate_content(prompt)
        await message.answer(f"🎓 Курсы для вас:\n\n{response.text}")
    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}")
        
# Запуск бота
if __name__ == '__main__':
    dp.run_polling(bot)
