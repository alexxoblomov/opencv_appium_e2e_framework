from pathlib import Path


class BaseTemplates:
    """
    Общий корень каталога шаблонов.
    """
    BASE_DIR = Path(__file__).parent.parent
    TEMPLATES_DIR = BASE_DIR / "templates"


class GameTemplates:
    """
    Пути к вырезанным элементам UI, а не к скриншотам экрана целиком.

    Один класс — один экран. В тесте можно смешивать шаблоны разных экранов:
    нажать кнопку и дождаться элемента следующего экрана.
    Файлы в репозиторий не входят: положите свои PNG по этим путям.
    """

    class EnvScreenTemplates(BaseTemplates):
        ENV_SELECT_SCREEN = BaseTemplates.TEMPLATES_DIR / "env" / "env_select_screen.png"
        OPTIONS_SCREEN = BaseTemplates.TEMPLATES_DIR / "env" / "options_screen.png"
        OPTIONS_FLAGS_SCREEN = BaseTemplates.TEMPLATES_DIR / "env" / "options_flags_screen.png"

    class LoginScreenTemplates(BaseTemplates):
        WELCOME_POPUP = BaseTemplates.TEMPLATES_DIR / "login" / "welcome_popup.png"
        GUEST_LOGIN_BUTTON = BaseTemplates.TEMPLATES_DIR / "login" / "guest_login_button.png"
        GOOGLE_LOGIN_BUTTON = BaseTemplates.TEMPLATES_DIR / "login" / "google_login_button.png"
        FACEBOOK_LOGIN_BUTTON = BaseTemplates.TEMPLATES_DIR / "login" / "facebook_login_button.png"

    class LobbyTemplates(BaseTemplates):
        PLAY_BUTTON = BaseTemplates.TEMPLATES_DIR / "lobby" / "play_button.png"
        MENU_SCREEN = BaseTemplates.TEMPLATES_DIR / "lobby" / "menu_screen.png"
