# opencv_appium_e2e_framework

Пример мобильных e2e-тестов на `pytest` + Appium. Репозиторий показывает запуск приложения на устройстве, тапы по координатам, ожидание экранов через OpenCV и отчёты Allure.

> Проект в демонстрационном состоянии. Конфиг устройства, путь к сборке, шаблоны экранов и тест-кейсы нужно адаптировать под своё приложение перед запуском.

## Что внутри

- `conftest.py` — настройка `pytest`, Appium-драйвер, CLI-опции, маппинг координат и пример фикстур входа.
- `devices.py` — пример конфигурации устройств.
- `buttons.py` — модель кнопки и пример координат.
- `open_cv.py` — ожидание экранов и сравнение скриншота с шаблоном через OpenCV.
- `utils.py` — маппинг координат и разбор клиентских логов.
- `templates/` — пути к шаблонам экранов. Сами PNG кладутся локально и в git не попадают.
- `apk/` — место для сборки. APK в git не коммитится.

## Возможности

- Запуск мобильных тестов через Appium.
- Несколько устройств через параметр `--device`.
- Автоматический пересчёт координат под разрешение текущего устройства.
- Проверка появления и исчезновения UI по изображению.
- Сбор логов и поиск клиентских `NullReferenceException`.
- Вложения скриншотов и диагностической информации в Allure.

## Требования

- Python 3.10+
- Node.js и Appium Server
- Android SDK / ADB
- Подключенное Android-устройство или эмулятор
- Allure CLI, если нужны HTML-отчёты

Зависимости:

```bash
pip install -r requirements.txt
```

Appium Server:

```bash
npm install -g appium
appium driver install uiautomator2
```

## Подготовка

1. Положите сборку в `apk/app.apk` или поменяйте путь в `apk/apk_path.py`.

2. В `devices.py` укажите `device_name` (`adb devices`) и `platform_version`. Ключ `example_phone` можно переименовать.

3. Нарежьте элементы UI в PNG и положите их по путям из `templates/templates.py`. Координаты кнопок в `buttons.py` задайте в базовом разрешении `base_w` × `base_h`.

4. Проверьте, что ADB видит устройство:

```bash
adb devices
```

5. Запустите Appium Server:

```bash
appium --address 127.0.0.1 --port 4723 --allow-cors
```

## Запуск тестов

```bash
pytest -s -k "test_open_menu" -v --device "example_phone"
```

С проверкой клиентских логов на исключения:

```bash
pytest -s -k "test_open_menu" -v --device "example_phone" --check-logs
```

Отчёт Allure:

```bash
pytest -s -k "test_login_screen_state" -v --device "example_phone" --alluredir=./allure-results --clean-alluredir
allure generate ./allure-results -o ./allure-report --clean
allure open ./allure-report
```

## Как добавлять тесты

1. Добавьте шаблоны нужных экранов в `templates/` и пути в `templates/templates.py`.
2. Опишите координаты через `Button` или вложенные классы `DeviceButtons`.
3. Используйте `wait_for_template`, `wait_until_not_template` или `tap_and_wait_for_template` вместо фиксированных `sleep`.
4. После действия проверяйте состояние экрана: шаблон появился, исчез или UI стабилизировался.

## Пример

```python
from open_cv import tap_and_wait_for_template
from buttons import DeviceButtons
from templates.templates import GameTemplates


def test_open_menu(enter_lobby, appium_driver):
    tap_and_wait_for_template(
        button=DeviceButtons.Lobby.MENU,
        appium_driver=appium_driver,
        template_path=GameTemplates.LobbyTemplates.MENU_SCREEN,
        threshold=0.8,
    )
```

## Важно

- В репозитории нет серийников устройств, сборок и скриншотов приложения.
- Значения в `devices.py`, `buttons.py` и `apk/apk_path.py` нужно заменить на свои.
