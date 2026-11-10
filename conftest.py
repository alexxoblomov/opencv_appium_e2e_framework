"""
conftest.py — инфраструктура запуска мобильных e2e-тестов (Appium + Pytest)

Состав и назначение:
- Логирование: единая настройка логов и подавление лишнего шума от внешних библиотек.
- Аргументы CLI: --device, интерактивный выбор устройства (локально).
- Драйвер: инициализация Appium WebDriver с UiAutomator2/XCUITest.
- Маппинг координат: автоподстановка маппера для стабильных тапов под текущее разрешение.
- Визуальные ожидания: ожидания из open_cv вместо time.sleep.
- Фикстуры входа: пример пути до экрана логина и до лобби.

Правила:
- Избегать time.sleep в сценарных фикстурах; использовать wait_for_template / wait_until_not_template / tap_and_wait_for_template.
- Любое действие, меняющее экран, должно завершаться проверкой (появление или исчезновение шаблона).
- Короткий sleep уместен только там, где переключатель не меняет шаблон экрана.
"""

import logging
import sys
import threading
import time

import allure
import pytest
import questionary
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver import Remote

from buttons import Button, DeviceButtons
from devices import DEVICES
from open_cv import tap_and_wait_for_template, wait_for_template
from templates.templates import GameTemplates
from utils import _normalize_epoch_ms, map_point

# =========================
# ЛОГИРОВАНИЕ И СТАРТ/ФИНИШ
# =========================

logging.basicConfig(
    level=logging.DEBUG,
    format=' %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log", mode='w'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True,
)

logging.getLogger('appium').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def log_test_start_end(request):
    """
    Авто-фикстура: логирует старт и завершение каждого теста.

    Args:
        request: Pytest request с метаданными текущего теста.
    """
    test_name = request.node.name
    logger.info(f"starting test: {test_name}")

    yield
    logger.info(f"finished test: {test_name}")


# =========================
# ОТЛОВ КЛИЕНТСКИХ ОШИБОК
# =========================

@pytest.fixture(autouse=True)
def guard_client_exceptions(request, appium_driver):
    if not request.config.getoption("--check-logs", default=False):
        yield
        return

    logger = logging.getLogger("NRE")
    start_ms = int(time.time() * 1000)

    stop_event = threading.Event()
    seen = set()
    nre_entries = []

    platform = str(getattr(appium_driver, "capabilities", {}).get("platformName", "Android")).lower()
    log_type = "logcat" if platform == "android" else "syslog"

    def _loop():
        last_cutoff_ms = start_ms
        while not stop_event.is_set():
            try:
                entries = appium_driver.get_log(log_type) or []
            except Exception:
                if stop_event.wait(1.0):
                    break
                continue

            for e in entries:
                ts_ms = _normalize_epoch_ms(e.get("timestamp"))
                if ts_ms is not None and ts_ms < last_cutoff_ms:
                    continue

                msg = (e.get("message") or "")
                msg_l = msg.lower()

                if ("nullreferenceexception" not in msg_l) and (
                        "object reference not set to an instance of an object" not in msg_l):
                    continue

                key = f"{ts_ms}|{msg}"
                if key in seen:
                    continue
                seen.add(key)
                nre_entries.append(e)

                level = e.get("level", "ERROR")
                logger.error(f"NRE detected [{level}] {ts_ms}: {msg}")

                try:
                    ts_name = time.strftime("%Y%m%d_%H%M%S")
                    test_name = request.node.name

                    png_bytes = appium_driver.get_screenshot_as_png()
                    allure.attach(
                        png_bytes,
                        name=f"nre_{ts_name}_{test_name}.png",
                        attachment_type=allure.attachment_type.PNG,
                    )
                except Exception as se:
                    logger.warning("Unable to attach screenshot: %s", se, exc_info=True)
                    allure.attach(str(se), name="nre_screenshot_error", attachment_type=allure.attachment_type.TEXT)

            last_cutoff_ms = int(time.time() * 1000)
            if stop_event.wait(1.0):
                break

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    yield

    if hasattr(request.node, "rep_call") and not getattr(request.node, "rep_call").passed:
        stop_event.set()
        t.join(timeout=3)
        return

    stop_event.set()
    t.join(timeout=3)

    if nre_entries:
        text = "\n".join(f"[{e.get('level')}] {e.get('timestamp')}: {e.get('message')}" for e in nre_entries)
        allure.attach(text, name="client_nre_excerpt (non-fatal)", attachment_type=allure.attachment_type.TEXT)
        logger.warning("NullReferenceException is found: %d (see attachment client_nre_excerpt)", len(nre_entries))

        try:
            request.node.user_properties.append(("client_nre_count", len(nre_entries)))
        except Exception:
            pass


