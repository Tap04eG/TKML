import subprocess
import os
import uuid
from typing import List, Optional, Callable, Union

class MinecraftRunner:
    @staticmethod
    def run(
        java_path: str,
        main_class: str,
        classpath: str,
        natives_dir: str,
        game_dir: Union[str, os.PathLike],
        assets_dir: str,
        assets_index: str,
        username: str,
        uuid_: Optional[str] = None,
        width: int = 854,
        height: int = 480,
        extra_jvm_args: Optional[List[str]] = None,
        extra_game_args: Optional[List[str]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        max_memory: int = 2048
    ) -> bool:
        """
        Запускает Minecraft с заданными параметрами.
        
        :param java_path: Путь к java.exe
        :param main_class: Главный класс Minecraft (обычно net.minecraft.client.main.Main)
        :param classpath: Classpath (все jar-файлы через os.pathsep)
        :param natives_dir: Папка с natives
        :param game_dir: Рабочая папка сборки (строка или Path)
        :param assets_dir: Папка assets
        :param assets_index: ID индекса assets
        :param username: Ник игрока (строка)
        :param uuid_: UUID игрока (если None — генерируется offline uuid)
        :param width: Ширина окна
        :param height: Высота окна
        :param extra_jvm_args: Дополнительные JVM-аргументы
        :param extra_game_args: Дополнительные игровые аргументы
        :param log_callback: Функция для логирования строк
        :param max_memory: Максимальный объём памяти (МБ)
        :return: True если процесс завершился успешно, иначе False
        """
        # Проверка типа username
        username = str(username)
        # Проверка типа game_dir
        if not isinstance(game_dir, str):
            game_dir = str(game_dir)
        if uuid_ is None:
            uuid_ = str(uuid.uuid3(uuid.NAMESPACE_DNS, username))
        if extra_jvm_args is None:
            extra_jvm_args = []
        if extra_game_args is None:
            extra_game_args = []

        jvm_args = [
            f"-Djava.library.path={natives_dir}",
            f"-Djna.tmpdir={natives_dir}",
            f"-cp", classpath,
            f"-Xmx{max_memory}M",
        ] + extra_jvm_args

        # Если extra_game_args предоставлены, используем их напрямую
        # Иначе создаем базовые аргументы
        if extra_game_args:
            game_args = extra_game_args
        else:
            game_args = [
                "--username", username,
                "--version", assets_index,
                "--gameDir", game_dir,
                "--assetsDir", assets_dir,
                "--assetIndex", assets_index,
                "--uuid", uuid_,
                "--accessToken", "0",
                "--userType", "legacy",
                "--width", str(width),
                "--height", str(height),
            ]

        cmd = [java_path] + jvm_args + [main_class] + game_args
        if log_callback:
            log_callback(f"Запуск: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(cmd, cwd=game_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.stdout is not None:
                for line in proc.stdout:
                    if log_callback:
                        log_callback(line.rstrip())
            if proc.stderr is not None:
                for line in proc.stderr:
                    if log_callback:
                        log_callback(line.rstrip())
            proc.wait()
            if log_callback:
                if proc.returncode == 0:
                    log_callback('Minecraft успешно запущен (или завершён без ошибок).')
                else:
                    log_callback(f'Процесс завершился с ошибкой (код {proc.returncode})')
            return proc.returncode == 0
        except Exception as e:
            if log_callback:
                log_callback(f'Ошибка запуска Minecraft: {e}')
            return False 