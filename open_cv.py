import logging, inspect, os, cv2, allure
import numpy as np
import time
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

"""

Здесь лежит логика библиотеки Open_CV - в будущем предлагаю все функции, связанные со сравнением описывать тут
Пока что здесь лежит только единственная и ключевая assert-конструкция фреймворка

"""


def get_screenshot_image(driver) -> Tuple[np.ndarray, bytes]:
    """
    Делает скриншот устройства через Appium и возвращает:
    - изображение в формате OpenCV (BGR)
    - исходные PNG-байты (для вложения в Allure)

    Файл на диск не записывается.
    """
    png_bytes = driver.get_screenshot_as_png()
    nparr = np.frombuffer(png_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError("Failed to decode screenshot bytes")
    return img, png_bytes


def compare_image_with_template(screenshot_bgr: np.ndarray, template_path: str, threshold: float = 0.8) -> Tuple[bool, float]:
    """
    То же, что compare_with_template, но принимает изображение скриншота (BGR) в памяти.
    Поддерживает маску по альфа-каналу шаблона (PNG с прозрачностью).
    """
    template_rgba = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)

    if screenshot_bgr is None or template_rgba is None:
        raise FileNotFoundError("Failed to load images")

    mask = None
    if template_rgba.ndim == 3 and template_rgba.shape[2] == 4:
        template_bgr = template_rgba[:, :, :3]
        alpha = template_rgba[:, :, 3]
        mask = (alpha > 0).astype(np.uint8) * 255
    else:
        template_bgr = template_rgba if template_rgba.ndim == 3 else cv2.cvtColor(template_rgba, cv2.COLOR_GRAY2BGR)

    th, tw = template_bgr.shape[:2]

    # screenshot_resized = cv2.resize(screenshot_bgr, (tw, th), interpolation=cv2.INTER_AREA)

    method = cv2.TM_CCOEFF_NORMED if mask is None else cv2.TM_CCORR_NORMED
    if mask is not None and int(mask.sum()) == 0:
        mask = None
        method = cv2.TM_CCOEFF_NORMED

    if mask is not None:
        result = cv2.matchTemplate(screenshot_bgr , template_bgr, method, mask=mask)
    else:
        result = cv2.matchTemplate(screenshot_bgr , template_bgr, method)

    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold, max_val


