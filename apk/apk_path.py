from pathlib import Path


class AppBuild:
    """
    Путь к сборке, которую Appium ставит на устройство.
    Положите файл в apk/app.apk или поменяйте имя ниже.
    """

    APP_PATH = str(Path(__file__).parent / "app.apk")
