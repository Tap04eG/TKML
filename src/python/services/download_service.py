"""
DownloadService — сервис для скачивания файлов (sync/async, с кэшем)
"""
import requests
import aiohttp
import asyncio
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from services.cache_service import CacheService
from services.log_service import LogService

class DownloadService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_manager=None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.cache = CacheService(config_manager)
        self.config_manager = config_manager
        # Получаем количество потоков из конфига
        self.max_workers = getattr(config_manager, 'config', {}).get('download_threads', 8) if config_manager else 8

    def download_file_sync(self, url: str, dest: Path, progress_callback: Optional[Callable[[int, str], None]] = None, use_cache: bool = True) -> bool:
        key = url
        if use_cache and self.cache.has(key):
            data = self.cache.get(key)
            if data:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(data)
                LogService.log('INFO', f'Файл взят из кэша: {url}', source='DownloadService')
                if progress_callback:
                    progress_callback(100, 'Из кэша')
                return True
        
        # Retry-логика: 3 попытки с паузой 3 секунды между попытками
        max_retries = 3
        retry_delay = 3  # секунды
        timeout = 10  # секунды на одну попытку
        
        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            try:
                with requests.get(url, stream=True, timeout=timeout) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(dest, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total:
                                    percent = int(downloaded * 100 / total)
                                    # Рассчитываем скорость
                                    elapsed = time.time() - start_time
                                    if elapsed > 0:
                                        speed_mb = (downloaded / 1024 / 1024) / elapsed
                                        progress_callback(percent, f'Скачивание... {speed_mb:.1f} MB/s')
                                    else:
                                        progress_callback(percent, 'Скачивание...')
                    
                    if use_cache:
                        with open(dest, 'rb') as f:
                            self.cache.set(key, f.read())
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed_mb = (downloaded / 1024 / 1024) / elapsed
                    LogService.log('INFO', f'Файл скачан: {url} ({speed_mb:.1f} MB/s)', source='DownloadService')
                else:
                    LogService.log('INFO', f'Файл скачан: {url}', source='DownloadService')
                    
                if progress_callback:
                    progress_callback(100, 'Готово')
                return True
                
            except Exception as e:
                LogService.log('WARNING', f'Попытка {attempt}/{max_retries} не удалась для {url}: {e}', source='DownloadService')
                
                # Удаляем частично скачанный файл
                if dest.exists():
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                
                # Если это не последняя попытка, ждём перед следующей
                if attempt < max_retries:
                    LogService.log('INFO', f'Ожидание {retry_delay} сек. перед повторной попыткой для {url}', source='DownloadService')
                    time.sleep(retry_delay)
                else:
                    # Последняя попытка не удалась
                    LogService.log('ERROR', f'Все {max_retries} попытки скачивания не удались для {url}: {e}', source='DownloadService')
                    if progress_callback:
                        progress_callback(-1, f'Ошибка: {e}')
                    return False
        
        return False

    def download_multiple_files(self, files: List[Tuple[str, Path]], progress_callback: Optional[Callable[[int, int, str], None]] = None, log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Многопоточное скачивание нескольких файлов
        
        Args:
            files: Список кортежей (url, destination_path)
            progress_callback: Callback(текущий_файл, всего_файлов, сообщение)
            log_callback: Callback для логирования
        """
        if not files:
            return True
            
        total_files = len(files)
        successful_downloads = 0
        failed_downloads = 0
        
        if log_callback:
            log_callback(f"Начинаем скачивание {total_files} файлов в {self.max_workers} потоках")
        
        def download_single_file(file_info: Tuple[str, Path]) -> Tuple[bool, str, Path, float]:
            url, dest_path = file_info
            start_time = time.time()
            try:
                result = self.download_file_sync(url, dest_path)
                duration = time.time() - start_time
                return result, url, dest_path, duration
            except Exception as e:
                duration = time.time() - start_time
                return False, url, dest_path, duration
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Запускаем все задачи
            future_to_file = {executor.submit(download_single_file, file_info): file_info for file_info in files}
            
            # Обрабатываем результаты по мере завершения
            for i, future in enumerate(as_completed(future_to_file)):
                try:
                    success, url, dest_path, duration = future.result()
                    current_file = i + 1
                    
                    if success:
                        successful_downloads += 1
                        msg = f"Скачано {current_file}/{total_files}: {dest_path.name} за {duration:.2f} сек."
                        if log_callback:
                            log_callback(msg)
                        LogService.log('INFO', msg, source='DownloadService')
                        if progress_callback:
                            progress_callback(current_file, total_files, f"Скачано: {dest_path.name}")
                    else:
                        failed_downloads += 1
                        msg = f"Ошибка {current_file}/{total_files}: {dest_path.name} (время: {duration:.2f} сек.)"
                        if log_callback:
                            log_callback(msg)
                        LogService.log('ERROR', msg, source='DownloadService')
                        if progress_callback:
                            progress_callback(current_file, total_files, f"Ошибка: {dest_path.name}")
                            
                except Exception as e:
                    failed_downloads += 1
                    err_msg = f"Исключение при скачивании: {e}"
                    if log_callback:
                        log_callback(err_msg)
                    LogService.log('ERROR', err_msg, source='DownloadService')
        
        if log_callback:
            log_callback(f"Скачивание завершено: {successful_downloads} успешно, {failed_downloads} ошибок")
        LogService.log('INFO', f"Скачивание завершено: {successful_downloads} успешно, {failed_downloads} ошибок", source='DownloadService')
        
        return failed_downloads == 0

    async def download_file_async(self, url: str, dest: Path, progress_callback: Optional[Callable[[int, str], None]] = None, use_cache: bool = True) -> bool:
        key = url
        if use_cache and self.cache.has(key):
            data = self.cache.get(key)
            if data:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(data)
                LogService.log('INFO', f'Файл взят из кэша (async): {url}', source='DownloadService')
                if progress_callback:
                    progress_callback(100, 'Из кэша')
                return True
        
        # Retry-логика: 3 попытки с паузой 3 секунды между попытками
        max_retries = 3
        retry_delay = 3  # секунды
        timeout = 10  # секунды на одну попытку
        
        for attempt in range(1, max_retries + 1):
            try:
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        total = int(resp.headers.get('content-length', 0))
                        downloaded = 0
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if progress_callback and total:
                                        percent = int(downloaded * 100 / total)
                                        progress_callback(percent, 'Скачивание...')
                        if use_cache:
                            with open(dest, 'rb') as f2:
                                self.cache.set(key, f2.read())
                LogService.log('INFO', f'Файл скачан (async): {url}', source='DownloadService')
                if progress_callback:
                    progress_callback(100, 'Готово')
                return True
                
            except Exception as e:
                LogService.log('WARNING', f'Попытка {attempt}/{max_retries} не удалась для {url} (async): {e}', source='DownloadService')
                
                # Удаляем частично скачанный файл
                if dest.exists():
                    try:
                        dest.unlink()
                    except Exception:
                        pass
                
                # Если это не последняя попытка, ждём перед следующей
                if attempt < max_retries:
                    LogService.log('INFO', f'Ожидание {retry_delay} сек. перед повторной попыткой для {url} (async)', source='DownloadService')
                    await asyncio.sleep(retry_delay)
                else:
                    # Последняя попытка не удалась
                    LogService.log('ERROR', f'Все {max_retries} попытки async-скачивания не удались для {url}: {e}', source='DownloadService')
                    if progress_callback:
                        progress_callback(-1, f'Ошибка: {e}')
                    return False
        
        return False

    def download_json(self, url: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Загрузить JSON данные с URL"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            LogService.log('ERROR', f'Ошибка загрузки JSON с {url}: {e}', source='DownloadService')
            return None

    def download_text(self, url: str, timeout: int = 30) -> Optional[str]:
        """Загрузить текстовые данные с URL"""
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            LogService.log('ERROR', f'Ошибка загрузки текста с {url}: {e}', source='DownloadService')
            return None

    def download_with_cache(self, url: str, dest: Path, progress_callback: Optional[Callable[[int, str], None]] = None, use_cache: bool = True) -> bool:
        """
        Только синхронный вариант. Для async используйте download_with_cache_async.
        """
        return self.download_file_sync(url, dest, progress_callback, use_cache)

    async def download_with_cache_async(self, url: str, dest: Path, progress_callback: Optional[Callable[[int, str], None]] = None, use_cache: bool = True) -> bool:
        return await self.download_file_async(url, dest, progress_callback, use_cache) 