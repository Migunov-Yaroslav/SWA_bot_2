# coding=utf-8
import logging
import os
from logging.handlers import RotatingFileHandler

import pygsheets
import telegram
from constants import (AMOUNT_COL, HELP_MESSAGE, INSTR_COL, MAT_NO_COL,
                       MAX_SYMBOLS, NAME_COL, PLACE_COL, REMARK_COL,
                       START_MESSAGE, TITLES)
from dotenv import load_dotenv
from exceptions import (AccessError, NothingFoundError, PasswordError,
                        PasswordOkError, ToLongResultError)
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
BOT_PASSWORD = os.getenv('BOT_PASSWORD')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME')

logged_users: list = []

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'SWAbot.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
handler.setFormatter(formatter)


def send_message_and_log(update, context, text):
    """
    Отправить сообщение в Telegram.

    Попытаться отправить в сообщение в Telegram с информацией о найденных
    запчастях и добавить запись в лог, если не получится добавить запись в
    лог о сбое.

    :param update: Updater
    :param context: Dispatcher.context
    :param text: str
    :return: None
    """
    try:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
        )
    except telegram.error.TelegramError as error:
        logger.error(f'Сбой доставки сообщения: {error}')
    else:
        logger.info(
            'Сообщение отправлено в чат '
            f'{update.effective_chat.id}'
        )


def check_password(update, context):
    """
    Проверить пароль пользователя.

    Если ID пользователя отсутствует в перечне, проверить сообщение
    пользователя на наличие корректного пароля.

    :param update: Updater
    :param context: Dispatcher.context
    :return: bool
    """
    if (
        update.effective_chat.id not in logged_users
        and update.message.text != BOT_PASSWORD
    ):
        send_message_and_log(
            update=update, context=context, text='Введите пароль',
        )
        logger.info(
            f'Кто-то не может ввести пароль. ID:{update.effective_chat.id}'
        )

        raise PasswordError('Введен неверный пароль')

    if update.message.text == BOT_PASSWORD:
        send_message_and_log(
            update=update,
            context=context,
            text='Пароль принят. Чтобы прочитать какие команды понимает '
                 'бот отправьте команду /help.',
        )
        logged_users.append(update.effective_chat.id)

        raise PasswordOkError('Введен верный пароль')

    return True


def find_spare_part_rows(sheet, lookup_str):
    """
    Найти номера строк таблицы, в которых находится информация об искомых з/ч.

    Перебрать все строки каждого из вложенных списков, проверить вхождение в
    них строки шаблона при помощи встроенной функции строк find() и вернуть
    номера вложенных списков.

    :param sheet: List(List(str)) - содержимое рабочего листа Google таблицы в
    виде списка из вложенных списков; номер n вложенного списка - это
    номер n+1 соответствующей строки в рабочем листе; номер n вложенного
    списка - это номер n+1 столбца в рабочем листе;
    :param lookup_str: str - искомая строка;
    :return: List(int) - список номеров списков в исходном списке sheet_list,
    которые содержат искомую строку.
    """
    lookup_rows = []
    for row_index in range(0, len(sheet)):
        for col_index in range(0, len(sheet[0])):
            if (
                    sheet[row_index][col_index].lower().find(
                        lookup_str.lower()
                    ) != -1 and (row_index not in lookup_rows)
            ):
                lookup_rows.append(row_index)

    return lookup_rows


def find_spare_part_place(sheet, row_num):
    """
    Найти места хранения искомых запчастей.

    Перебрать для каждого номера списка n, полученного от функции
    find_spare_part_rows(), каждую строку вложенных списков, начиная с
    n-1 до нуля. Если в строке содержится слово 'шкаф', то номер в начале
    этой строки - номер шкафа. Если до обнаружения ключевого слова 'шкаф'
    обнаруживается ключевое слово 'полка', то к месту хранения запчасти
    добавить указание полки. Сравнение строк производить с помощью
    встроенной функции строк find(). Вернуть строку с указанием места
    хранения искомых запчастей.

    :param sheet: sheet: List(List(str)) - содержимое рабочего листа Google
    таблицы в виде списка из вложенных списков; номер n вложенного списка - это
    номер n+1 соответствующей строки в рабочем листе; номер n вложенного
    списка - это номер n+1 столбца в рабочем листе;
    :param row_num: List(int) - список с номерами вложенных списков,
    в которых содержится информация об искомых запчастях;
    :return: str
    """
    spare_part_place = {'Шкаф': '', 'Полка': ''}

    for row_index in range(row_num, -1, -1):
        cell = sheet[row_index][0]
        if (
            cell.lower().find('шкаф') != -1 and not spare_part_place['Шкаф']
        ):
            cabinet_numb = cell.split(' ')
            spare_part_place['Шкаф'] = (
                cabinet_numb[0].rstrip(' ') + ' шкаф' + ', '
            )

        if cell.lower().find('major') != -1:
            spare_part_place['Шкаф'] = cell

        if (
            cell.lower().find('полка') != -1 and not spare_part_place['Полка']
            and not spare_part_place['Шкаф']
        ):
            spare_part_place['Полка'] = cell

    return spare_part_place['Шкаф'] + spare_part_place['Полка'].lower()


def format_message(results):
    """
    Форматировать сообщение.

    Форматировать сообщение с информацией об искомых запчастях, отправляемое
    пользователю: превратить список строк в одну строку

    :param results: List(str) - список строк с информацией об искомых
    запчастях;
    :return: str.
    """
    message = ''

    for elem in results:
        for key, value in tuple(elem.items()):
            message = message + key + ': ' + value + '\n'
        message = message + '\n\n'

    return message


