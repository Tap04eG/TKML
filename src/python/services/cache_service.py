"""
CacheService — сервис для кэширования файлов и данных
"""
import os
import time
from pathlib import Path
from threading import Timer
from typing import Optional, Any
from services.log_service import LogService

class CacheService:
    _instance = None
    _timer = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_manager=None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.config_manager = config_manager
        self.cache_dir = Path(self.config_manager.get('cache_path', '.tmkl/cache')) if self.config_manager else Path('.tmkl/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = int(self.config_manager.get('cache_ttl', 60*60)) if self.config_manager else 60*60  # 1 час по умолчанию
        self.cleanup_on_timer()

    def _key_to_path(self, key: str) -> Path:
        # Преобразуем ключ в безопасное имя файла
        safe = key.replace('/', '_').replace(':', '_').replace('?', '_').replace('&', '_')
        return self.cache_dir / safe

    def has(self, key: str, ttl: Optional[int] = None) -> bool:
        path = self._key_to_path(key)
        if not path.exists():
            return False
        age = time.time() - path.stat().st_mtime
        ttl = ttl or self.default_ttl
        if age > ttl:
            try:
                path.unlink()
            except Exception:
                pass
            return False
        return True

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[bytes]:
        if not self.has(key, ttl):
            return None
        path = self._key_to_path(key)
        try:
            with open(path, 'rb') as f:
                return f.read()
        except Exception as e:
            LogService.log('ERROR', f'Ошибка чтения из кэша: {e}', source='CacheService')
            return None

    def set(self, key: str, data: bytes, ttl: Optional[int] = None):
        path = self._key_to_path(key)
        try:
            with open(path, 'wb') as f:
                f.write(data)
            # Обновляем время модификации
            os.utime(path, None)
        except Exception as e:
            LogService.log('ERROR', f'Ошибка записи в кэш: {e}', source='CacheService')

    def get_path(self, key: str, ttl: Optional[int] = None) -> Optional[Path]:
        if self.has(key, ttl):
            return self._key_to_path(key)
        return None

    def clear(self):
        for file in self.cache_dir.glob('*'):
            try:
                file.unlink()
            except Exception as e:
                LogService.log('ERROR', f'Ошибка удаления файла кэша: {e}', source='CacheService')

    def cleanup(self, max_age_seconds: Optional[int] = None):
        max_age = max_age_seconds or self.default_ttl
        now = time.time()
        for file in self.cache_dir.glob('*'):
            try:
                age = now - file.stat().st_mtime
                if age > max_age:
                    file.unlink()
            except Exception as e:
                LogService.log('ERROR', f'Ошибка очистки кэша: {e}', source='CacheService')

    def cleanup_on_timer(self, interval_seconds: Optional[int] = None):
        interval = interval_seconds or 2*60*60  # 2 часа по умолчанию
        if self._timer:
            self._timer.cancel()
        self._timer = Timer(interval, self._cleanup_timer_callback)
        self._timer.daemon = True
        self._timer.start()

    def _cleanup_timer_callback(self):
        self.cleanup()
        self.cleanup_on_timer() 