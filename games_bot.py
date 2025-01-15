from games_bot_config import DB_CONFIG, API_TOKEN, BOT_SETTINGS
from bot_messages import get_translation, replace_placeholders

from abc import ABC
from datetime import datetime
import random
import os
import re
import time

import mysql.connector
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ApplicationBuilder, ContextTypes
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram import ReplyKeyboardRemove

ROWS = 8
COLS = 8
DELAY = 0.4
EMPTY = ' 🟦 '
AVALIABLE = ' 🟩 '
SHIP = ' 🔳 '
BUILDING_SHIP = ' 🔲 '
BANG = ' 💥 '
BIGBANG = ' 💢 '
MISS = ' 💠 '
SHIPS = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
# SHIPS = [1]

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class DatabaseConnectionManager:
    def __enter__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

class UserManager:
    def __init__(self, conn):
        self.conn = conn

    def get_user_info(self, user_id):
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM {BOT_SETTINGS['users_table']} WHERE user_id = %s", (user_id,))
        user_info = cursor.fetchone()
        cursor.close()
        return user_info if user_info else -1

    def save_user_info(self, user_id, first_name, last_name, username, phone_number, is_bot, language_code, is_premium, source):
        cursor = self.conn.cursor()
        cursor.execute(f'''
            INSERT INTO {BOT_SETTINGS['users_table']} (user_id, first_name, last_name, username, phone_number, is_bot, language_code, is_premium, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            first_name = VALUES(first_name),
            last_name = VALUES(last_name),
            username = VALUES(username),
            phone_number = VALUES(phone_number),
            is_bot = VALUES(is_bot),
            language_code = VALUES(language_code),
            is_premium = VALUES(is_premium),
            source = VALUES(source)
        ''', (user_id, first_name, last_name, username, phone_number, is_bot, language_code, is_premium, source))
        self.conn.commit()
        cursor.close()

    def update_leader_board_name(self, user_id, leader_board_name):
        if not is_safe_leader_board_name(leader_board_name):
            return False

        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE {BOT_SETTINGS['users_table']}
            SET leader_board_name = %s
            WHERE user_id = %s
        ''', (leader_board_name, user_id))
        self.conn.commit()
        cursor.close()
        return True

class BaseBoard(ABC):
    def __init__(self, rows, cols, empty_symbol, initial_board=None):
        self.rows = rows
        self.cols = cols
        self.empty_symbol = empty_symbol
        if initial_board:
            self.board = initial_board
        else:
            self.board = [[empty_symbol for _ in range(cols)] for _ in range(rows)]

    def display(self):
        for line in self.board:
            print(" ".join(line))

    def update_cell(self, x, y, symbol):
        if 0 <= x < self.rows and 0 <= y < self.cols:
            self.board[x][y] = symbol
        else:
            raise ValueError("Wrong coordinates")

class Board(BaseBoard):
    def __init__(self, rows, cols, empty_symbol, initial_board=None):
        super().__init__(rows, cols, empty_symbol, initial_board)

    def is_cell_empty(self, x, y):
        return self.board[x][y] == self.empty_symbol

    def place_ship(self, ship):
        for x, y in ship.get_coordinates():
            self.update_cell(x, y, ship.symbol)

    def is_ship_placed(self, x, y):
        return self.board[x][y] == SHIP

class PlayerBoard(BaseBoard):
    def __init__(self, rows, cols, empty_symbol, initial_board=None):
        super().__init__(rows, cols, empty_symbol, initial_board)

class GameLogic:
    def __init__(self, rows, cols, empty_symbol, ship_symbol, initial_board=None, initial_player_board=None):
        self.rows = rows
        self.cols = cols
        self.empty_symbol = empty_symbol
        self.ship_symbol = ship_symbol
        self.board = Board(rows, cols, empty_symbol, initial_board)
        self.player_board = PlayerBoard(rows, cols, empty_symbol, initial_player_board)
        self.is_board_generated = False

    def generate_board(self, ships):
        if self.is_board_generated:
            return True
        max_attempts = 20
        placed = False
        for attempt in range(max_attempts):
            board = Board(self.rows, self.cols, self.empty_symbol)

            for ship_size in ships:
                ship = Ship(ship_size, self.ship_symbol)
                placed = False
                tries = 200

                while not placed and tries > 0:
                    x = random.randint(0, self.rows - 1)
                    y = random.randint(0, self.cols - 1)
                    direction = random.choice(['horizontal', 'vertical'])
                    placed = ship.place(x, y, direction, board)
                    tries -= 1

                if not placed:
                    break
            if placed:
                break

        if not placed:
            return False

        self.is_board_generated = True
        self.board = board
        return True

    def check_if_killed(self, x, y):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            for i in range(self.rows):
                nx, ny = x + dx * i, y + dy * i
                if 0 <= nx < self.rows and 0 <= ny < self.cols and self.board.is_ship_placed(nx, ny):
                    return False
                elif 0 <= nx < self.rows and 0 <= ny < self.cols and self.board.is_cell_empty(nx, ny):
                    break
        return True

    def check_if_won(self):
        return all(not self.board.is_ship_placed(x, y) for x in range(self.rows) for y in range(self.cols))

class LeaderboardManager:
    def __init__(self, conn):
        self.conn = conn

    def add_leaderboard_entry(self, user_id, name, score):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO gamebot_leaderboard (user_id, name, score)
            VALUES (%s, %s, %s)
        ''', (user_id, name, score))
        self.conn.commit()

        cursor.execute('''
            SELECT COUNT(*) + 1 AS position
            FROM gamebot_leaderboard
            WHERE score > %s
        ''', (score,))
        position = cursor.fetchone()[0]
        cursor.close()
        return position

    def update_leader_board_name(self, user_id, leader_board_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE gamebot_users
            SET leader_board_name = %s
            WHERE user_id = %s
        ''', (leader_board_name, user_id))
        self.conn.commit()
        cursor.close()

    def get_top_leaderboard(self, limit=100):
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT user_id, name, score, date
            FROM gamebot_leaderboard
            ORDER BY score DESC
            LIMIT %s
        ''', (limit,))
        results = cursor.fetchall()
        cursor.close()
        return results

