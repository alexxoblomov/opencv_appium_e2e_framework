import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class Button:
    """
    Тап по координате в базовом разрешении.
    conftest подменяет tap и пересчитывает точку под текущий экран.
    """
    x: int
    y: int

    def tap(self, driver):
        try:
            driver.tap([(self.x, self.y)])
        except Exception:
            raise


class DeviceButtons:
    """
    Пример раскладки кнопок для базового разрешения из devices.py.

    Координаты ниже — иллюстрация. Снимите свои с экрана приложения
    и разложите их по экранам так же, как здесь.
    """

    class EnvScreen:
        OPEN_OPTIONS = Button(x=1400, y=1080)
        OPTIONS_TAB = Button(x=640, y=120)
        TOGGLE_POPUPS = Button(x=900, y=700)
        TOGGLE_REWARDS = Button(x=1600, y=700)
        CLOSE_OPTIONS = Button(x=2300, y=80)
        TARGET_ENV = Button(x=420, y=560)
        CLOSE = Button(x=2480, y=140)

    class LoginScreen:
        WELCOME_ACCEPT = Button(x=1360, y=860)
        GUEST_LOGIN = Button(x=800, y=900)
        GOOGLE_LOGIN = Button(x=1500, y=900)
        FACEBOOK_LOGIN = Button(x=1150, y=900)

    class Lobby:
        MENU = Button(x=400, y=1080)
