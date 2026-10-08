# ----------------------------------------------------------------------------#
# Embedded libraries                                                          #
# ----------------------------------------------------------------------------#
from asyncio import run as async_run

# ----------------------------------------------------------------------------#
# Project modules                                                             #
# ----------------------------------------------------------------------------#
from utilities.basic_utilities_project import add_workdir_in_PATH

add_workdir_in_PATH()
from app.search_words import ApplicationService as app
from src.web.router import start_web_server

# ----------------------------------------------------------------------------#
# Application code                                                            #
# ----------------------------------------------------------------------------#

app_report = app.ReportService()
app_clear = app.ClearReportService()


def start_web() -> None:
    """
    Запускает приложение.

    Notes:
        Функция инициализирует и запускает веб-сервер приложения.
    """
    start_web_server()


def start_console() -> None:
    """
    Запускает приложение с консольным вводом.

    Notes:
        Функция инициализирует и запускает приложение с консольным вводом.
    """
    app_report.generate_report(is_interactive=True)


def start_default() -> None:
    """
    Запускает приложение с фильтрами по умолчанию.

    Notes:
        Функция инициализирует и запускает приложение с фильтрами из файла
        конфигурации. Результат поиска слов сохраняется в текстовый файл отчета.
    """
    app_report.generate_report()


def start_clear() -> None:
    """
    Запускает очищение директории отчётов.

    Notes:
        Запускает сервис безопасной очистки директории отчётов от файлов и папок.
    """
    async_run(app_clear.cleanup())


if __name__ == "__main__":
    start_web()
