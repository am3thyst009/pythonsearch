import time
import functools
import asyncio

# Хранилище кэша: ключ -> (результат, время сохранения)
_cache_store: dict = {}


def cache(ttl: int = 300):
    """
    Декоратор кэширования для async-функций.
    ttl — время жизни кэша в секундах (по умолчанию 5 минут).
    Если функция уже вызывалась с теми же аргументами — возвращает
    сохранённый результат без нового запроса к API.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()

            if key in _cache_store:
                result, saved_at = _cache_store[key]
                if now - saved_at < ttl:
                    print(f"  [кэш] результат взят из кэша для {func.__name__}")
                    return result

            result = await func(*args, **kwargs)
            _cache_store[key] = (result, now)
            return result
        return wrapper
    return decorator


def timer(func):
    """
    Декоратор для измерения времени выполнения async-функции.
    Выводит в консоль сколько секунд занял запрос.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"  [таймер] {func.__name__} выполнился за {elapsed:.2f}с")
        return result
    return wrapper


def retry(attempts: int = 3, delay: float = 1.0):
    """
    Декоратор повторных попыток для async-функций.
    При ошибке сети повторяет запрос до `attempts` раз с паузой `delay` секунд.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < attempts:
                        print(f"  [retry] попытка {attempt} не удалась: {e}. Повтор через {delay}с...")
                        await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator
