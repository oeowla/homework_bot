import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, types

# Константы сообщений
MISSING_TOKENS_MSG = 'Отсутствуют переменные окружения: {}'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {}'
API_RETURN_ERROR = "API возвращает код {}"
API_RESPONSE_NOT_DICT = "Ответ API должен быть словарем"
HOMEWORKS_FIELD_ERROR = "Отсутствует или некорректно поле homeworks"
CURRENT_DATE_FIELD_ERROR = "Отсутствует поле current_date"
HOMEWORK_STRUCTURE_ERROR = "Некорректная структура домашней работы"
HOMEWORK_NAME_ERROR = 'Отсутствует название домашней работы'
UNKNOWN_STATUS_ERROR = 'Неизвестный статус домашней работы: {}'
PROGRAM_ERROR_MSG = 'Сбой в работе программы: {}'

load_dotenv()

# Константы токенов:
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Константы настроек:
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

# Словарь статусов домашки:
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

ERROR_MESSAGE_TEMPLATE = (
    "Ошибка при запросе к API. URL: {url}, "
    "headers: {headers}, params: {params}. Ошибка: {error}"
)

# Настройки логирования:
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка доступности токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [
        name for name, value in tokens.items()
        if not value
    ]
    if missing_tokens:
        error_message = MISSING_TOKENS_MSG.format(", ".join(missing_tokens))
        raise ValueError(error_message)


def send_message(bot, message):
    """Функция отправки сообщений."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено: %s', message)
    except (types.TelegramError, ConnectionError) as error:
        raise ConnectionError(SEND_MESSAGE_ERROR.format(error))


def get_api_answer(timestamp):
    """Запрос к эндпоинту, возвращает его ответ."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.RequestException as error:
        raise ConnectionError(ERROR_MESSAGE_TEMPLATE.format(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
            error=error
        ))
    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError(
            API_RETURN_ERROR.format(response.status_code)
        )
    try:
        return response.json()
    except ValueError as error:
        raise ValueError(f"Ошибка декодирования JSON: {error}")


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(API_RESPONSE_NOT_DICT)
    if 'homeworks' not in response or not isinstance(
        response['homeworks'], list
    ):
        raise TypeError(HOMEWORKS_FIELD_ERROR)
    if 'current_date' not in response:
        raise KeyError(CURRENT_DATE_FIELD_ERROR)
    if response['homeworks']:
        homework = response['homeworks'][0]
        if 'status' not in homework or (
            'homework_name' not in homework and 'lesson_name' not in homework
        ):
            raise KeyError(HOMEWORK_STRUCTURE_ERROR)


def parse_status(homework):
    """Возвращает сообщение со статусом домашки."""
    homework_name = homework.get('homework_name') or homework.get(
        'lesson_name'
    )
    if not homework_name:
        raise ValueError(HOMEWORK_NAME_ERROR)
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNKNOWN_STATUS_ERROR.format(status))
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except ValueError as error:
        logger.critical(error)
        raise SystemExit(error)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response['homeworks']:
                message = parse_status(response['homeworks'][0])
                send_message(bot, message)
                logger.debug('Отправлено сообщение: %s', message)
            else:
                logger.debug('Нет новых статусов домашних работ')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = PROGRAM_ERROR_MSG.format(error)
            if str(error) != last_error:
                try:
                    send_message(bot, message)
                except Exception:
                    pass
                last_error = str(error)
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    main()
