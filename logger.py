"""Настройка логирования MaxNotifier.

Лог-файл log.txt создаётся рядом с исполняемым файлом
(или скриптом при запуске из исходников).
"""

import logging
import os
import sys

_logger: logging.Logger | None = None


def get_base_dir() -> str:
    """Возвращает каталог рядом с exe (PyInstaller) или скриптом."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_logger() -> logging.Logger:
    """Инициализирует логгер с выводом в файл и консоль."""
    global _logger
    if _logger is not None:
        return _logger

    log_path = os.path.join(get_base_dir(), "log.txt")

    logger = logging.getLogger("MaxNotifier")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Возвращает текущий логгер (создаёт при первом вызове)."""
    if _logger is None:
        return setup_logger()
    return _logger
