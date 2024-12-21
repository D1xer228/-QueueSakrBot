import http.client
import os
import json
import telebot
from telebot import types
from collections import defaultdict
import datetime

from utils import map_lesson_name_to_subject

API_TOKEN = os.environ.get('BOT_TOKEN')  # Замените на свой токен
bot = telebot.TeleBot(API_TOKEN)

client = http.client.HTTPSConnection(os.environ.get('APP_HOST'))


# Получение расписания
def get_schedule(group_id: str, semester: int, week: str, day: str) -> list:
    url = f"/api/schedule/lesson/group/{group_id}?semester={semester}&week={week}&day={day}"
    client.request("GET", url)
    res = client.getresponse()
    response_data = res.read()
    response_json = json.loads(response_data.decode("utf-8"))
    return response_json


# Инициализация данных
# queues = defaultdict(lambda: defaultdict(list))  # Очереди по дням

if os.path.exists('data/queues.json'):
    with open('data/queues.json', 'r') as f:
        queues = json.load(f)
else:
    queues = defaultdict(lambda: defaultdict(list))  # Initialize if file doesn't exist

user_mode = {}
student_names = {}
student_groups = {}
groups = {
    "САкр-221": "8e1ed030-7032-4aa7-9df6-2d14c9e72d6a",
    "САкд-222.1 САкд-222.2": "30eaef7e-7ad6-420f-9a56-f108ff3e6496",
}

def save_queues():
    with open('data/queues.json', 'w') as f:
        json.dump(queues, f)

# Начальная команда
@bot.message_handler(commands=['start'])
def start(message):
    switch_mode(message)


@bot.message_handler(func=lambda message: message.text == "Вернуться назад")
def go_back(message):
    switch_mode(message)


# Обработка выбора режима
@bot.message_handler(func=lambda message: message.text in ["Студент", "Преподаватель"])
def set_mode(message):
    user_mode[message.chat.id] = message.text
    if message.text == "Студент":
        if message.chat.id not in student_names:
            bot.send_message(message.chat.id, "Введите ваше имя:")
            bot.register_next_step_handler(message, get_student_name)
        else:
            show_student_menu(message)
    else:
        bot.send_message(message.chat.id, "Введите пароль для доступа к режиму преподавателя:")
        bot.register_next_step_handler(message, check_teacher_password)


def check_teacher_password(message):
    teacher_password = "1123"  # Пример пароля
    if message.text == teacher_password:
        show_teacher_menu(message)
    else:
        bot.send_message(message.chat.id, "Неверный пароль.")
        switch_mode(message)


def get_student_name(message):
    student_names[message.chat.id] = message.text
    show_group_selection(message)


def show_group_selection(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for group in groups.keys():
        markup.add(types.KeyboardButton(group))
    bot.send_message(message.chat.id, "Выберите вашу группу:", reply_markup=markup)
    bot.register_next_step_handler(message, set_student_group)


def set_student_group(message):
    group = message.text
    if group in groups:
        student_groups[message.chat.id] = groups[group]
        bot.send_message(message.chat.id, f"Вы выбрали группу {group}.")
        show_student_menu(message)
    else:
        bot.send_message(message.chat.id, "Ошибка: группа не найдена.")
        show_group_selection(message)


def show_student_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("ПОКС"), types.KeyboardButton("АСОС"), types.KeyboardButton("ОАП"))
    markup.add(types.KeyboardButton("Показать очередь"), types.KeyboardButton("Освободить очередь"))
    markup.add(types.KeyboardButton("Вернуться назад"))
    bot.send_message(message.chat.id, "Выберите пару:", reply_markup=markup)




@bot.message_handler(func=lambda message: message.text in ["ПОКС", "АСОС", "ОАП"])
def show_lesson_info(message):
    lesson_name = message.text
    subject = map_lesson_name_to_subject(lesson_name)
    group_id = student_groups.get(message.chat.id)

    if group_id:
        fixed_date = datetime.datetime(2024, 12, 10)
        current_day = fixed_date.strftime('%A').lower()

        api_day = {
            'monday': 'monday',
            'tuesday': 'tuesday',
            'wednesday': 'wednesday',
            'thursday': 'thursday',
            'friday': 'friday',
            'saturday': 'saturday'
        }.get(current_day, 'monday')

        print(fixed_date, api_day)

        schedule = get_schedule(group_id, 5, "denominator", api_day)
        # print(schedule, api_day)

        if schedule:
            lesson_exists = any(subject.lower() in lesson['subject'].lower() for lesson in schedule)
            if lesson_exists:
                confirm_queue(message, subject)
            else:
                bot.send_message(message.chat.id, f"На {fixed_date.strftime('%Y-%m-%d')} нет пары {lesson_name}.")
        else:
            bot.send_message(message.chat.id, "Расписание не найдено.")
    else:
        bot.send_message(message.chat.id, "Группа не найдена.")
        switch_mode(message)


