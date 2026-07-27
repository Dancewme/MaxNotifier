"""Отправка email-уведомлений через SMTP.

Поддерживает автоматическое переподключение при сбоях SMTP.
"""

import smtplib
import ssl
import time
from email.mime.text import MIMEText

from logger import get_logger

SMTP_RECONNECT_DELAY = 5
SMTP_MAX_RECONNECT_DELAY = 60

EMAIL_SUBJECT = "MAX"
EMAIL_BODY = "Проверь MAX, пришло новое сообщение."


class Mailer:
    """Отправка email-уведомлений с защитой от спама."""

    def __init__(
        self,
        host: str,
        port: int,
        login: str,
        password: str,
        email_to: str,
        cooldown_seconds: int,
    ) -> None:
        self._host = host
        self._port = port
        self._login = login
        self._password = password
        self._email_to = email_to
        self._cooldown = cooldown_seconds
        self._last_sent: float = 0.0
        self._logger = get_logger()

    def _is_on_cooldown(self) -> bool:
        """Проверяет, действует ли cooldown с момента последней отправки."""
        if self._last_sent == 0.0:
            return False
        elapsed = time.monotonic() - self._last_sent
        return elapsed < self._cooldown

    def send_notification(self) -> bool:
        """Отправляет email-уведомление, если cooldown прошёл.

        Returns:
            True — письмо отправлено успешно.
            False — отправка пропущена (cooldown) или не удалась.
        """
        if self._is_on_cooldown():
            remaining = self._cooldown - (time.monotonic() - self._last_sent)
            self._logger.info(
                "Cooldown: письмо пропущено, осталось %.0f сек.",
                remaining,
            )
            return False

        msg = MIMEText(EMAIL_BODY, "plain", "utf-8")
        msg["Subject"] = EMAIL_SUBJECT
        msg["From"] = self._login
        msg["To"] = self._email_to

        delay = SMTP_RECONNECT_DELAY
        while True:
            try:
                self._send(msg)
                self._last_sent = time.monotonic()
                self._logger.info(
                    "Письмо отправлено на %s", self._email_to
                )
                return True

            except (smtplib.SMTPException, OSError) as e:
                self._logger.error(
                    "Ошибка отправки email: %s. Повтор через %d сек.",
                    e,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, SMTP_MAX_RECONNECT_DELAY)

    def _send(self, msg: MIMEText) -> None:
        """Подключается к SMTP-серверу и отправляет письмо.

        Использует SSL для порта 465 и STARTTLS для остальных портов.
        """
        if self._port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self._host, self._port, context=context, timeout=30
            ) as server:
                server.login(self._login, self._password)
                server.sendmail(self._login, self._email_to, msg.as_string())
        else:
            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(self._login, self._password)
                server.sendmail(self._login, self._email_to, msg.as_string())
