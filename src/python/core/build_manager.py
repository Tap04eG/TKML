"""
Менеджер сборок Minecraft
Управление созданием, загрузкой и установкой сборок
"""

import os
import json
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
import traceback
import tempfile

from services.download_service import DownloadService
from services.cache_service import CacheService
from services.log_service import LogService


class BuildStatus(Enum):
    """Статусы сборок"""
    READY = "ready"           # Готова к запуску
    DOWNLOADING = "downloading"  # Скачивается
    INSTALLING = "installing"    # Устанавливается
    ERROR = "error"           # Ошибка
    UNKNOWN = "unknown"       # Неизвестно


class BuildManager:
    """Менеджер для работы со сборками Minecraft"""
    
    def __init__(self, config_manager, minecraft_manager):
        """Инициализация менеджера сборок"""
        self.config_manager = config_manager
        self.minecraft_manager = minecraft_manager
        self.minecraft_path = Path(self.config_manager.get("minecraft_path"))
        
        # Создаем структуру папок
        self.instances_path = self.config_manager.get_instances_path()
        self.versions_path = self.config_manager.get_versions_path()
        self.libraries_path = self.config_manager.get_libraries_path()
        self.assets_path = self.config_manager.get_assets_path()
        self.logs_path = self.config_manager.get_logs_path()
        self.config_path = self.config_manager.get_config_path()
        self.temp_path = self.config_manager.get_temp_path()
        
        # Создаем необходимые директории
        self._create_directory_structure()
        
        # Словарь для отслеживания состояний сборок
        self.build_states = {}
        self.build_progress = {}
        self.build_messages = {}
        
        # Блокировка для потокобезопасности
        self._state_lock = threading.Lock()
    
    def _create_directory_structure(self):
        """Создание структуры папок"""
        directories = [
            self.instances_path,
            self.versions_path,
            self.libraries_path,
            self.assets_path / "indexes",
            self.assets_path / "objects",
            self.assets_path / "virtual" / "legacy",
            self.logs_path / "crash_reports",
            self.config_path,
            self.temp_path / "downloads",
            self.temp_path / "installers",
            self.temp_path / "cache"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def create_build(self, build_config: Dict[str, Any], progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        print('create_build called, log_callback:', log_callback)
        if log_callback:
            log_callback(f"[BuildManager] Начато создание сборки: {build_config}")
        LogService.log('INFO', f"Вызван create_build с конфигом: {build_config}")
        LogService.log('INFO', f"[BuildManager] Начато создание сборки: {build_config}")
        try:
            build_name = build_config.get("name", "Unnamed Build")
            minecraft_version = build_config.get("minecraft_version")
            loader = build_config.get("loader", "Vanilla")
            loader_version = build_config.get("loader_version")
            if log_callback:
                log_callback(f"Параметры: name={build_name}, version={minecraft_version}, loader={loader}, loader_version={loader_version}")
            LogService.log('DEBUG', f"[BuildManager] Параметры: name={build_name}, version={minecraft_version}, loader={loader}, loader_version={loader_version}")
            if log_callback:
                log_callback(f"Создаём директорию для сборки: {build_name}")
            if progress_callback:
                progress_callback(0, "Подготовка к созданию сборки...")
            # Создаем директорию для сборки
            instance_dir = self.instances_path / self._sanitize_name(build_name)
            instance_dir.mkdir(parents=True, exist_ok=True)
            if log_callback:
                log_callback(f"Создана папка сборки: {instance_dir}")
            if progress_callback:
                progress_callback(5, "Создание папки сборки...")
            # Создаем .minecraft папку внутри сборки
            minecraft_instance_dir = instance_dir / ".minecraft"
            minecraft_instance_dir.mkdir(exist_ok=True)
            if log_callback:
                log_callback(f"Создана папка .minecraft: {minecraft_instance_dir}")
            if progress_callback:
                progress_callback(8, "Создание папки .minecraft...")
            if log_callback:
                log_callback(f"Загрузка Minecraft версии: {minecraft_version}")
            if progress_callback:
                progress_callback(10, "Загрузка Minecraft...")
            # Загружаем базовую версию Minecraft
            if not self._download_minecraft_version(str(minecraft_version), progress_callback, log_callback):
                if log_callback:
                    log_callback(f"Ошибка загрузки Minecraft версии: {minecraft_version}")
                return False
            if log_callback:
                log_callback(f"Minecraft {minecraft_version} загружен.")
            if progress_callback:
                progress_callback(30, "Minecraft загружен. Подготовка к установке лоадера...")
            if log_callback:
                log_callback(f"Установка лоадера: {loader}")
            if progress_callback:
                progress_callback(40, f"Установка {loader}...")
            # Устанавливаем лоадер
            version_id = str(minecraft_version)
            if loader != "Vanilla":
                if not self._install_loader(str(minecraft_version), loader, str(loader_version) if loader_version else "", progress_callback, log_callback):
                    if log_callback:
                        log_callback(f"Ошибка установки лоадера {loader}")
                    return False
                version_id = f"{loader.lower()}-{loader_version}-{minecraft_version}"
                if log_callback:
                    log_callback(f"Лоадер {loader} установлен.")
                if progress_callback:
                    progress_callback(70, f"Лоадер {loader} установлен...")
            if log_callback:
                log_callback(f"Создание профиля запуска...")
            if progress_callback:
                progress_callback(80, "Создание профиля запуска...")
            # Создаем профиль запуска
            self._create_launch_profile(build_config, instance_dir, version_id)
            if log_callback:
                log_callback(f"Профиль запуска создан.")
            if progress_callback:
                progress_callback(85, "Профиль запуска создан...")
            if log_callback:
                log_callback(f"Создание конфигурации сборки...")
            # Создаем конфигурацию сборки
            self._create_instance_config(build_config, instance_dir)
            if log_callback:
                log_callback(f"Конфигурация сборки создана.")
            if progress_callback:
                progress_callback(95, "Конфигурация сборки создана...")
            if log_callback:
                log_callback(f"Сборка создана успешно!")
            if progress_callback:
                progress_callback(100, "Сборка создана успешно!")
            LogService.log('INFO', f"[BuildManager] Сборка '{build_name}' успешно создана")
            return True
        except Exception as e:
            LogService.log('ERROR', f"[BuildManager] Ошибка создания сборки: {e}", stack=traceback.format_exc())
            if log_callback:
                log_callback(f"Ошибка создания сборки: {e}")
            if progress_callback:
                progress_callback(-1, f"Ошибка: {str(e)}")
            return False
    
    def _sanitize_name(self, name: str) -> str:
        """Очистка названия для использования в пути"""
        import re
        # Заменяем недопустимые символы на подчеркивания
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Убираем лишние пробелы и подчеркивания
        sanitized = re.sub(r'\s+', '_', sanitized.strip())
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized
    
    def _download_minecraft_version(self, version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        if log_callback:
            log_callback(f"Начало загрузки Minecraft версии: {version}")
        LogService.log('INFO', f"Попытка скачать Minecraft версию: {version}")
        LogService.log('INFO', f"[BuildManager] Начало загрузки версии Minecraft: {version}")

        try:
            LogService.log('INFO', f"[BUILD] Начало загрузки Minecraft версии: {version}")
            version_dir = self.versions_path / version
            
            if version_dir.exists():
                if log_callback:
                    log_callback(f"Версия {version} уже существует: {version_dir}")
                LogService.log('INFO', f"Версия {version} уже существует")
                return True
                
            LogService.log('DEBUG', f"[BUILD] Получение информации о версии {version}")
            version_info = self._get_version_info(version)
            
            if not version_info:
                if log_callback:
                    log_callback(f"Не удалось получить информацию о версии: {version}")
                return False
                
            LogService.log('DEBUG', f"[BUILD] Информация о версии получена: {version_info.keys()}")
            
            # Сохраняем JSON-файл версии в папку версии
            try:
                version_dir.mkdir(parents=True, exist_ok=True)  # Гарантируем, что папка существует
                version_json_path = version_dir / f"{version}.json"
                with open(version_json_path, "w", encoding="utf-8") as f:
                    json.dump(version_info, f, indent=2, ensure_ascii=False)
                LogService.log('INFO', f"[BUILD] JSON-файл версии сохранён: {version_json_path}")
                if log_callback:
                    log_callback(f"JSON-файл версии сохранён: {version_json_path}")
            except Exception as e:
                LogService.log('ERROR', f"[BUILD] Ошибка сохранения JSON-файла версии: {e}", stack=traceback.format_exc())
                if log_callback:
                    log_callback(f"Ошибка сохранения JSON-файла версии: {e}")
                return False

            # Скачиваем библиотеки для Vanilla
            libraries = version_info.get("libraries", [])
            if libraries:
                LogService.log('INFO', f"[BUILD] Начинаю скачивание {len(libraries)} библиотек для Vanilla")
                self._download_libraries(libraries, progress_callback, log_callback)
            
            client_url = version_info.get("downloads", {}).get("client", {}).get("url")
            if not client_url:
                if log_callback:
                    log_callback(f"URL клиента не найден для версии {version}")
                LogService.log('ERROR', f"URL клиента не найден для версии {version}")
                return False
                
            LogService.log('INFO', f"[BUILD] URL клиента найден: {client_url}")
            client_path = version_dir / f"{version}.jar"
            if log_callback:
                log_callback(f"Скачивание Minecraft client: {client_url} → {client_path}")
            LogService.log('INFO', f"[download_mc_attempt] filename={version}.jar dst={client_path} src={client_url}")

            try:
                version_dir.mkdir(parents=True, exist_ok=True)
                LogService.log('DEBUG', f"[BUILD] Начало загрузки клиента в: {client_path}")
                response = DownloadService().download_file_sync(client_url, client_path, progress_callback)
                if not response:
                    if log_callback:
                        log_callback(f"Ошибка загрузки Minecraft client: {response}")
                    LogService.log('ERROR', f"[download_mc_error] filename={version}.jar dst={client_path} src={client_url} msg={response}")
                    return False
                if log_callback:
                    log_callback(f"Minecraft client успешно загружен: {client_path}")
                LogService.log('INFO', f"[download_mc] filename={version}.jar dst={client_path} src={client_url}")
            except Exception as e:
                if log_callback:
                    log_callback(f"Ошибка загрузки Minecraft client: {e}")
                LogService.log('ERROR', f"[download_mc_error] filename={version}.jar dst={client_path} src={client_url} msg={e}")
                return False
            LogService.log('INFO', f"[BuildManager] Версия Minecraft {version} успешно загружена")

            # Скачиваем ассеты (assetIndex и объекты)
            self._download_assets(version_info, progress_callback)

            return True
        except Exception as e:
            LogService.log('ERROR', f"[BuildManager] Ошибка загрузки версии Minecraft {version}: {e}", stack=traceback.format_exc())
            if log_callback:
                log_callback(f"Ошибка загрузки версии Minecraft {version}: {e}")
            return False
    
    def _get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Получение информации о версии"""
        try:
            LogService.log('DEBUG', f"[BUILD] Получение информации о версии {version}")
            # Сначала пробуем получить из манифеста
            manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
            LogService.log('DEBUG', f"[BUILD] Загрузка манифеста: {manifest_url}")
            with tempfile.NamedTemporaryFile(delete=False) as tmp_manifest:
                if not DownloadService().download_file_sync(manifest_url, Path(tmp_manifest.name)):
                    LogService.log('ERROR', f"[BUILD] Не удалось скачать манифест версий")
                    return None
                manifest = json.load(open(tmp_manifest.name, 'r', encoding='utf-8'))
            LogService.log('DEBUG', f"[BUILD] Манифест загружен, версий в манифесте: {len(manifest.get('versions', []))}")
            version_info = None
            for v in manifest.get("versions", []):
                if v["id"] == version:
                    LogService.log('DEBUG', f"[BUILD] Найдена версия {version} в манифесте")
                    version_url = v["url"]
                    LogService.log('DEBUG', f"[BUILD] Загрузка детальной информации: {version_url}")
                    with tempfile.NamedTemporaryFile(delete=False) as tmp_version:
                        if not DownloadService().download_file_sync(version_url, Path(tmp_version.name)):
                            LogService.log('ERROR', f"[BUILD] Не удалось скачать детальную информацию о версии")
                            return None
                        version_info = json.load(open(tmp_version.name, 'r', encoding='utf-8'))
                    LogService.log('DEBUG', f"[BUILD] Детальная информация получена: {list(version_info.keys())}")
                    break
            if version_info is None:
                LogService.log('ERROR', f"[BUILD] Версия {version} не найдена в манифесте")
                available_versions = [v["id"] for v in manifest.get("versions", [])[:10]]
                LogService.log('DEBUG', f"[BUILD] Первые 10 доступных версий: {available_versions}")
            return version_info
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Ошибка получения информации о версии {version}: {e}", stack=traceback.format_exc())
            return None
    
    def _download_file(self, url: str, file_path: Path, progress_callback: Optional[Callable] = None, index: Optional[int] = None, total: Optional[int] = None) -> bool:
        try:
            LogService.log('DEBUG', f"[BUILD] Начало загрузки файла: {url} -> {file_path}")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_path.exists():
                LogService.log('DEBUG', f"[BUILD] Файл уже существует: {file_path}")
                return True
            result = DownloadService().download_file_sync(url, file_path, progress_callback)
            if result:
                LogService.log('DEBUG', f"[BUILD] Файл успешно загружен: {file_path}")
            else:
                LogService.log('ERROR', f"[BUILD] Ошибка загрузки файла {url}", stack=traceback.format_exc())
            return result
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Ошибка загрузки файла {url}: {e}", stack=traceback.format_exc())
            return False
    
    def _is_library_needed(self, library: Dict, current_os: str) -> bool:
        """
        Проверяет, нужна ли библиотека для текущей ОС на основе правил
        """
        rules = library.get("rules", [])
        if not rules:
            return True  # если нет правил - нужна всегда
            
        for rule in rules:
            action = rule.get("action", "allow")
            os_rule = rule.get("os", {})
            
            # Проверяем ОС
            if "name" in os_rule:
                rule_os = os_rule["name"]
                if rule_os == current_os:
                    # Библиотека для нашей ОС
                    if action == "allow":
                        return True
                    elif action == "disallow":
                        return False
                else:
                    # Библиотека для другой ОС
                    if action == "allow":
                        return False
                    elif action == "disallow":
                        return True
                        
            # Проверяем архитектуру (если указана)
            if "arch" in os_rule:
                import platform
                current_arch = platform.machine().lower()
                rule_arch = os_rule["arch"]
                
                if current_arch == rule_arch:
                    if action == "allow":
                        return True
                    elif action == "disallow":
                        return False
                else:
                    if action == "allow":
                        return False
                    elif action == "disallow":
                        return True
        
        # Если правила не сработали - библиотека нужна
        return True

    def _download_libraries(self, libraries: List[Dict], progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        try:
            LogService.log('DEBUG', f"[BUILD] Начало загрузки библиотек, всего: {len(libraries)}")
            if log_callback:
                log_callback(f"Начинаем загрузку {len(libraries)} библиотек")
            
            # Определяем текущую ОС
            import platform
            current_os = platform.system().lower()
            if current_os == "windows":
                current_os = "windows"
            elif current_os == "linux":
                current_os = "linux" 
            elif current_os == "darwin":
                current_os = "osx"
            else:
                current_os = "windows"  # fallback
                
            LogService.log('DEBUG', f"[BUILD] Текущая ОС: {current_os}")
            
            # Подготавливаем список файлов для скачивания
            files_to_download = []
            for library in libraries:
                try:
                    # Проверяем правила библиотеки
                    if not self._is_library_needed(library, current_os):
                        LogService.log('DEBUG', f"[BUILD] Библиотека не нужна для {current_os}: {library.get('name', 'unknown')}")
                        continue
                        
                    artifact = library.get("downloads", {}).get("artifact")
                    if not artifact:
                        LogService.log('DEBUG', f"[BUILD] Библиотека без артефакта: {library}")
                        continue
                        
                    url = artifact.get("url")
                    path = artifact.get("path")
                    
                    if url and path:
                        lib_path = self.libraries_path / path
                        files_to_download.append((url, lib_path))
                    else:
                        LogService.log('WARNING', f"[BUILD] Библиотека без URL или пути: {library}")
                        
                except Exception as e:
                    LogService.log('ERROR', f"[BUILD] Ошибка при обработке библиотеки: {e}", stack=traceback.format_exc())
                    continue
            
            if not files_to_download:
                LogService.log('INFO', f"[BUILD] Нет файлов для скачивания")
                if log_callback:
                    log_callback("Нет файлов для скачивания")
                return True
            
            # Используем многопоточное скачивание
            download_service = DownloadService(self.config_manager)
            
            def progress_wrapper(current: int, total: int, message: str):
                if progress_callback:
                    try:
                        progress = 25 + int((current / total) * 10)  # 25-35%
                        progress_callback(progress, f"Загрузка библиотек: {current}/{total} - {message}")
                    except Exception as e:
                        LogService.log('ERROR', f"[BUILD] Ошибка в progress_callback: {e}", stack=traceback.format_exc())
            
            def log_wrapper(message: str):
                if log_callback:
                    try:
                        log_callback(message)
                    except Exception as e:
                        LogService.log('ERROR', f"[BUILD] Ошибка в log_callback: {e}", stack=traceback.format_exc())
                LogService.log('INFO', f"[BUILD] {message}")
            
            result = download_service.download_multiple_files(
                files_to_download, 
                progress_callback=progress_wrapper,
                log_callback=log_wrapper
            )
            
            LogService.log('INFO', f"[BUILD] Загрузка библиотек завершена: {'успешно' if result else 'с ошибками'}")
            return result
            
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Критическая ошибка при загрузке библиотек: {e}", stack=traceback.format_exc())
            if log_callback:
                log_callback(f"Критическая ошибка при загрузке библиотек: {e}")
            return False
    
    def _download_assets(self, version_info: Dict[str, Any], progress_callback: Optional[Callable] = None) -> bool:
        try:
            assets = version_info.get("assetIndex", {})
            url = assets.get("url")
            id_ = assets.get("id")
            if not url or not id_:
                return False
            assets_dir = self.assets_path / "indexes"
            assets_dir.mkdir(parents=True, exist_ok=True)
            asset_path = assets_dir / f"{id_}.json"
            try:
                response = DownloadService().download_file_sync(url, asset_path, progress_callback)
                if not response:
                    LogService.log('ERROR', f"[BUILD] Не удалось скачать ассет индекс {id_}", stack=traceback.format_exc())
                    return False
                # --- СКАЧИВАНИЕ САМИХ АССЕТОВ ---
                import json
                with open(asset_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                objects = index_data.get("objects", {})
                files_to_download = []
                for obj_name, obj_info in objects.items():
                    hash_ = obj_info.get("hash")
                    if not hash_ or len(hash_) < 2:
                        continue
                    url = f"https://resources.download.minecraft.net/{hash_[:2]}/{hash_}"
                    dest = self.assets_path / "objects" / hash_[:2] / hash_
                    files_to_download.append((url, dest))
                if files_to_download:
                    LogService.log('INFO', f"[BUILD] Начинаю скачивание {len(files_to_download)} ассетов")
                    def asset_progress_wrapper(current, total, message):
                        if progress_callback:
                            percent = int((current / total) * 100)
                            progress_callback(percent, message)
                    DownloadService().download_multiple_files(files_to_download, asset_progress_wrapper)
                return True
            except Exception as e:
                LogService.log('ERROR', f"[BUILD] Ошибка при скачивании ассетов: {e}", stack=traceback.format_exc())
                return False
        except Exception as e:
            return False
    
    def _install_loader(self, minecraft_version: str, loader: str, loader_version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Начинаю установку лоадера: {loader} {loader_version} для {minecraft_version}")
        try:
            if loader == "Fabric":
                return self._install_fabric(minecraft_version, loader_version, progress_callback, log_callback)
            elif loader == "Forge":
                return self._install_forge(minecraft_version, loader_version, progress_callback, log_callback)
            elif loader == "Quilt":
                return self._install_quilt(minecraft_version, loader_version, progress_callback, log_callback)
            elif loader == "NeoForge":
                return self._install_neoforge(minecraft_version, loader_version, progress_callback, log_callback)
            elif loader in ["Paper", "Purpur"]:
                return self._install_server_jar(minecraft_version, loader, loader_version, progress_callback, log_callback)
            else:
                return True
                
        except Exception as e:
            return False
    
    def _install_fabric(self, minecraft_version: str, loader_version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Установка Fabric: {minecraft_version} {loader_version}")
        try:
            if log_callback:
                log_callback(f"Установка Fabric: {minecraft_version} {loader_version}")
            if progress_callback:
                try:
                    progress_callback(45, "Установка Fabric...")
                except Exception as e:
                    LogService.log('ERROR', f"[BUILD] Ошибка в progress_callback при установке Fabric: {e}", stack=traceback.format_exc())
            
            # Получаем URL для Fabric
            url = f"https://meta.fabricmc.net/v2/versions/loader/{minecraft_version}/{loader_version}/profile/json"
            LogService.log('DEBUG', f"[BUILD] Fabric URL: {url}")
            
            # Загружаем профиль Fabric
            try:
                response = DownloadService().download_file_sync(url, self.temp_path / f"fabric-loader-{loader_version}-{minecraft_version}.json", progress_callback)
                if not response:
                    LogService.log('ERROR', f"[BUILD] Не удалось скачать профиль Fabric", stack=traceback.format_exc())
                    return False
                fabric_profile = json.load(open(self.temp_path / f"fabric-loader-{loader_version}-{minecraft_version}.json", 'r', encoding='utf-8'))
                LogService.log('DEBUG', f"[BUILD] Fabric профиль получен успешно")
            except Exception as e:
                LogService.log('ERROR', f"[BUILD] Ошибка получения Fabric профиля: {e}", stack=traceback.format_exc())
                return False
            
            # Сохраняем профиль
            try:
                profile_name = f"fabric-loader-{loader_version}-{minecraft_version}"
                profile_path = self.versions_path / profile_name / f"{profile_name}.json"
                profile_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(fabric_profile, f, indent=2)
                LogService.log('DEBUG', f"[BUILD] Fabric профиль сохранен: {profile_path}")
            except Exception as e:
                LogService.log('ERROR', f"[BUILD] Ошибка сохранения Fabric профиля: {e}", stack=traceback.format_exc())
                return False
            
            # Загружаем библиотеки Fabric
            try:
                libraries = fabric_profile.get("libraries", [])
                LogService.log('DEBUG', f"[BUILD] Найдено библиотек Fabric: {len(libraries)}")
                
                if not self._download_libraries(libraries, progress_callback, log_callback):
                    LogService.log('ERROR', f"[BUILD] Ошибка загрузки библиотек Fabric", stack=traceback.format_exc())
                    return False
                    
                LogService.log('INFO', f"[BUILD] Fabric успешно установлен")
                return True
                
            except Exception as e:
                LogService.log('ERROR', f"[BUILD] Ошибка загрузки библиотек Fabric: {e}", stack=traceback.format_exc())
                return False
            
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Критическая ошибка при установке Fabric: {e}", stack=traceback.format_exc())
            return False
    
    def _install_forge(self, minecraft_version: str, forge_version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Установка Forge: {minecraft_version} {forge_version}")
        try:
            if log_callback:
                log_callback(f"Установка Forge: {minecraft_version} {forge_version}")
            if progress_callback:
                progress_callback(45, "Установка Forge...")
            
            # Получаем URL для Forge
            url = f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{minecraft_version}-{forge_version}/forge-{minecraft_version}-{forge_version}-installer.jar"
            
            # Скачиваем установщик
            installer_path = self.temp_path / "installers" / f"forge-{minecraft_version}-{forge_version}-installer.jar"
            if not self._download_file(url, installer_path, progress_callback):
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def _install_quilt(self, minecraft_version: str, loader_version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Установка Quilt: {minecraft_version} {loader_version}")
        try:
            if log_callback:
                log_callback(f"Установка Quilt: {minecraft_version} {loader_version}")
            if progress_callback:
                progress_callback(45, "Установка Quilt...")
            
            # Получаем URL для Quilt
            url = f"https://meta.quiltmc.org/v3/versions/loader/{minecraft_version}/{loader_version}/profile/json"
            
            # Загружаем профиль Quilt
            response = DownloadService().download_file_sync(url, self.temp_path / f"quilt-loader-{loader_version}-{minecraft_version}.json", progress_callback)
            if not response:
                LogService.log('ERROR', f"[BUILD] Не удалось скачать профиль Quilt", stack=traceback.format_exc())
                return False
            quilt_profile = json.load(open(self.temp_path / f"quilt-loader-{loader_version}-{minecraft_version}.json", 'r', encoding='utf-8'))
            
            # Сохраняем профиль
            profile_name = f"quilt-loader-{loader_version}-{minecraft_version}"
            profile_path = self.versions_path / profile_name / f"{profile_name}.json"
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(quilt_profile, f, indent=2)
            
            # Загружаем библиотеки Quilt
            libraries = quilt_profile.get("libraries", [])
            if not self._download_libraries(libraries, progress_callback, log_callback):
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def _install_neoforge(self, minecraft_version: str, neoforge_version: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Установка NeoForge: {minecraft_version} {neoforge_version}")

        try:
            if log_callback:
                log_callback(f"Установка NeoForge: {minecraft_version} {neoforge_version}")
            if progress_callback:
                progress_callback(45, "Установка NeoForge...")
            
            # Получаем URL для NeoForge
            url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
            
            # Скачиваем установщик
            installer_path = self.temp_path / "installers" / f"neoforge-{neoforge_version}-installer.jar"
            if not self._download_file(url, installer_path, progress_callback):
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def _install_server_jar(self, minecraft_version: str, server_type: str, build_number: str, progress_callback: Optional[Callable] = None, log_callback: Optional[Callable] = None) -> bool:
        LogService.log('INFO', f"Установка серверного JAR: {server_type} {build_number} для {minecraft_version}")

        try:
            if log_callback:
                log_callback(f"Установка серверного JAR: {server_type} {build_number} для {minecraft_version}")
            if progress_callback:
                progress_callback(45, f"Установка {server_type}...")
            if server_type == "Paper":
                url = f"https://api.papermc.io/v2/projects/paper/versions/{minecraft_version}/builds/{build_number}/downloads/paper-{minecraft_version}-{build_number}.jar"
            elif server_type == "Purpur":
                url = f"https://api.purpurmc.org/v2/purpur/{minecraft_version}/{build_number}/download"
            else:
                return False
            server_jar_path = self.versions_path / f"{server_type.lower()}-{minecraft_version}-{build_number}" / f"{server_type.lower()}-{minecraft_version}-{build_number}.jar"
            server_jar_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                response = DownloadService().download_file_sync(url, server_jar_path, progress_callback)
                if not response:
                    LogService.log('ERROR', f"[BUILD] Не удалось скачать серверный JAR {server_type} {build_number}", stack=traceback.format_exc())
                    return False
                return True
            except Exception as e:
                return False
        except Exception as e:
            return False
    
    def _create_launch_profile(self, build_config: Dict[str, Any], instance_dir: Path, version_id: str):
        try:
            profile_data = {
                "name": build_config.get("name"),
                "type": "custom",
                "created": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lastUsed": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "lastVersionId": version_id,
                "gameDir": str(instance_dir / ".minecraft"),
                "javaDir": self.config_manager.get("java_path", "auto"),
                "javaArgs": f"-Xmx{self.config_manager.get('max_memory', 2048)}M -Xms{self.config_manager.get('min_memory', 512)}M"
            }
            
            # Сохраняем профиль
            profiles_file = self.config_path / "launcher_profiles.json"
            
            if profiles_file.exists():
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
            else:
                profiles = {"profiles": {}}
            
            profile_name = self._sanitize_name(build_config.get("name", "Unnamed"))
            profiles["profiles"][profile_name] = profile_data
            
            with open(profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            pass
    
    def _create_instance_config(self, build_config: Dict[str, Any], instance_dir: Path):
        try:
            config_data = {
                "name": build_config.get("name"),
                "minecraft_version": build_config.get("minecraft_version"),
                "loader": build_config.get("loader"),
                "loader_version": build_config.get("loader_version"),
                "created": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "last_used": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "notes": build_config.get("notes", ""),
            }
            
            config_file = instance_dir / "instance.cfg"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            pass
    
    def get_builds(self) -> List[Dict[str, Any]]:
        """Получение списка созданных сборок"""
        try:
            builds = []
            if not self.instances_path.exists():
                LogService.log('DEBUG', "[BUILD] Папка instances не существует")
                return builds
                
            for instance_dir in self.instances_path.iterdir():
                try:
                    if not instance_dir.is_dir():
                        continue
                        
                    config_file = instance_dir / "instance.cfg"
                    if not config_file.exists():
                        LogService.log('WARNING', f"[BUILD] Конфигурационный файл не найден: {config_file}")
                        continue
                        
                    # Безопасное чтение конфигурации
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                    except (json.JSONDecodeError, UnicodeDecodeError, IOError) as e:
                        LogService.log('ERROR', f"[BUILD] Ошибка чтения конфигурации {config_file}: {e}", stack=traceback.format_exc())
                        continue
                        
                    build_name = config.get("name", instance_dir.name)
                    if not build_name:
                        LogService.log('WARNING', f"[BUILD] Пустое имя сборки в {instance_dir}")
                        continue
                        
                    state_info = self.get_build_state(build_name)
                    build_info = {
                        "name": build_name,
                        "path": str(instance_dir),
                        "created": config.get("created", instance_dir.stat().st_ctime),
                        "last_used": config.get("last_used", instance_dir.stat().st_mtime),
                        "minecraft_version": config.get("minecraft_version", "Unknown"),
                        "loader": config.get("loader", "Unknown"),
                        "notes": config.get("notes", ""),
                        "status": state_info["status"],
                        "progress": state_info["progress"],
                        "message": state_info["message"]
                    }
                    builds.append(build_info)
                    LogService.log('DEBUG', f"[BUILD] Добавлена сборка: {build_name}")
                    
                except Exception as e:
                    LogService.log('ERROR', f"[BUILD] Ошибка обработки сборки {instance_dir}: {e}", stack=traceback.format_exc())
                    continue
                    
            LogService.log('DEBUG', f"[BUILD] Всего найдено сборок: {len(builds)}")
            return builds
            
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Критическая ошибка при получении списка сборок", stack=traceback.format_exc())
            return []
    
    def delete_build(self, build_name: str) -> bool:
        """Удаление сборки"""
        try:
            instance_dir = self.instances_path / self._sanitize_name(build_name)
            
            if instance_dir.exists():
                shutil.rmtree(instance_dir)
                # Очищаем состояние сборки
                self.clear_build_state(build_name)
                LogService.log('INFO', f"[BUILD] Сборка удалена: {build_name}")
                return True
            
            LogService.log('WARNING', f"[BUILD] Не удалось найти сборку для удаления: {build_name}")
            return False
            
        except Exception as e:
            LogService.log('ERROR', f"[BUILD] Ошибка при удалении сборки {build_name}", stack=traceback.format_exc())
            return False
    
    def get_build_logs(self, build_name: str) -> List[Dict[str, Any]]:
        """Получение логов сборки"""
        try:
            instance_dir = self.instances_path / self._sanitize_name(build_name)
            logs_dir = instance_dir / ".minecraft" / "logs"
            
            logs = []
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log"):
                    log_info = {
                        "name": log_file.name,
                        "path": str(log_file),
                        "size": log_file.stat().st_size,
                        "modified": log_file.stat().st_mtime
                    }
                    logs.append(log_info)
            
            return logs
            
        except Exception as e:
            return []
    
    def is_build_ready(self, build_name: str) -> bool:
        """Проверка готовности сборки к запуску"""
        try:
            instance_dir = self.instances_path / self._sanitize_name(build_name)
            
            # Проверяем существование директории
            if not instance_dir.exists():
                return False
            
            # Проверяем наличие конфигурации
            config_file = instance_dir / "instance.cfg"
            if not config_file.exists():
                return False
            
            # Проверяем наличие .minecraft папки
            minecraft_dir = instance_dir / ".minecraft"
            if not minecraft_dir.exists():
                return False
            
            # Проверяем состояние сборки
            state_info = self.get_build_state(build_name)
            return state_info["status"] == BuildStatus.READY
            
        except Exception as e:
            return False
    
    def launch_build(self, build_name: str) -> bool:
        """Запуск сборки"""
        try:
            if not self.is_build_ready(build_name):
                return False
            
            # Здесь будет логика запуска Minecraft
            # Пока что просто возвращаем True
            return True
            
        except Exception as e:
            return False 

    def set_build_state(self, build_name: str, status: BuildStatus, progress: int = 0, message: str = ""):
        with self._state_lock:
            self.build_states[build_name] = {
                "status": status,
                "progress": progress,
                "message": message
            }

    def get_build_state(self, build_name: str) -> dict:
        with self._state_lock:
            return self.build_states.get(build_name, {
                "status": BuildStatus.UNKNOWN,
                "progress": 0,
                "message": ""
            })

    def clear_build_state(self, build_name: str):
        with self._state_lock:
            if build_name in self.build_states:
                del self.build_states[build_name] 