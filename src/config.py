# ----------------------------------------------------------------------------#
# Embedded libraries                                                          #
# ----------------------------------------------------------------------------#
import sys
from pathlib import Path

# ----------------------------------------------------------------------------#
# External libraries                                                          #
# ----------------------------------------------------------------------------#
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ----------------------------------------------------------------------------#
# Application code                                                            #
# ----------------------------------------------------------------------------#


class ServerConfig(BaseSettings):
    """
    Конфигурация uvicorn.

    Attributes:
        host: Хост для запуска сервера.
        port: Порт для запуска сервера.
        is_reload: Включает автоматическую перезагрузку сервера.
        access_log: Включает журналирование запросов.
    """

    model_config = SettingsConfigDict(env_prefix="SERVER_")
    host: str = "127.0.0.1"
    port: int = 8000
    is_reload: bool = not getattr(sys, "frozen", False)
    access_log: bool = not getattr(sys, "frozen", False)

    @model_validator(mode="before")
    @classmethod
    def detect_docker_env(cls, data: dict) -> dict:
        """
        Настраивает параметры сервера при запуске в Docker-контейнере.

        При наличии файла ``/.dockerenv`` сервер начинает прослушивать
        все сетевые интерфейсы, а автоматическая перезагрузка отключается.
        Значения, переданные явно в ``data``, имеют приоритет над настройками
        Docker-окружения.

        Args:
            data: Исходные параметры конфигурации сервера.

        Returns:
            Словарь параметров конфигурации с настройками,
            соответствующими среде выполнения.
        """
        if Path("/.dockerenv").exists():
            if "host" not in data:
                data["host"] = "0.0.0.0"
            if "is_reload" not in data:
                data["is_reload"] = False
        return data


class LetterFilterModel(BaseSettings):
    """
    Модель параметров фильтрации слов.

    Args:
        word_length: длина искомого слова.
        letters_excluded: символы, которых нет в слове.
        letters_included: символы, которые есть в слове.
        letters_excluded_pos: исключённые символы по позициям.
        letters_fixed_pos: символы на фиксированных позициях. Если символ позиции неизвестен, указывается "+".
        is_save_file: если ``True``, результат сохраняется в текстовый файл.
        сохранять ли результат фильтрации в текстовый файл.
        is_output_terminal: булевское значение True/False, отвечающее на вопрос
        выводить ли результат фильтрации в терминал.
    """

    model_config = SettingsConfigDict(env_prefix="LFM_")
    word_length: int = 5
    letters_excluded: str = "лт"
    letters_included: str = "аня"
    letters_excluded_pos: list[str] = ["а", "", "б", "", ""]
    letters_fixed_pos: list[str] | str = "+а+н+"
    is_save_file: bool = True
    is_output_terminal: bool = False


class Config(BaseSettings):
    """
    Конфигурация приложения Search Word.

    Настройки загружаются из переменных окружения с префиксом ``APP_``.
    Если переменная окружения не задана, используется значение по умолчанию.

    Attributes:
        log_level: Уровень журналирования приложения.
        report_line_limit: Максимальная длина строки отчёта.
        is_open_webbrowser: Открывать ли веб-интерфейс в браузере
            после запуска сервера.
        data_folder: Каталог с файлами исходных данных.
        encoding_ru_words: Кодировка файла со словарём.
        file_ru_words: Имя файла со словарём русских существительных.
        pattern_ru_letters: Регулярное выражение для очистки и проверки
            русскоязычных символов.
        report_folder: Каталог для сохранения отчётов.
        report_file: Имя файла отчёта.
    """

    model_config = SettingsConfigDict(env_prefix="APP_")
    log_level: int = 10
    report_line_limit: int = 70
    is_open_webbrowser: bool = True
    data_folder: str = "src/data"
    encoding_ru_words: str = "utf-8"
    file_ru_words: str = "russian_nouns.txt"
    pattern_ru_letters: str = r"[^а-яё-]"
    report_folder: str = "report"
    report_file: str = "Found words.txt"

    @property
    def path_file_ru_words(self) -> Path:
        """
        Возвращает путь к файлу словаря.

        Путь формируется из каталога данных ``data_folder`` и имени файла
        ``file_ru_words``.

        Returns:
            Путь к файлу словаря русских существительных.
        """
        return Path(self.data_folder) / self.file_ru_words

    @property
    def path_report_folder(self) -> Path:
        """
        Возвращает абсолютный путь к каталогу отчётов.

        Каталог вычисляется относительно текущей рабочей директории процесса.

        Returns:
            Абсолютный путь к каталогу отчётов.
        """
        return Path.cwd() / self.report_folder

    @property
    def path_report_file(self) -> Path:
        """
        Возвращает путь к файлу отчёта.

        Путь формируется из каталога отчётов ``path_report_folder`` и имени
        файла ``report_file``. Каталог и файл не создаются при обращении
        к свойству.

        Returns:
            Путь к файлу отчёта.
        """
        return self.path_report_folder / self.report_file

    @property
    def is_docker(self) -> bool:
        """
        Определяет, запущено ли приложение в Docker-контейнере.

        Проверка выполняется по наличию стандартного файла ``/.dockerenv``.

        Returns:
            ``True``, если приложение запущено в Docker-контейнере,
            иначе ``False``.
        """
        return Path("/.dockerenv").exists()