class Ship:
    def __init__(self, size, symbol):
        self.size = size
        self.symbol = symbol
        self.coordinates = []
        self.empty_zone = []

    def get_coordinates(self):
        return self.coordinates

    def place(self, x, y, direction, board):
        if direction == 'horizontal':
            self.coordinates = [(x, y + i) for i in range(self.size)]
            self.empty_zone = [(x + dx, y + dy) for dx in range(-1, 2) for dy in range(-1, self.size + 1)]

        elif direction == 'vertical':
            self.coordinates = [(x + i, y) for i in range(self.size)]
            self.empty_zone = [(x + dx, y + dy) for dx in range(-1, self.size + 1) for dy in range(-1, 2)]

        if all(0 <= x < board.rows and 0 <= y < board.cols and board.is_cell_empty(x, y) for x, y in self.coordinates):
            if all(board.is_cell_empty(x, y) for x, y in self.empty_zone if 0 <= x < board.rows and 0 <= y < board.cols):
                board.place_ship(self)
                return True
        return False


class ButtonFactory:
    def create_button(self, text_key, callback_data, language_code, **format_kwargs):
        text = get_translation(language_code, text_key)

        if format_kwargs:
            text = text.format(**format_kwargs)

        return InlineKeyboardButton(text, callback_data=callback_data)

class KeyboardBuilder:
    def __init__(self, button_factory):
        self.button_factory = button_factory

    def create_name_keyboard(self, language_code, current_user_info):
        keyboard = []
        row = []

        name = current_user_info.get('leader_board_name') or current_user_info.get('first_name', '')
        if name:
            button = self.button_factory.create_button(
                'text_use_name',
                'name_tg' if not current_user_info.get('leader_board_name') else 'name_lastused',
                language_code=language_code,
                name=name  # Передаем имя для форматирования
            )
            row.append(button)

        row.append(self.button_factory.create_button('text_use_other_name', 'name_new', language_code))
        keyboard.append(row)

        keyboard.append([
            self.button_factory.create_button('text_leaderboard_skip', 'leaderboard_skip', language_code)
        ])

        return InlineKeyboardMarkup(keyboard)

    def create_main_keyboard(self, language_code):
        keyboard = [
            [self.button_factory.create_button('btn_new_game', 'newgame', language_code)],
            [self.button_factory.create_button('btn_leaderboard', 'leaderboard_show', language_code)]
        ]
        return InlineKeyboardMarkup(keyboard)

    def create_sea_fight_keyboard(self, player_board):
        keyboard = []
        for y in range(player_board.rows):
            row = []
            for x in range(player_board.cols):
                sym = player_board.board[y][x]
                row.append(InlineKeyboardButton(sym, callback_data=f'fire_{x}_{y}'))
            keyboard.append(row)
        return InlineKeyboardMarkup(keyboard)


