import logging
import os
import sys
import time
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

from exceptions import CheckEnvException
from exceptions import ApiAnswerException
from exceptions import AssistantException


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


def check_tokens():
    """Проверка наличия всех необходимых переменных."""
    required_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    variables_none = [k for k, v in required_variables.items() if v is None]
    if len(variables_none) > 0:
        error_str = ', '.join(variables_none)
        msg = (
            f'Отсутствует обязательная переменная окружения: {error_str}. '
            'Программа принудительно остановлена.'
        )
        raise CheckEnvException(msg)
    return True


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
        msg = (
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
            'Код ответа API: {response.status_code}'
        )
        raise ApiAnswerException(msg)
    except JSONDecodeError as err:
        msg = (
            'Ошибка конвертирования в json ответа от '
            f'Эндпоинта {ENDPOINT}: {err}'
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
    homeworks = response.get('homeworks')
    current_date = response.get('current_date')
    if homeworks is None or current_date is None:
        msg = f'Отсутствуют ожидаемые ключи в ответе API: {response}'
        raise TypeError(msg)
    if type(homeworks) != list:
        msg = f'В ответе поле homeworks не является списком: {response}'
        raise TypeError(msg)
    if len(homeworks) == 0:
        logger.debug('Нет обновления статусов в ответе API')
        return False
    return True


def parse_status(homework):
    """Проверка статуса проверки домашнего задания."""
    if not isinstance(homework, dict):
        msg = f'Переменная homework не содержит словарь: {homework}'
        raise TypeError(msg)
    if homework.get('homework_name') is None or homework.get('status') is None:
        msg = (
            'Отсутствуют ожидаемые ключи (homework_name, status) '
            f'в словаре homework: {homework}'
        )
        raise AssistantException(msg)

    verdict = HOMEWORK_VERDICTS.get(homework['status'])
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
    try:
        check_tokens()
    except CheckEnvException as error:
        msg = f'Сбой в работе программы: {error}'
        logger.critical(msg)
        sys.exit(0)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_error_api_msg = True
    while True:
        try:
            api_response = get_api_answer(timestamp)
            send_error_api_msg = True
            if check_response(api_response):
                status = parse_status(api_response['homeworks'][0])
                if status:
                    send_message(bot, status)
                timestamp = api_response['current_date']

        except ApiAnswerException as error:
            msg = f'Сбой в работе программы: {error}'
            logger.error(msg)
            if send_error_api_msg:
                send_message(bot, api_response)
                send_error_api_msg = False
        except Exception as error:
            msg = f'Сбой в работе программы: {error}'
            logger.error(msg)
            send_message(bot, msg)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
