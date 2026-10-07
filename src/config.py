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
        letters_excluded: символы, которые гарантированно отсутствуют в слове.
        letters_included: символы, которые гарантированно присутствуют в слове.
        letters_excluded_pos: для каждой позиции — символы, которые не могут находиться в этой позиции.
        letters_fixed_pos: для каждой позиции — символ, который должен находиться в этой позиции, либо пустая строка, если позиция не фиксирована.
        is_save_file: булевское значение True/False, отвечающее на вопрос
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
    Конфигурация приложения.
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
        return Path(self.data_folder) / self.file_ru_words

    @property
    def path_report_folder(self) -> Path:
        return Path.cwd() / self.report_folder

    @property
    def path_report_file(self) -> Path:
        return self.path_report_folder / self.report_file

    @property
    def is_docker(self) -> bool:
        return Path("/.dockerenv").exists()
