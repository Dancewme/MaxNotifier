"""Точка входа MaxNotifier.

Программа отслеживает появление новых окон уведомлений десктоп-клиента MAX
через Win32 Event Hook и отправляет email-уведомление.
"""

from config import load_config
from logger import get_logger
from mailer import Mailer
from max_monitor import MaxMonitor


def main() -> None:
    logger = get_logger()
    logger.info("=== MaxNotifier запущен ===")

    config = load_config()

    process_name = config.get("MAX", "PROCESS_NAME").strip()
    debug = config.getboolean("MAX", "DEBUG", fallback=False)

    smtp_host = config.get("SMTP", "SMTP_HOST").strip()
    smtp_port = config.getint("SMTP", "SMTP_PORT")
    smtp_login = config.get("SMTP", "SMTP_LOGIN").strip()
    smtp_password = config.get("SMTP", "SMTP_PASSWORD").strip()
    email_to = config.get("SMTP", "EMAIL_TO").strip()
    cooldown = config.getint("SMTP", "COOLDOWN_SECONDS")

    mailer = Mailer(
        host=smtp_host,
        port=smtp_port,
        login=smtp_login,
        password=smtp_password,
        email_to=email_to,
        cooldown_seconds=cooldown,
    )

    logger.info("Мониторинг: процесс MAX — %s", process_name)
    logger.info(
        "SMTP: %s:%d, получатель: %s, cooldown: %d сек.",
        smtp_host,
        smtp_port,
        email_to,
        cooldown,
    )

    monitor = MaxMonitor(process_name=process_name, debug=debug)
    monitor.start(on_notification=mailer.send_notification)

    logger.info("=== MaxNotifier остановлен ===")


if __name__ == "__main__":
    main()