# =========================
# МАППЕР ЭКРАНА (КОМПАТ)
# =========================

def _get_base_resolution(device_key: str):
    cfg = DEVICES.get(device_key, {})
    base_w = cfg.get("base_w")
    base_h = cfg.get("base_h")

    if not base_w or not base_h:
        base_w, base_h = 2712, 1220
    return base_w, base_h


@pytest.fixture(autouse=True)
def enable_screen_mapper(request):
    """
    Перехватывает Button.tap и маппит координаты под текущее разрешение экрана.

    Args:
        request: Pytest request, используется для чтения --device.

    Поведение:
        - Вычисляет базовое разрешение по DEVICES[--device]
        - Подменяет Button.tap на версию с map_point(...)
        - После выполнения теста возвращает исходную реализацию
    """
    device_key = request.config.getoption("--device")
    base_w, base_h = _get_base_resolution(device_key)

    original_tap = Button.tap

    def mapped_tap(self: Button, driver):
        size = driver.get_window_size()
        cur_w, cur_h = size["width"], size["height"]
        tx, ty = map_point(self.x, self.y, base_w, base_h, cur_w, cur_h)
        return driver.tap([(tx, ty)])

    Button.tap = mapped_tap
    try:
        yield
    finally:
        Button.tap = original_tap


# =========================
# PYTEST ОПЦИИ И КОНФИГ
# =========================

def pytest_addoption(parser):
    """
    Регистрирует CLI-опции запуска тестов:

    --device: ключ устройства из DEVICES (обязательный)
    --check-logs: искать клиентские исключения в логах устройства
    """
    parser.addoption(
        "--device",
        action="store",
        required=True,
        choices=list(DEVICES.keys()),
        help="Укажите устройство для тестов. Доступные варианты: %(choices)s"
    )
    parser.addoption(
        "--check-logs",
        action="store_true",
        help="Проверять клиентские логи на исключения после каждого теста"
    )


def pytest_configure(config):
    """
    Интерактивный выбор устройства, если --device не передан (для локальных запусков).

    Примечание:
        На CI и в автоматизированных прогонах всегда передавайте --device и отключайте интерактивность.
    """
    if config.getoption("--device") is None:
        device = questionary.select(
            "Выберите устройство:",
            choices=list(DEVICES.keys()),
        ).ask()
        config.option.device = device


# =========================
# ДРАЙВЕР APPIUM
# =========================

@pytest.fixture(scope="function", autouse=True)
def appium_driver(request):
    """
    Фикстура драйвера: инициализирует Appium WebDriver и завершает его по окончании теста.

    Поведение:
        - Собирает capabilities из DEVICES[--device]
        - Создаёт Remote драйвер (http://127.0.0.1:4723) с UiAutomator2/XCUITest
        - implicit wait = 10s
        - driver.quit() в финализаторе
    """
    device = request.config.getoption("--device")
    device_config = DEVICES[device]

    if device_config["platform_name"] == "Android":
        options = UiAutomator2Options()
        options.set_capability("clearDeviceLogsOnStart", True)
        options.set_capability("skipLogcatCapture", False)

        options.android_install_timeout = 600000
        options.adb_exec_timeout = 600000
        options.uiautomator2_server_install_timeout = 600000
        options.enforce_app_install = True
        options.skip_server_installation = False
        options.auto_grant_permissions = True

    else:
        options = XCUITestOptions()

    for key, value in device_config.items():
        setattr(options, key, value)

    driver = Remote("http://127.0.0.1:4723", options=options)
    driver.implicitly_wait(10)

    yield driver
    driver.quit()


# =========================
# СЦЕНАРНЫЕ ФИКСТУРЫ ВХОДА
# =========================

