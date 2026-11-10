from apk.apk_path import AppBuild


"""
Словарь DEVICES описывает устройства для Appium.
device_name — серийник из `adb devices`, platform_version — версия ОС с устройства.
Остальные поля обычно можно оставить как в примере.
base_w / base_h — разрешение, в котором сняты координаты кнопок. Маппер
пересчитывает их под фактический экран.
"""

DEVICES = {
    "example_phone": {
        "platform_name": "Android",
        "device_name": "YOUR_ADB_SERIAL",
        "platform_version": "14",
        "app": AppBuild.APP_PATH,
        "automation_name": "UiAutomator2",
        "no_reset": False,
        "androidInstallTimeout": 600000,
        "adbExecTimeout": 600000,
        "base_w": 2712,
        "base_h": 1220,
    },
}