async def send_game_start_message(update, context, user, game_manager):
    image_path = os.path.join(os.path.dirname(__file__), 'img', f"seafight.jpg")
    button_factory = ButtonFactory()
    keyboard_builder = KeyboardBuilder(button_factory)
    with open(image_path, 'rb') as photo:
        main_keyboard = keyboard_builder.create_main_keyboard(user.language_code)
        await context.bot.send_photo(chat_id=user.id, photo=photo, parse_mode='HTML',
                                     reply_markup=main_keyboard)

    kbd = keyboard_builder.create_sea_fight_keyboard(game_manager.player_board)

    await context.bot.send_message(chat_id=user.id, parse_mode='HTML', text=get_translation(user.language_code, "text_sea_fight"), reply_markup=kbd)

async def send_error_message(update, context, user):
    button_factory = ButtonFactory()
    keyboard_builder = KeyboardBuilder(button_factory)
    kbd = keyboard_builder.create_main_keyboard(user.language_code)
    await context.bot.send_message(chat_id=user.id, parse_mode='HTML', text=get_translation(user.language_code, "error_text_cant_generate_board"), reply_markup=kbd)

async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    with DatabaseConnectionManager() as conn:
        user_manager = UserManager(conn)
        current_user_info = user_manager.get_user_info(user.id)
        if current_user_info == -1:
            user_manager.save_user_info(
                user.id, user.first_name, user.last_name, user.username,
                update.message.contact.phone_number if update.message.contact else None,
                user.is_bot, user.language_code, user.is_premium,
                context.args[0][:50] if context.args else None
            )

    await update.message.reply_text(
        get_translation(user.language_code, "text_start_msg"),
        reply_markup=ReplyKeyboardRemove()
    )

    game_manager = GameLogic(ROWS, COLS, EMPTY, SHIP)
    if game_manager.generate_board(SHIPS):
        await send_game_start_message(update, context, user, game_manager)
        context.user_data['board'] = game_manager.board.board
        context.user_data['player_board'] = game_manager.player_board.board
    else:
        await send_error_message(update, context, user)


