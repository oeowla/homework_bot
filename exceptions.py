class MissingTokenError(Exception):
    """Исключение при отсутствии обязательных переменных окружения."""


class APIRequestError(Exception):
    """Исключение при ошибке запроса к API."""


class ParseStatusError(Exception):
    """Исключение при невозможности разобрать статус домашней работы."""


class SendMessageError(Exception):
    """Исключение при ошибке отправки сообщения в Telegram."""
