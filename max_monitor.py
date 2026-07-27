"""Мониторинг окон уведомлений MAX через Win32 Event Hook.

Отслеживает появление новых окон от процесса десктоп-клиента MAX и
вызывает callback при обнаружении окна уведомления о новом сообщении.

Использует SetWinEventHook для отслеживания событий окон в реальном времени.
Работает только на Windows.
"""

import ctypes
import time
from ctypes import WINFUNCTYPE, wintypes
from typing import Callable

from logger import get_logger

# --- Win32 bindings ---

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Константы Win32
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
OBJID_WINDOW = 0
PM_REMOVE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Типы callback-функций Win32
WinEventProcType = WINFUNCTYPE(
    None,
    wintypes.HANDLE,   # hWinEventHook
    wintypes.DWORD,    # event
    wintypes.HWND,     # hwnd
    wintypes.LONG,     # idObject
    wintypes.LONG,     # idChild
    wintypes.DWORD,    # dwEventThread
    wintypes.DWORD,    # dwmsEventTime
)

WndEnumProcType = WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM,
)

# Настройка сигнатур Win32 функций (важно для 64-битной корректности)
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.SetWinEventHook.argtypes = [
    wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
    WinEventProcType, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
]

user32.UnhookWinEvent.restype = wintypes.BOOL
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]

user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
]

user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [WndEnumProcType, wintypes.LPARAM]

user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]

user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]

user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]

user32.GetWindowLongW.restype = wintypes.LONG
user32.GetWindowLongW.argtypes = [wintypes.HWND, wintypes.INT]

user32.GetWindowTextW.restype = wintypes.INT
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]

user32.GetClassNameW.restype = wintypes.INT
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, wintypes.INT]

user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND,
    wintypes.UINT, wintypes.UINT, wintypes.UINT,
]

user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD,
    wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


# --- Константы мониторинга ---

RECONNECT_DELAY = 5
MESSAGE_PUMP_INTERVAL = 0.1
CLEANUP_INTERVAL = 60

# Константы стилей окон
GWL_STYLE = -16
WS_CHILD = 0x40000000

# Классы Qt, которые не являются окнами уведомлений
IGNORED_CLASS_PREFIXES = ("QEventDispatcherWin32",)

# Дедупликация SHOW-событий: окно может показываться повторно
SHOW_DEDUP_SECONDS = 5


