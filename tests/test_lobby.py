from buttons import DeviceButtons
from open_cv import wait_for_template, tap_and_wait_for_template
from templates.templates import GameTemplates


def test_open_menu(enter_lobby, appium_driver):
    """
    В лобби видна кнопка старта. Тап по меню открывает экран меню.
    """
    wait_for_template(
        template_path=GameTemplates.LobbyTemplates.PLAY_BUTTON,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
    tap_and_wait_for_template(
        button=DeviceButtons.Lobby.MENU,
        appium_driver=appium_driver,
        template_path=GameTemplates.LobbyTemplates.MENU_SCREEN,
        threshold=0.95, timeout=15.0, interval=0.5, attempts=1, attach_on_success=True
    )