async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    print(f'[{user_id}] {bcolors.OKCYAN}handle_callback_query{bcolors.ENDC}  {datetime.now()}')
    await query.answer()
    data = query.data
    print(f'[{user_id}] data = {data}')
    language_code = update.effective_user.language_code
    chat_id = update.effective_chat.id
    message_id = query.message.message_id

    data = data.split('_')
    score = context.user_data.get('score', 0)
    initial_board = context.user_data.get('board', None)
    initial_player_board = context.user_data.get('player_board', None)

    game_logic = GameLogic(ROWS, COLS, EMPTY, SHIP, initial_board, initial_player_board)
    button_factory = ButtonFactory()
    keyboard_builder = KeyboardBuilder(button_factory)

    if data[0] == 'fire':
        if game_logic and not game_logic.check_if_won():
            _, y, x = data
            x = int(x)
            y = int(y)

            text = get_translation(language_code, 'text_miss')

            if game_logic.board.is_ship_placed(x, y):
                game_logic.player_board.update_cell(x, y, BANG)
                game_logic.board.update_cell(x, y, BANG)
                score += 10

                if game_logic.check_if_killed(x, y):
                    text = get_translation(language_code, 'text_killed')
                    await blinking_sea_fight(x, y, game_logic.board.board, game_logic.player_board, context, chat_id, message_id, text + f"\n{get_translation(language_code, 'text_score')}: {score}")
                else:
                    text = get_translation(language_code, 'text_damaged')

            elif game_logic.board.is_cell_empty(x, y):
                game_logic.player_board.update_cell(x, y, MISS)
                score -= 1
            else:
                return

            new_kbd = keyboard_builder.create_sea_fight_keyboard(game_logic.player_board)

            context.user_data['score'] = score
            context.user_data['board'] = game_logic.board.board
            context.user_data['player_board'] = game_logic.player_board.board
            context.user_data['operation'] = ""

            if game_logic.check_if_won():
                text = get_translation(language_code, 'text_win')
                text = replace_placeholders(text, score)
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text,
                                                    parse_mode='HTML', reply_markup=new_kbd)

                await context.bot.send_message(chat_id=user_id, text=get_translation(language_code, 'text_share_msg'))
                text = get_translation(language_code, 'text_share_text')
                text = replace_placeholders(text, score)
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')

                with DatabaseConnectionManager() as conn:
                    user_manager = UserManager(conn)
                    current_user_info = user_manager.get_user_info(user_id)

                name_kbd = keyboard_builder.create_name_keyboard(language_code, current_user_info)

                if not current_user_info['leader_board_name'] or current_user_info['leader_board_name'] == '':
                    await context.bot.send_message(chat_id=user_id, text=get_translation(language_code, 'text_need_your_name'), reply_markup=name_kbd)
                    context.user_data['operation'] = "waiting_for_name"
                else:
                    await context.bot.send_message(chat_id=user_id, text=get_translation(language_code, 'text_leaderboard_adding'), reply_markup=name_kbd)

            else:
                text += f"\n{get_translation(language_code, 'text_score')}: {score}"
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text,
                                                    parse_mode='HTML', reply_markup=new_kbd)

    elif data[0] == 'name':
        if data[1] == 'tg':
            context.user_data['operation'] = ""
            with DatabaseConnectionManager() as conn:
                user_manager = UserManager(conn)
                current_user_info = user_manager.get_user_info(user_id)
                name = current_user_info['first_name']
                leaderboard_manager = LeaderboardManager(conn)
                position = leaderboard_manager.add_leaderboard_entry(user_id, name, score)

            text = get_translation(language_code, 'text_leaderboard_added')
            text = replace_placeholders(text, name, position, score)
            new_kbd = keyboard_builder.create_main_keyboard(language_code)

            try:
                await context.bot.delete_message(chat_id=user_id, message_id=message_id)
            except Exception as e:
                print(f"Error while deleting message with message_id {message_id}: {e}")

            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=new_kbd)

        elif data[1] == 'lastused':
            context.user_data['operation'] = ""
            with DatabaseConnectionManager() as conn:
                user_manager = UserManager(conn)
                current_user_info = user_manager.get_user_info(user_id)
                name = current_user_info['leader_board_name']
                leaderboard_manager = LeaderboardManager(conn)
                position = leaderboard_manager.add_leaderboard_entry(user_id, name, score)

            text = get_translation(language_code, 'text_leaderboard_added')
            text = replace_placeholders(text, name, position, score)
            new_kbd = keyboard_builder.create_main_keyboard(language_code)

            try:
                await context.bot.delete_message(chat_id=user_id, message_id=message_id)
            except Exception as e:
                print(f"Error while deleting message with message_id {message_id}: {e}")

            await context.bot.send_message(chat_id=user_id, text=text, reply_markup=new_kbd)

        elif data[1] == 'new':
            await context.bot.send_message(chat_id=user_id,
                                           text=get_translation(language_code, 'text_send_your_name'))
            context.user_data['operation'] = "waiting_for_name"

    elif data[0] == 'leaderboard':
        if data[1] == 'skip':
            new_kbd = keyboard_builder.create_main_keyboard(language_code)
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"{get_translation(language_code, 'text_you_won')}: {score}",
                                                parse_mode='HTML', reply_markup=new_kbd)
        if data[1] == 'show':
            with DatabaseConnectionManager() as conn:
                leaderboard_manager = LeaderboardManager(conn)
                top = leaderboard_manager.get_top_leaderboard()
            text = get_translation(language_code, 'text_leaderboard')
            position = 1
            for entry in top:
                text += f"\n{position}. {entry['name']} [{entry['score']}]"
                position += 1
            new_kbd = keyboard_builder.create_main_keyboard(language_code)
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text,
                                                parse_mode='HTML', reply_markup=new_kbd)
            except:
                await context.bot.send_message(chat_id=chat_id, text=text,
                                                parse_mode='HTML', reply_markup=new_kbd)

    elif data[0] == 'newgame':
        context.user_data['score'] = 0

        game_manager = GameLogic(ROWS, COLS, EMPTY, SHIP)
        if game_manager.generate_board(SHIPS):
            await send_game_start_message(update, context, user, game_manager)
            context.user_data['board'] = game_manager.board.board
            context.user_data['player_board'] = game_manager.player_board.board
            game_manager.board.display()
        else:
            await send_error_message(update, context, user)

