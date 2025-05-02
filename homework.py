import logging
import os
import time
import requests
from dotenv import load_dotenv
from telebot import TeleBot
from exceptions import (
    MissingTokenError,
    APIRequestError,
    ParseStatusError,
    SendMessageError
)

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

# Настройки логирования:
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
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
        logger.critical(
            'Отсутствуют обязательные переменные окружения: %s',
            ', '.join(missing_tokens)
        )
        raise MissingTokenError(
            f'Отсутствуют переменные окружения: {", ".join(missing_tokens)}'
        )


def send_message(bot, message):
    """Функция отправки сообщений."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено: %s', message)
    except Exception as error:
        logger.error('Ошибка при отправке сообщения: %s', error)
        raise SendMessageError(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту, возвращает его ответ."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if homework_statuses.status_code != 200:
            raise APIRequestError(
                f"API возвращает код {homework_statuses.status_code}"
            )
        return homework_statuses.json()
    except requests.RequestException as error:
        raise APIRequestError(f"Ошибка при запросе к API: {error}")


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API должен быть словарем")
    if 'homeworks' not in response or not isinstance(
        response['homeworks'], list
    ):
        raise TypeError("Отсутствует или некорректно поле homeworks")
    if 'current_date' not in response:
        raise KeyError("Отсутствует поле current_date")
    if response['homeworks']:
        homework = response['homeworks'][0]
        if 'status' not in homework or (
            'homework_name' not in homework and 'lesson_name' not in homework
        ):
            raise KeyError("Некорректная структура домашней работы")


def parse_status(homework):
    """Возвращает сообщение со статусом домашки."""
    homework_name = homework.get('homework_name') or homework.get(
        'lesson_name'
    )
    if not homework_name:
        raise ParseStatusError(
            'Отсутствует ключ homework_name или lesson_name'
        )
    homework_status = homework.get('status')
    if not homework_status:
        raise ParseStatusError('Отсутствует ключ status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ParseStatusError(
            f'Неизвестный статус домашней работы: {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except MissingTokenError as error:
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
            message = f'Сбой в работе программы: {error}'
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
    main()
