import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] '
    '%(message)s (%(filename)s, %(lineno)d, %(name)s)'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class AssistantException(Exception):
    """Обработка исключений логики работы ассистента."""

    def __init__(self, message):
        """Инициализация объекта."""
        self.message = message
        super().__init__(self.message)


class ApiAnswerException(AssistantException):
    """Обработка исключений вызова api."""

    def __init__(self, message):
        """Инициализация объекта."""
        self.message = message
        super().__init__(self.message)


def check_tokens():
    """Проверка наличия всех необходимых переменных."""
    required_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    error_str = ', '.join(
        [k for k, v in required_variables.items() if v is None]
    )
    if error_str:
        logger.critical(
            f'Отсутствует обязательная переменная окружения: {error_str}. '
            'Программа принудительно остановлена. ', extra={'send_telegram': 1}
        )
        sys.exit(0)


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug(f'Бот отправил сообщение "{message}"')
    except Exception as err:
        logger.error(f'Ошибка отправки сообщения в Telegram: {err}')


def get_api_answer(timestamp):
    """Вызов api проверки домашнего задания."""
    try:
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code == 200:
            return response.json()
        else:
            msg = (
                f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
                'Код ответа API: {response.status_code}'
            )
            raise ApiAnswerException(msg)
    except Exception as err:
        msg = f'Ошибка при вызове Эндпоинта {ENDPOINT}: {err}'
        raise ApiAnswerException(msg)


def check_response(response):
    """Проверка наличия в ответе необходимых полей."""
    if not isinstance(response, dict):
        msg = f'В ответе пришли данные не в виде словаря: {response}'
        raise TypeError(msg)
    elif (
        response.get('homeworks') is None
        or response.get('current_date') is None
    ):
        msg = f'Отсутствуют ожидаемые ключи в ответе API: {response}'
        raise TypeError(msg)
    elif type(response['homeworks']) != list:
        print(type(response['homeworks']))
        msg = f'В ответе поле homeworks не является списком: {response}'
        raise TypeError(msg)
    elif len(response['homeworks']) == 0:
        logger.debug('Нет обновления статусов в ответе API')
        return False
    elif not isinstance(response['homeworks'][0], dict):
        msg = (
            'Список homeworks не содержит словарь: '
            f'{response["homeworks"][0]}'
        )
        raise TypeError(msg)
    elif (
        response['homeworks'][0].get('homework_name') is None
        or response['homeworks'][0].get('status') is None
    ):
        msg = f'Отсутствуют ожидаемые ключи в ответе API: {response}'
        raise TypeError(msg)
    return True


def parse_status(homework):
    """Проверка статуса проверки домашнего задания."""
    verdict = HOMEWORK_VERDICTS.get(homework['status'])
    if not homework.get('homework_name'):
        msg = f'Отсутствуют ожидаемые ключи в ответе API: {homework}'
        raise AssistantException(msg)
    if verdict is None:
        msg = (
            'Неожиданный статус домашней работы, '
            f'обнаруженный в ответе API, status: {homework["status"]}'
        )
        raise AssistantException(msg)
    return (
        f'Изменился статус проверки работы "{homework["homework_name"]}"'
        f'. {verdict}'
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    SEND_ERROR_API_MSG = True

    while True:
        try:
            api_response = get_api_answer(timestamp)
            # block for testing #
            #
            # api_response = {
            #     'current_date': 111,
            #     'homeworks': [
            #         {
            #             'homework_name': 'test1',
            #             'status': 'rejected',
            #         }
            #     ]
            # }
            if api_response:
                SEND_ERROR_API_MSG = True
                check = check_response(api_response)
                if check:
                    status = parse_status(api_response['homeworks'][0])
                    if status:
                        send_message(bot, status)
                    timestamp = api_response.get('current_date')

        except ApiAnswerException as error:
            msg = f'Сбой в работе программы: {error}'
            logger.error(msg)
            if SEND_ERROR_API_MSG:
                send_message(bot, api_response)
                SEND_ERROR_API_MSG = False
        except Exception as error:
            msg = f'Сбой в работе программы: {error}'
            logger.error(msg)
            send_message(bot, msg)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
