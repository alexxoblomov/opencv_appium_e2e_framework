from open_cv import wait_for_template
from templates.templates import GameTemplates


def test_login_screen_state(enter_login_screen, appium_driver):
    """
    После входа на экран логина на нём есть кнопки гостя, Google и Facebook.
    """
    wait_for_template(
        template_path=GameTemplates.LoginScreenTemplates.GUEST_LOGIN_BUTTON,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
    wait_for_template(
        template_path=GameTemplates.LoginScreenTemplates.GOOGLE_LOGIN_BUTTON,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
    wait_for_template(
        template_path=GameTemplates.LoginScreenTemplates.FACEBOOK_LOGIN_BUTTON,
        appium_driver=appium_driver,
        threshold=0.95, timeout=15.0, interval=0.5, attach_on_success=True
    )
