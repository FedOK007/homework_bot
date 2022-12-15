class AssistantException(Exception):
    """Обработка исключений логики работы ассистента."""


class ApiAnswerException(AssistantException):
    """Обработка исключений вызова api."""


class CheckEnvException(AssertionError):
    """Обработка исключений проверки переменных окружения."""