def search_spare_parts(update, context):
    """
    Найти запчасть

    Основная функция телеграм-бота, которая проверят доступ пользователя,
    ищет в Google таблице информацию о запчастях и отправляет пользователю
    сообщения.
    Создать переменную sheet_list при помощи метода Worksheet.get_values().
    Метод возвращает содержимое Google таблицы в виде списка списков,
    содержащих строки, каждая из которых содержит значение одной ячейки
    исходной таблицы. Проверить пароль пользователя. Найти информацию о
    запчастях.

    Алгоритм поиска информации о запчастях.
    Для каждого числа n в списке, возвращаемого функцией
    find_spare_part_rows(), создать словарь, в котором ключи - название
    параметров запчасти, значения - строки в определенной позиции
    вложенного списка n.
    Отправить сообщение пользователю.

    :param update: Updater
    :param context: Dispatcher.context
    :return: None
    """
    check_password(update, context)

    # Авторизация в Google API
    try:
        client = pygsheets.authorize(
            service_file='swa-bot.json',
        )
    except Exception as error:
        logger.error(f'Ошибка авторизации в Google API: {error}')
        send_message_and_log(
            update,
            context,
            text='Ошибка авторизации в Google API: не удается получить '
                 f'доступ к таблице с базой запчастей. Ошибка: {error}'
        )
        raise AccessError(f'Ошибка авторизации в Google API: {error}')

    print(client.spreadsheet_titles())

    # Открытие таблицы
    try:
        spreadsheet = client.open(title=SPREADSHEET_NAME)
    except Exception as error:
        logger.error(f'Ошибка открытия файла {SPREADSHEET_NAME}: {error}')
        send_message_and_log(
            update,
            context,
            text='Не удается открыть файл с базой данных запчастей'
                 f' {SPREADSHEET_NAME}. Ошибка: {error}'
        )
        raise AccessError(f'Ошибка открытия файла {SPREADSHEET_NAME}: {error}')

    # Открытие рабочего листа
    try:
        w_sheet = spreadsheet.sheet1
    except Exception as error:
        logger.error(
            f'Ошибка открытия рабочего листа {error}'
        )
        send_message_and_log(
            update,
            context,
            text='Не удается открыть рабочий лист с базой данных запчастей. '
                 f'Ошибка: {error}'
        )
        raise AccessError(
            f'Ошибка открытия рабочего листа: {error}'
        )

    # Выгрузка данных с рабочего листа в виде списка списков строк
    try:
        sheet_list = w_sheet.get_values(
            start='A1',
            end='F' + str(w_sheet.rows)
        )
    except Exception as error:
        logger.error(
            'Ошибка при выгрузке данных с рабочего листа методом '
            f'get_values: {error}'
        )
        send_message_and_log(
            update,
            context,
            text='Не удается получить данные с рабочего листа. Ошибка: '
                 f'{error}'
        )
        raise AccessError(
            'Ошибка при выгрузке данных с рабочего листа методом '
            f'get_values: {error}'
        )

    lookup_str = update.message.text
    results = []
    rows_list = find_spare_part_rows(sheet=sheet_list, lookup_str=lookup_str)

    if not rows_list:
        send_message_and_log(
            update,
            context,
            text='По вашему запросу ничего не найдено'
        )
        raise NothingFoundError('По запросу ничего не найдено')

    for row_index in rows_list:
        results.append(
            {
                TITLES[NAME_COL]: sheet_list[row_index][NAME_COL],
                TITLES[MAT_NO_COL]: sheet_list[row_index][MAT_NO_COL],
                TITLES[AMOUNT_COL]: sheet_list[row_index][AMOUNT_COL],
                TITLES[INSTR_COL]: sheet_list[row_index][INSTR_COL],
                TITLES[REMARK_COL]: sheet_list[row_index][REMARK_COL],
                TITLES[PLACE_COL]: find_spare_part_place(sheet_list, row_index)
            }
        )

    # цикл для удаления словарей, где значения всех ключей - пустые строки и
    # замены в остальных словарях пустых строк на '-'
    for elem in results:
        elem_dict = {
            key: value for (key, value) in elem.items() if value
        }
        elem_dict.pop(TITLES[PLACE_COL])

        if not elem_dict:
            results.remove(elem)

        for key, value in tuple(elem.items()):
            if not value:
                elem[key] = '-'

    if len(format_message(results)) > MAX_SYMBOLS:
        send_message_and_log(
            update,
            context,
            text='Найдено слишком много данных, попробуйте уточнить поисковый '
                 'запрос.'
        )
        raise ToLongResultError('Найдено слишком много данных')

    send_message_and_log(
        update=update,
        context=context,
        text=format_message(results),
    )


def show_help(update, context):
    check_password(update, context)
    send_message_and_log(
        update=update,
        context=context,
        text=HELP_MESSAGE,
    )


def start(update, context):
    send_message_and_log(
        update=update,
        context=context,
        text=START_MESSAGE,
    )


def main():
    updater = Updater(token=BOT_TOKEN)
    updater.dispatcher.add_handler(
        CommandHandler('help', show_help)
    )
    updater.dispatcher.add_handler(
        CommandHandler('start', start)
    )
    updater.dispatcher.add_handler(
        MessageHandler(Filters.text, search_spare_parts)
    )

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
