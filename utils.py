import logging, re, allure, os
from typing import List, Dict, Optional


logger = logging.getLogger(__name__)


def map_point(x, y, base_w, base_h, cur_w, cur_h):
    """
    Маппит точку (x, y) из базового разрешения (base_w x base_h)
    в текущее разрешение экрана (cur_w x cur_h), учитывая соотношение сторон и отступы.

    Аргументы:
    - x, y: координаты точки в базовом разрешении
    - base_w, base_h: базовая ширина/высота
    - cur_w, cur_h: текущая ширина/высота окна устройства

    Возвращает:
    - (mapped_x, mapped_y) в координатах текущего экрана
    """
    scale = min(cur_w / base_w, cur_h / base_h)
    offset_x = (cur_w - base_w * scale) / 2
    offset_y = (cur_h - base_h * scale) / 2
    return int(offset_x + x * scale), int(offset_y + y * scale)


def map_box(x1, y1, x2, y2, base_w, base_h, cur_w, cur_h):
    """
    Маппит прямоугольник из базового разрешения в текущее по двум углам.

    Аргументы:
    - x1, y1, x2, y2: координаты углов в базовом разрешении
    - base_w, base_h, cur_w, cur_h: см. map_point

    Возвращает:
    - (mx1, my1, mx2, my2) — прямоугольник в координатах текущего экрана
    """
    x1, y1 = map_point(x1, y1, base_w, base_h, cur_w, cur_h)
    x2, y2 = map_point(x2, y2, base_w, base_h, cur_w, cur_h)
    return x1, y1, x2, y2


def attach_latest_screenshot_to_allure(screenshots_dir="screenshots", attachment_name="screenshot"):
    """
    Находит самый свежий .png в папке screenshots_dir и прикрепляет его в Allure.

    Аргументы:
    - screenshots_dir: каталог скриншотов
    - attachment_name: имя вложения в Allure

    Поведение:
    - Если нет файлов — пишет лог и ничего не прикладывает
    - Ошибки при чтении/вложении логируются и не роняют тест
    """
    try:
        if os.path.exists(screenshots_dir):
            screenshot_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]

            if screenshot_files:
                latest_screenshot = max(screenshot_files,
                                        key=lambda x: os.path.getctime(os.path.join(screenshots_dir, x)))
                screenshot_path = os.path.join(screenshots_dir, latest_screenshot)

                with open(screenshot_path, 'rb') as f:
                    allure.attach(
                        f.read(),
                        name=attachment_name,
                        attachment_type=allure.attachment_type.PNG
                    )
                logger.info(f"Screenshot {latest_screenshot} attached to allure report")
            else:
                logger.info(f"Not found screenshots in {screenshots_dir}")
        else:
            logger.info(f"Directory {screenshots_dir}  not present")
    except Exception as e:
        logger.info(f"Error while attaching screenshot: {str(e)}")


# =========================
# ОТЛОВ КЛИЕНТСКИХ ОШИБОК
# =========================


EXCEPTION_PATTERNS = [
    re.compile(r"\bNullReferenceException\b", re.IGNORECASE),
    re.compile(r"Object reference not set to an instance of an object", re.IGNORECASE),
    re.compile(r"^\s*E/Unity\s*:.*\bNullReferenceException\b", re.IGNORECASE),  # Unity error-строки с NRE
]


def _normalize_epoch_ms(ts: Optional[float]) -> Optional[int]:
    if ts is None:
        return None
    try:
        t = float(ts)
        if t < 10**12:  # секунды → мс
            t *= 1000.0
        return int(t)
    except Exception:
        return None


def find_exceptions_in_log_entries(log_entries: List[Dict], since_ms: Optional[int] = None) -> List[Dict]:
    suspects: List[Dict] = []
    for entry in log_entries or []:
        ts_ms = _normalize_epoch_ms(entry.get("timestamp"))
        if since_ms is not None and ts_ms is not None and ts_ms < since_ms:
            continue
        message = entry.get("message") or ""
        if any(p.search(message) for p in EXCEPTION_PATTERNS):
            suspects.append(entry)
    return suspects