def wait_for_template(template_path, appium_driver, threshold, timeout=20.0, interval=0.5, attach_on_success=False, log_every_n=3, attach_timeline=True):
    """
    Ожидает появления шаблона на экране: с заданной периодичностью делает скриншоты и сравнивает с шаблоном.

    Аргументы:
    - template_path: путь/Path к шаблону.
    - threshold: порог совпадения [0..1] для успеха.
    - appium_driver: активный Appium WebDriver.
    - timeout: общий бюджет ожидания (сек).
    - interval: пауза между попытками (сек).
    - attach_on_success: прикреплять найденный скриншот в Allure.
    - log_every_n: писать DEBUG-лог каждой N-й попытки.
    - attach_timeline: прикреплять таймлайн совпадений в Allure.

    Возвращает:
    - True при успехе, иначе исключение.

    Исключения:
    - AssertionError при истечении timeout без достижения порога.
    """
    start = time.monotonic()

    last_match_value = None
    last_png_bytes = None
    probe = 0
    timeline = []  # (elapsed_sec, match_value)

    name = getattr(template_path, 'name', str(template_path))

    with allure.step(f"Ожидание появления проверяемого экрана: {name} (threshold={threshold}, timeout={timeout}s)"):
        while time.monotonic() - start < timeout:
            probe += 1
            screenshot_bgr, png_bytes = get_screenshot_image(appium_driver)
            last_png_bytes = png_bytes

            is_found, match_value = compare_image_with_template(
                screenshot_bgr=screenshot_bgr,
                template_path=str(template_path),
                threshold=threshold
            )

            # если score = inf/nan — быстро перепробуем кадр
            if not np.isfinite(match_value):
                time.sleep(0.2)
                continue

            last_match_value = match_value
            elapsed = time.monotonic() - start
            timeline.append((elapsed, match_value))
            if probe % log_every_n == 0:
                logger.debug(f"wait_for_template[{name}]: probe={probe} match={match_value:.3f} elapsed={elapsed:.2f}s remaining={timeout - elapsed:.2f}s")

            if is_found:
                logger.info(f"wait_for_template[{name}]: success match={match_value:.2f} elapsed={elapsed:.2f}s")
                if attach_on_success and last_png_bytes is not None:
                    allure.attach(last_png_bytes, name="matched_screenshot", attachment_type=allure.attachment_type.PNG)
                if attach_timeline:
                    try:
                        lines = [f"{t:.2f}s\t{m:.3f}" for t, m in timeline]
                        allure.attach("\n".join(lines), name="match_timeline", attachment_type=allure.attachment_type.TEXT)
                    except Exception:
                        pass
                return True

            time.sleep(interval)

        if last_png_bytes is not None:
            allure.attach(last_png_bytes, name="last_before_timeout", attachment_type=allure.attachment_type.PNG)

        if attach_timeline:
            try:
                lines = [f"{t:.2f}s\t{m:.3f}" for t, m in timeline]
                allure.attach("\n".join(lines), name="match_timeline", attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass

        elapsed = time.monotonic() - start
        logger.warning(f"wait_for_template[{name}]: timeout last_match={last_match_value:.2f} elapsed={elapsed:.2f}s")

        raise AssertionError(
            f"Template not found within {timeout}s. Last match score: {last_match_value:.2f} (expected ≥ {threshold})"
        )


def tap_and_wait_for_template(button, appium_driver, template_path, threshold=0.80, timeout=12.0, interval=0.5, attempts=3, attach_on_success=True):
    """
    Выполняет тап по координате и ожидает появления целевого шаблона, с ограниченным числом ретраев.

    Аргументы:
    - button: объект с методом tap(driver) (например, Button/DeviceButtons.*).
    - appium_driver: активный Appium WebDriver.
    - template_path: путь/Path к ожидаемому шаблону.
    - threshold: порог совпадения [0..1].
    - timeout: бюджет ожидания после тапа (сек).
    - interval: интервал опроса (сек).
    - attempts: число повторных тапов при неудаче.
    - attach_on_success: прикреплять найденный скриншот в Allure.

    Возвращает:
    - True при успехе, иначе исключение.

    Исключения:
    - AssertionError, если после attempts попыток шаблон не появился.
    """
    for attempt in range(1, attempts + 1):
        button.tap(appium_driver)
        try:
            wait_for_template(
                template_path=template_path,
                threshold=threshold,
                appium_driver=appium_driver,
                timeout=timeout,
                interval=interval,
                attach_on_success=attach_on_success
            )
            return True
        except AssertionError:
            if attempt == attempts:
                raise
            time.sleep(0.7)


def wait_until_not_template(template_path, threshold, appium_driver, timeout=10.0, interval=0.3, log_every_n=3, attach_timeline=True):
    """
    Ожидает исчезновения шаблона с экрана (совпадение должно стать < threshold) в пределах timeout.

    Аргументы:
    - template_path: путь/Path к шаблону.
    - threshold: порог совпадения [0..1] ниже которого считаем, что шаблон исчез.
    - appium_driver: активный Appium WebDriver.
    - timeout: общий бюджет ожидания (сек).
    - interval: интервал опроса (сек).
    - log_every_n: писать DEBUG-лог каждой N-й попытки.
    - attach_timeline: прикреплять таймлайн совпадений в Allure.

    Возвращает:
    - True при успехе, иначе исключение.

    Исключения:
    - AssertionError, если шаблон не исчез до истечения timeout.
    """
    start = time.monotonic()
    last_match_value = None
    last_png_bytes = None
    probe = 0
    timeline = []  # (elapsed_sec, match_value)

    name = getattr(template_path, 'name', str(template_path))

    with allure.step(f"Ожидание смены экрана: {name} (threshold={threshold}, timeout={timeout}s)"):
        while time.monotonic() - start < timeout:
            probe += 1
            screenshot_bgr, png_bytes = get_screenshot_image(appium_driver)
            last_png_bytes = png_bytes

            is_found, match_value = compare_image_with_template(
                screenshot_bgr=screenshot_bgr,
                template_path=str(template_path),
                threshold=threshold
            )

            # если score = inf/nan — быстро перепробуем кадр
            if not np.isfinite(match_value):
                time.sleep(0.2)
                continue

            last_match_value = match_value
            elapsed = time.monotonic() - start
            timeline.append((elapsed, match_value))

            if probe % log_every_n == 0:
                logger.debug(f"wait_until_not_template[{name}]: probe={probe} match={match_value:.3f} elapsed={elapsed:.2f}s remaining={timeout - elapsed:.2f}s")

            if not is_found:
                logger.info(f"wait_until_not_template[{name}]: disappeared elapsed={elapsed:.2f}s")

                if attach_timeline:
                    try:
                        lines = [f"{t:.2f}s\t{m:.3f}" for t, m in timeline]
                        allure.attach("\n".join(lines), name="match_timeline", attachment_type=allure.attachment_type.TEXT)
                    except Exception:
                        pass
                return True

            time.sleep(interval)

        if last_png_bytes is not None:
            allure.attach(last_png_bytes, name="last_before_timeout", attachment_type=allure.attachment_type.PNG)

        if attach_timeline:
            try:
                lines = [f"{t:.2f}s\t{m:.3f}" for t, m in timeline]
                allure.attach("\n".join(lines), name="match_timeline", attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass

        elapsed = time.monotonic() - start
        logger.warning(f"wait_until_not_template[{name}]: timeout last_match={last_match_value:.2f} elapsed={elapsed:.2f}s")

        raise AssertionError(
            f"Template did not disappear within {timeout}s. Last match score: {last_match_value:.2f} (expected < {threshold})"
        )