class MaxMonitor:
    """Мониторинг окон уведомлений MAX через Win32 Event Hook.

    Отслеживает создание и показ окон от процесса MAX.
    При обнаружении нового окна (отличного от главного) вызывает callback,
    который отправляет email-уведомление.
    """

    def __init__(self, process_name: str, debug: bool = False) -> None:
        self._process_name = process_name.lower()
        self._debug = debug
        self._logger = get_logger()
        self._on_notification: Callable[[], None] | None = None
        self._hook: int | None = None
        self._callback: WinEventProcType | None = None
        self._main_window: int | None = None
        self._max_pid: int | None = None
        self._notified_windows: set[int] = set()
        self._last_show_time: dict[int, float] = {}

    def _get_process_path(self, pid: int) -> str:
        """Возвращает путь к exe-файлу процесса по его PID."""
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(
                handle, 0, buf, ctypes.byref(size)
            ):
                return buf.value
            return ""
        finally:
            kernel32.CloseHandle(handle)

    def _is_max_process(self, pid: int) -> bool:
        """Проверяет, принадлежит ли PID процессу MAX."""
        exe_path = self._get_process_path(pid)
        return self._process_name in exe_path.lower()

    def _get_window_pid(self, hwnd: int) -> int:
        """Возвращает PID процесса-владельца окна."""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _get_class_name(self, hwnd: int) -> str:
        """Возвращает имя класса окна."""
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def _get_window_title(self, hwnd: int) -> str:
        """Возвращает заголовок окна."""
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def _is_ignored_class(self, class_name: str) -> bool:
        """Проверяет, относится ли класс к игнорируемым (Qt-мусор)."""
        return any(
            class_name.startswith(prefix)
            for prefix in IGNORED_CLASS_PREFIXES
        )

    def _find_main_window(self) -> tuple[int, int] | None:
        """Находит главное окно MAX.

        Возвращает кортеж (hwnd, pid) или None.
        Главное окно — первое видимое top-level окно процесса MAX.
        """
        result: list[tuple[int, int] | None] = [None]

        def enum_callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetParent(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if self._is_max_process(pid.value):
                result[0] = (hwnd, pid.value)
                return False
            return True

        user32.EnumWindows(WndEnumProcType(enum_callback), 0)
        return result[0]

    def _win_event_callback(
        self,
        hWinEventHook: int,
        event: int,
        hwnd: int,
        idObject: int,
        idChild: int,
        dwEventThread: int,
        dwmsEventTime: int,
    ) -> None:
        """Callback для SetWinEventHook — вызывается при событиях окон."""
        if idObject != OBJID_WINDOW:
            return
        if not hwnd:
            return
        if self._main_window and hwnd == self._main_window:
            return

        # Проверяем, что окно принадлежит процессу MAX
        pid = self._get_window_pid(hwnd)
        if not self._is_max_process(pid):
            return

        # Получаем класс и фильтруем Qt-мусор
        class_name = self._get_class_name(hwnd)
        if self._is_ignored_class(class_name):
            return

        # Пропускаем дочерние элементы интерфейса
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        if style & WS_CHILD:
            return

        if self._debug:
            title = self._get_window_title(hwnd)
            event_name = (
                "CREATE" if event == EVENT_OBJECT_CREATE
                else "SHOW" if event == EVENT_OBJECT_SHOW
                else f"EVENT_{event:#x}"
            )
            self._logger.info(
                "[DEBUG] %s: hwnd=%d, title='%s', class='%s'",
                event_name, hwnd, title, class_name,
            )

        if event == EVENT_OBJECT_CREATE:
            # Новое окно — дедупликация по hwnd
            if hwnd in self._notified_windows:
                return
            self._notified_windows.add(hwnd)
        elif event == EVENT_OBJECT_SHOW:
            # Показ скрытого окна — дедупликация по времени
            now = time.monotonic()
            last = self._last_show_time.get(hwnd, 0.0)
            if now - last < SHOW_DEDUP_SECONDS:
                return
            self._last_show_time[hwnd] = now
        else:
            return

        self._logger.info(
            "Обнаружено окно уведомления MAX (hwnd=%d, class='%s')",
            hwnd, class_name,
        )

        if self._on_notification:
            self._on_notification()

    def _setup_hook(self) -> bool:
        """Устанавливает SetWinEventHook для процесса MAX."""
        self._callback = WinEventProcType(self._win_event_callback)
        self._hook = user32.SetWinEventHook(
            EVENT_OBJECT_CREATE,
            EVENT_OBJECT_SHOW,
            0,
            self._callback,
            self._max_pid,
            0,
            WINEVENT_OUTOFCONTEXT,
        )
        if not self._hook:
            self._logger.error("Не удалось установить SetWinEventHook")
            return False
        return True

    def _teardown_hook(self) -> None:
        """Снимает SetWinEventHook."""
        if self._hook:
            user32.UnhookWinEvent(self._hook)
            self._hook = None
        self._callback = None

    def start(self, on_notification: Callable[[], None]) -> None:
        """Запускает мониторинг окон MAX.

        Блокирует выполнение, обрабатывая Win32 сообщения.
        Автоматически переходит в режим ожидания при закрытии MAX
        и возобновляет мониторинг при повторном запуске.
        Завершается по KeyboardInterrupt (Ctrl+C).
        """
        self._on_notification = on_notification

        try:
            while True:
                # Поиск главного окна MAX
                if self._main_window is None:
                    self._logger.info("Поиск главного окна MAX...")
                    found = self._find_main_window()
                    if found is None:
                        self._logger.warning(
                            "Окно MAX не найдено. Повтор через %d сек.",
                            RECONNECT_DELAY,
                        )
                        time.sleep(RECONNECT_DELAY)
                        continue

                    self._main_window, self._max_pid = found
                    self._logger.info(
                        "Главное окно MAX найдено (hwnd=%d, pid=%d)",
                        self._main_window, self._max_pid,
                    )

                    if not self._setup_hook():
                        time.sleep(RECONNECT_DELAY)
                        continue

                    self._logger.info("Мониторинг окон уведомлений MAX запущен")

                # Message pump
                msg = wintypes.MSG()
                last_cleanup = time.monotonic()

                while True:
                    # Обработка сообщений Win32
                    while user32.PeekMessageW(
                        ctypes.byref(msg), None, 0, 0, PM_REMOVE
                    ):
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))

                    # Проверка, что MAX всё ещё жив
                    if not user32.IsWindow(self._main_window):
                        self._logger.warning(
                            "Окно MAX закрыто. Повторный поиск..."
                        )
                        self._teardown_hook()
                        self._main_window = None
                        self._max_pid = None
                        self._notified_windows.clear()
                        self._last_show_time.clear()
                        break

                    # Периодическая очистка мёртвых hwnd
                    if time.monotonic() - last_cleanup > CLEANUP_INTERVAL:
                        self._notified_windows = {
                            w for w in self._notified_windows
                            if user32.IsWindow(w)
                        }
                        self._last_show_time = {
                            w: t for w, t in self._last_show_time.items()
                            if user32.IsWindow(w)
                        }
                        last_cleanup = time.monotonic()

                    time.sleep(MESSAGE_PUMP_INTERVAL)

        except KeyboardInterrupt:
            pass

        self._teardown_hook()
        self._logger.info("Мониторинг остановлен")