async def handle_text_message(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    language_code = update.effective_user.language_code
    text = update.message.text
    user_id = update.effective_chat.id
    operation = context.user_data.get('operation', None)

    if operation == "waiting_for_name":
        name = text[:50]
        if not is_safe_leader_board_name(name):
            await update.message.reply_text(get_translation(language_code, 'error_text_leaderboard_name'))
        else:
            with DatabaseConnectionManager() as conn:
                user_manager = UserManager(conn)
                user_manager.update_leader_board_name(user_id, name)
                text = get_translation(language_code, 'text_leaderboard_added')
                score = context.user_data.get('score', 0)
                leaderboard_manager = LeaderboardManager(conn)
                position = leaderboard_manager.add_leaderboard_entry(user_id, name, score)
            text = replace_placeholders(text, name, position, score)
            await update.message.reply_text(text)


def is_safe_leader_board_name(name):
    if not name:
        return False
    pattern = r'^[a-zA-Zа-яА-Я0-9_ .-]+$'
    return re.match(pattern, name) is not None

def create_name_keyboard(language_code, current_user_info):
    keyboard = []
    row = []
    if not current_user_info['leader_board_name'] or current_user_info['leader_board_name'] == '':
        name = current_user_info['first_name']
        if name != '':
            row.append(InlineKeyboardButton(f"{get_translation(language_code, 'text_use_name')} '{name}'", callback_data=f'name_tg'))
    else:
        name = current_user_info['leader_board_name']
        row.append(InlineKeyboardButton(f"{get_translation(language_code, 'text_use_name')} '{name}'", callback_data=f'name_lastused'))

    row.append(InlineKeyboardButton(get_translation(language_code, 'text_use_other_name'), callback_data=f'name_new'))

    keyboard.append(row)

    keyboard.append([InlineKeyboardButton(get_translation(language_code, 'text_leaderboard_skip'), callback_data=f'leaderboard_skip')])
    return InlineKeyboardMarkup(keyboard)

def create_main_keyboard(language_code):
    keyboard = [
        [InlineKeyboardButton(get_translation(language_code, 'btn_new_game'), callback_data=f'newgame')],
        [InlineKeyboardButton(get_translation(language_code, 'btn_leaderboard'), callback_data=f'leaderboard_show')]
    ]

    return InlineKeyboardMarkup(keyboard)

def create_sea_fight_keyboard(player_board):
    keyboard = []
    y = 0
    for line in player_board:
        row = []
        x = 0
        for sym in line:
            row.append(InlineKeyboardButton(sym, callback_data=f'fire_{x}_{y}'))
            x += 1
        keyboard.append(row)
        y += 1
    return InlineKeyboardMarkup(keyboard)

async def blinking_sea_fight(x, y, board, player_board, context, chat_id, message_id, text):

    ship = []
    button_factory = ButtonFactory()
    keyboard_builder = KeyboardBuilder(button_factory)

    for i in range(ROWS):
        if 0 <= x + i < ROWS:
            if board[x + i][y] == BANG:
                ship.append([x + i, y])
            else:
                break
    for i in range(ROWS):
        if 0 <= x - i < ROWS:
            if board[x - i][y] == BANG:
                ship.append([x - i, y])
            else:
                break
    for i in range(ROWS):
        if 0 <= y + i < ROWS:
            if board[x][y + i] == BANG:
                ship.append([x, y + i])
            else:
                break
    for i in range(ROWS):
        if 0 <= y - i < ROWS:
            if board[x][y - i] == BANG:
                ship.append([x, y - i])
            else:
                break

    for i in range(3):
        for e in ship:
            x, y = e
            player_board.update_cell(x, y, BIGBANG)

        new_kbd = keyboard_builder.create_sea_fight_keyboard(player_board)

        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='HTML', reply_markup=new_kbd)

        for e in ship:
            x, y = e
            player_board.update_cell(x, y, BANG)
        time.sleep(DELAY)

        new_kbd = keyboard_builder.create_sea_fight_keyboard(player_board)

        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='HTML', reply_markup=new_kbd)

        time.sleep(DELAY)

    for e in ship:
        x, y = e
        player_board.update_cell(x, y, BIGBANG)


def main():
    application = Application.builder().token(API_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    print("Start game bot: done.")

    application.run_polling()

if __name__ == '__main__':
    main()



