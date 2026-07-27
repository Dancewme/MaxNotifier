"""Работа с конфигурацией MaxNotifier.

Если config.ini отсутствует рядом с исполняемым файлом —
создаёт его с шаблонными параметрами и завершает работу.
"""

import configparser
import os
import sys

from logger import get_base_dir, get_logger

CONFIG_FILENAME = "config.ini"

REQUIRED_KEYS: list[tuple[str, str]] = [
    ("MAX", "PROCESS_NAME"),
    ("SMTP", "SMTP_HOST"),
    ("SMTP", "SMTP_PORT"),
    ("SMTP", "SMTP_LOGIN"),
    ("SMTP", "SMTP_PASSWORD"),
    ("SMTP", "EMAIL_TO"),
    ("SMTP", "COOLDOWN_SECONDS"),
]

TEMPLATE = """[MAX]
; Имя исполняемого файла десктоп-клиента MAX (например, Max.exe)
PROCESS_NAME=max.exe

; Режим отладки: логирует все новые окна (для поиска нужного)
; true или false
DEBUG=false

[SMTP]
; SMTP-сервер для отправки email-уведомлений
SMTP_HOST=
; Порт SMTP (обычно 465 для SSL или 587 для STARTTLS)
SMTP_PORT=465
; Логин (email отправителя)
SMTP_LOGIN=
; Пароль или app-пароль для SMTP
SMTP_PASSWORD=
; Адрес получателя уведомлений
EMAIL_TO=
; Минимальный интервал между письмами в секундах (защита от спама)
COOLDOWN_SECONDS=60
"""


def get_config_path() -> str:
    """Возвращает абсолютный путь к config.ini рядом с exe/скриптом."""
    return os.path.join(get_base_dir(), CONFIG_FILENAME)


def create_template_config() -> None:
    """Создаёт config.ini с шаблонными параметрами."""
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE)


def load_config() -> configparser.ConfigParser:
    """Загружает config.ini и проверяет обязательные параметры.

    Returns:
        ConfigParser с загруженной конфигурацией.

    Raises:
        SystemExit: если файл отсутствует (после создания шаблона)
                    или обязательные параметры не заполнены.
    """
    logger = get_logger()
    path = get_config_path()

    if not os.path.exists(path):
        create_template_config()
        logger.info("Файл config.ini не найден. Создан шаблон: %s", path)
        print(
            "\nСоздан файл config.ini с параметрами по умолчанию.\n"
            "Заполните все обязательные поля (PROCESS_NAME, SMTP_HOST, "
            "SMTP_PORT, SMTP_LOGIN, SMTP_PASSWORD, EMAIL_TO, "
            "COOLDOWN_SECONDS)\nи запустите программу снова.\n"
            f"Путь: {path}"
        )
        raise SystemExit(0)

    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")

    missing: list[str] = []
    for section, key in REQUIRED_KEYS:
        value = config.get(section, key, fallback="").strip()
        if not value:
            missing.append(f"[{section}] {key}")

    if missing:
        msg = (
            "Не заполнены обязательные параметры в config.ini:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\nЗаполните их и запустите программу снова."
        )
        logger.error(msg)
        print(f"\n{msg}")
        raise SystemExit(1)

    return config