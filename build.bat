@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   MaxNotifier — сборка через PyInstaller
echo ============================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH.
    echo Установите Python 3.12 и добавьте его в PATH.
    pause
    exit /b 1
)

REM Установка зависимостей
echo [1/3] Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости.
    pause
    exit /b 1
)
echo.

REM Сборка через PyInstaller
echo [2/3] Сборка MaxNotifier.exe...
python -m PyInstaller --onefile --name MaxNotifier --console --clean --noconfirm app.py
if errorlevel 1 (
    echo [ОШИБКА] Сборка не удалась.
    pause
    exit /b 1
)
echo.

REM Очистка временных файлов
echo [3/4] Очистка временных файлов...
if exist build rmdir /s /q build
if exist MaxNotifier.spec del /q MaxNotifier.spec
echo.

REM Создание config.ini рядом с exe
echo [4/4] Создание config.ini...
if not exist dist\config.ini (
    > dist\config.ini echo [MAX]
    >> dist\config.ini echo ; Имя исполняемого файла десктоп-клиента MAX (например, Max.exe)
    >> dist\config.ini echo PROCESS_NAME=max.exe
    >> dist\config.ini echo.
    >> dist\config.ini echo ; Режим отладки: логирует все новые окна (для поиска нужного)
    >> dist\config.ini echo ; true или false
    >> dist\config.ini echo DEBUG=false
    >> dist\config.ini echo.
    >> dist\config.ini echo [SMTP]
    >> dist\config.ini echo ; SMTP-сервер для отправки email-уведомлений
    >> dist\config.ini echo SMTP_HOST=
    >> dist\config.ini echo ; Порт SMTP (обычно 465 для SSL или 587 для STARTTLS)
    >> dist\config.ini echo SMTP_PORT=465
    >> dist\config.ini echo ; Логин (email отправителя)
    >> dist\config.ini echo SMTP_LOGIN=
    >> dist\config.ini echo ; Пароль или app-пароль для SMTP
    >> dist\config.ini echo SMTP_PASSWORD=
    >> dist\config.ini echo ; Адрес получателя уведомлений
    >> dist\config.ini echo EMAIL_TO=
    >> dist\config.ini echo ; Минимальный интервал между письмами в секундах (защита от спама)
    >> dist\config.ini echo COOLDOWN_SECONDS=60
    echo config.ini создан в dist\
) else (
    echo config.ini уже существует в dist\ — пропускаю
)
echo.

echo ============================================
echo   Сборка завершена!
echo   Исполняемый файл: dist\MaxNotifier.exe
echo   Конфигурация:     dist\config.ini
echo ============================================
echo.
echo Заполните config.ini (SMTP-настройки) и
echo запустите MaxNotifier.exe.
echo.
pause