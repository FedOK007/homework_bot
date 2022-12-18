class AssistantException(Exception):
    """Обработка исключений логики работы ассистента."""

    pass


class ApiAnswerException(AssistantException):
    """Обработка исключений вызова api."""

    pass


class CheckEnvException(AssertionError):
    """Обработка исключений проверки переменных окружения."""

    pass
