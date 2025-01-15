# bot_messages.py

def get_time_translation(language_code, time): #time_diff.seconds
    time_translations = {
        'en': {
            "days": "days",
            "hours": "hours",
            "minutes": "minutes",
        },
        'ru': {
            "days": "дней",
            "hours": "часов",
            "minutes": "минут",
        }
    }

    days, remainder = divmod(time, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    time_str = ""
    if days > 0:
        time_str += f"{days} {time_translations.get(language_code, time_translations.get('en', {})).get('days', 'days')} "
    if hours > 0:
        time_str += f"{hours} {time_translations.get(language_code, time_translations.get('en', {})).get('hours', 'hours') } "
    if minutes > 0:
        time_str += f"{minutes} {time_translations.get(language_code, time_translations.get('en', {})).get('minutes', 'minutes')}"

    return time_str

def replace_placeholders(template, *args):

    for i, value in enumerate(args, start=1):
        placeholder = f"%{i}"
        template = template.replace(placeholder, str(value))
    return template


translations = {
    'en': {
        'text_start_msg': 'Hi!',
        "text_sea_fight": "Fight!",
        "text_score": "Score",
        "text_miss": "Miss!",
        "text_damaged": "Hit!",
        "text_killed": "Sunk!",
        'text_you_won': 'Game over',
        'text_leaderboard': '<b>Leaderboard</b>',
        'text_need_your_name': 'Wow! Let\'s add this to the leaderboard? Send your nickname to add it 👇',
        'text_leaderboard_adding': 'Hooray! Let\'s add this to the leaderboard 👏',
        'text_send_your_name': 'Send your nickname in a reply message 👇',
        'text_use_name': "Use name {name}",
        'text_use_other_name': "I'll send another name",
        'text_leaderboard_skip': "I don't want to be on the leaderboard",
        'text_leaderboard_added': "Hooray, I've added you to the leaderboard! %1 is in %2 place with a score of %3!",
        'text_share_msg': "Share your results with friends 👇",
        'text_share_text': "Check it out, I scored %1 points in <a href='https://t.me/games_telegram_robot?start=share'>Sea Battle</a>! Can you score more? 😉",
        'text_win': "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛\nYou win!\nYour score: %1\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        'text_win1': "🟩🟧🟥🟨🟪🟫⬛\nYou win!\nYour score: %1\n🟩🟧🟥🟨🟪🟫⬛",

        'error_text_leaderboard_name': "You can only use letters, numbers, spaces, and underscores. Send another option.",
        'error_text_cant_generate_board': "Failed to place ships on the board.",

        "btn_new_game": "New Game",
        "btn_leaderboard": "Leaderboard",
    },
    'ru': {
        'text_start_msg': 'Привет! ',
        "text_sea_fight": "В бой!",
        "text_score": "Очки",
        "text_miss": "Мимо!",
        "text_damaged": "Попал!",
        "text_killed": "Потопил!",
        'text_you_won': 'Игра окончена',
        'text_leaderboard': '<b>Таблица результатов</b>',
        'text_need_your_name': 'Вау! Давай добавим это в таблицу рекордов? Пришли свой ник для добавления 👇',
        'text_leaderboard_adding': 'Ура! Давай добавим это в таблицу рекордов 👏',
        'text_send_your_name': 'Пришли свой ник в ответном сообщении 👇',
        'text_use_name': "Зови меня {name}",
        'text_use_other_name': "Пришлю другое имя",
        'text_leaderboard_skip': "Не хочу на доску почета",
        'text_leaderboard_added': "Ура, добавил тебя на доску почета! %1 на %2 месте с результатом %3!",
        'text_share_msg': "Поделись своими результатами с друзьями 👇",
        'text_share_text': "Смотри, я набрал %1 очков в <a href='https://t.me/games_telegram_robot?start=share'>Морской бой</a>! Сможешь набрать больше? 😉",
        'text_win': "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛\nПобеда!\nТвой результат: %1\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛",
        'text_win1': "🟩🟧🟥🟨🟪🟫⬛\nПобеда!\nТвой результат: %1\n🟩🟧🟥🟨🟪🟫⬛",

        'error_text_leaderboard_name': "Можно использовать только буквы, цифры, пробелы и нижние подчеркивания. Пришли другой вариант.",
        'error_text_cant_generate_board': "Не удалось разместить корабли на поле.",

        "btn_new_game": "Новая игра",
        "btn_leaderboard": "Таблица рекордов",
    }
}


def get_translation(language_code, key):
    return translations.get(language_code, translations.get('en', {})).get(key, key)


monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]