def _open_env_options(appium_driver) -> None:
    """Открывает панель опций на экране выбора окружения."""
    wait_for_template(
        template_path=GameTemplates.EnvScreenTemplates.ENV_SELECT_SCREEN,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.EnvScreen.OPEN_OPTIONS,
        appium_driver=appium_driver,
        template_path=GameTemplates.EnvScreenTemplates.OPTIONS_SCREEN,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.EnvScreen.OPTIONS_TAB,
        appium_driver=appium_driver,
        template_path=GameTemplates.EnvScreenTemplates.OPTIONS_FLAGS_SCREEN,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )


def _confirm_env_and_reach_login(appium_driver) -> None:
    """Закрывает экран окружения и доходит до кнопки гостевого входа."""
    tap_and_wait_for_template(
        button=DeviceButtons.EnvScreen.CLOSE_OPTIONS,
        appium_driver=appium_driver,
        template_path=GameTemplates.EnvScreenTemplates.ENV_SELECT_SCREEN,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )

    DeviceButtons.EnvScreen.TARGET_ENV.tap(appium_driver)
    time.sleep(0.5)

    tap_and_wait_for_template(
        button=DeviceButtons.EnvScreen.CLOSE,
        appium_driver=appium_driver,
        template_path=GameTemplates.LoginScreenTemplates.WELCOME_POPUP,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.LoginScreen.WELCOME_ACCEPT,
        appium_driver=appium_driver,
        template_path=GameTemplates.LoginScreenTemplates.GUEST_LOGIN_BUTTON,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )


@pytest.fixture
def enter_login_screen(appium_driver: object) -> None:
    """
    Вход на экран логина: экран окружения уже открыт, попап принят, видна кнопка гостя.
    """
    logger.info("enter_login_screen/start")

    wait_for_template(
        template_path=GameTemplates.EnvScreenTemplates.ENV_SELECT_SCREEN,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.EnvScreen.CLOSE,
        appium_driver=appium_driver,
        template_path=GameTemplates.LoginScreenTemplates.WELCOME_POPUP,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.LoginScreen.WELCOME_ACCEPT,
        appium_driver=appium_driver,
        template_path=GameTemplates.LoginScreenTemplates.GUEST_LOGIN_BUTTON,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )
    logger.info("enter_login_screen/done (GUEST_LOGIN_BUTTON is found)")


@pytest.fixture
def enter_lobby(appium_driver: object) -> None:
    """
    Гостевой вход в лобби. Перед выбором окружения включает показ попапов.
    Переключатели не меняют шаблон, поэтому между ними короткая пауза.
    """
    logger.info("enter_lobby/start popups=on")

    _open_env_options(appium_driver)

    DeviceButtons.EnvScreen.TOGGLE_POPUPS.tap(appium_driver)
    time.sleep(0.5)

    _confirm_env_and_reach_login(appium_driver)
    tap_and_wait_for_template(
        button=DeviceButtons.LoginScreen.GUEST_LOGIN,
        appium_driver=appium_driver,
        template_path=GameTemplates.LobbyTemplates.PLAY_BUTTON,
        threshold=0.95, timeout=40.0, interval=0.5, attempts=1, attach_on_success=True
    )
    logger.info("enter_lobby/done (PLAY_BUTTON is found)")


@pytest.fixture
def enter_lobby_without_popups(appium_driver: object) -> None:
    """
    Тот же вход в лобби, но с выключенными наградными попапами.
    """
    logger.info("enter_lobby_without_popups/start popups=off")

    _open_env_options(appium_driver)

    DeviceButtons.EnvScreen.TOGGLE_POPUPS.tap(appium_driver)
    time.sleep(0.5)

    DeviceButtons.EnvScreen.TOGGLE_REWARDS.tap(appium_driver)
    time.sleep(0.5)

    _confirm_env_and_reach_login(appium_driver)
    tap_and_wait_for_template(
        button=DeviceButtons.LoginScreen.GUEST_LOGIN,
        appium_driver=appium_driver,
        template_path=GameTemplates.LobbyTemplates.PLAY_BUTTON,
        threshold=0.95, timeout=40.0, interval=0.5, attempts=1, attach_on_success=True
    )
    logger.info("enter_lobby_without_popups/done (PLAY_BUTTON is found)")
