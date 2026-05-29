import logging
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "app.log")


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает настроенный логгер.
    Пишет одновременно в файл app.log и в консоль (только WARNING и выше).
    Вызывать в каждом модуле: logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # уже настроен, не дублируем хендлеры

    logger.setLevel(logging.DEBUG)

    # Хендлер для файла — пишет всё начиная с DEBUG
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  —  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Хендлер для консоли — только WARNING и выше, чтобы не засорять вывод
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("  [%(levelname)s] %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