def confirm_queue(message, subject):
    student_name = student_names[message.chat.id]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Да"), types.KeyboardButton("Нет"))
    bot.send_message(message.chat.id, f"{student_name}, вы хотите занять очередь на {subject}?", reply_markup=markup)
    bot.register_next_step_handler(message, process_join_queue, subject)


def process_join_queue(message, subject):
    if message.text == "Да":
        student_name = student_names[message.chat.id]
        current_day = datetime.datetime.now().strftime('%A').lower()
        queues[current_day][subject].append(student_name)
        save_queues()
        bot.send_message(message.chat.id, f"{student_name}, вы заняли очередь на {subject}.")
        show_student_menu(message)
    elif message.text == "Нет":
        show_student_menu(message)
    else:
        bot.send_message(message.chat.id, "Неверный выбор.")
        show_student_menu(message)


@bot.message_handler(func=lambda message: message.text == "Показать очередь")
def show_queue(message):
    current_day = datetime.datetime.now().strftime('%A').lower()
    queue_str = "\n".join(
        f"{subject}: {', '.join(names)}" for subject, names in queues[current_day].items()) or "Очередь пуста."
    bot.send_message(message.chat.id, f"Очередь на сегодня:\n{queue_str}")
    
    if (user_mode.get(message.chat.id) == "Студент"):
        show_student_menu(message)
    else:
        show_teacher_menu(message)


@bot.message_handler(func=lambda message: message.text == "Освободить очередь")
def free_queue(message):
    current_day = datetime.datetime.now().strftime('%A').lower()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for subject in queues[current_day].keys():
        markup.add(types.KeyboardButton(subject))
    markup.add(types.KeyboardButton("Вернуться назад"))
    bot.send_message(message.chat.id, "Выберите пару для освобождения очереди:", reply_markup=markup)
    bot.register_next_step_handler(message, process_free_queue)


def process_free_queue(message):
    current_day = datetime.datetime.now().strftime('%A').lower()
    student_name = student_names.get(message.chat.id)
    if message.text in queues[current_day]:
        queues[current_day][message.text] = [name for name in queues[current_day][message.text] if name != student_name]
        save_queues()
        bot.send_message(message.chat.id, f"{student_name}, вы успешно покинули очередь на {message.text}.")
        show_student_menu(message)
    elif message.text == "Вернуться назад":
        show_student_menu(message)
    else:
        bot.send_message(message.chat.id, "Неверный выбор.")
        show_student_menu(message)


def switch_mode(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Студент"), types.KeyboardButton("Преподаватель"))
    bot.send_message(message.chat.id, "Выберите режим:", reply_markup=markup)


def show_teacher_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Показать очередь"))
    bot.send_message(message.chat.id, "Режим преподавателя. Выберите действие:", reply_markup=markup)


def show_teacher_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Показать очередь"), types.KeyboardButton("Удалить студента"))
    markup.add(types.KeyboardButton("Вернуться назад"))
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Удалить студента")
def ask_for_student_name_to_remove(message):
    bot.send_message(message.chat.id, "Введите имя студента, которого хотите удалить из очереди:")
    bot.register_next_step_handler(message, remove_student_from_queue)

def remove_student_from_queue(message):
    student_name_to_remove = message.text
    removed = False
    for day, queue in queues.items():
        for lesson, students in queue.items():
            if student_name_to_remove in students:
                students.remove(student_name_to_remove)
                removed = True
                save_queues()
                break
    if removed:
        bot.send_message(message.chat.id, f"Студент {student_name_to_remove} удален из очереди.")
    else:
        bot.send_message(message.chat.id, f"Студент {student_name_to_remove} не найден в очереди.")
    show_teacher_menu(message)


# Запуск бота
bot.polling()
