# ----------------------------------------------------------------------------#
# Embedded libraries                                                          #
# ----------------------------------------------------------------------------#
from asyncio import create_task as a_create_task
from asyncio import get_running_loop as a_get_running_loop
from asyncio import sleep as a_sleep
from contextlib import asynccontextmanager
from enum import Enum
from json import dumps as json_dumps
from typing import Annotated
from webbrowser import open as web_open

# ----------------------------------------------------------------------------#
# External libraries                                                          #
# ----------------------------------------------------------------------------#
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer

# ----------------------------------------------------------------------------#
# Project modules                                                             #
# ----------------------------------------------------------------------------#
from app.search_words import ApplicationService as app
from src.config import Config, LetterFilterModel, ServerConfig
from src.logs import SmartLogger
from src.utilities import Utilities as uts

# ----------------------------------------------------------------------------#
# Application code                                                            #
# ----------------------------------------------------------------------------#

app_report = app.ReportService()
app_clear = app.ClearReportService()
cfg = Config()
lfm = LetterFilterModel()
log: SmartLogger = SmartLogger()
log.setLevel(cfg.log_level)
templates = Jinja2Templates(
    directory=uts.resource_path(relative_path="src/templates")
)
sc: ServerConfig = ServerConfig()
uvicorn_config: UvicornConfig = UvicornConfig(
    f"{__name__}:web",
    host=sc.host,
    port=sc.port,
    reload=sc.is_reload,
    access_log=sc.access_log,
)
uvicorn_server: UvicornServer = UvicornServer(uvicorn_config)


async def open_browser() -> None:
    """
    Открывает веб-интерфейс приложения в браузере.

    Функция ожидает запуска сервера, после чего открывает URL приложения
    в системном браузере. Используется только при запуске не в Docker-контейнере.
    """
    sc = ServerConfig()
    await a_sleep(1.5)
    loop = a_get_running_loop()
    loop.run_in_executor(None, web_open, f"http://{sc.host}:{sc.port}")


@asynccontextmanager
async def lifespan(web: FastAPI) -> None:
    """
    Управляет жизненным циклом FastAPI-приложения.

    При запуске записывает сообщение в журнал и при необходимости открывает
    веб-интерфейс в браузере. При завершении выполняет небольшую задержку,
    чтобы корректно завершить фоновые операции.

    Args:
        web: Экземпляр FastAPI-приложения.

    Yields:
        Управление приложению на время его работы.

    Returns:
        Ничего не возвращает после завершения жизненного цикла приложения.
    """
    is_open_webbrowser = cfg.is_open_webbrowser
    is_docker = cfg.is_docker

    log.info(msg="🚀 Сервер запускается...", pretty=True)
    if is_open_webbrowser and not is_docker:
        a_create_task(open_browser())
    yield

    log.info(msg="🛑 Сервер останавливается...", pretty=True)
    await a_sleep(1.5)


web = FastAPI(
    title="📜 Words search API",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "tryItOutEnabled": True,
        "filter": True,
        "displayRequestDuration": True,
    },
    lifespan=lifespan,
)

web.mount(
    path="/static",
    app=StaticFiles(directory=uts.resource_path(relative_path="src/static")),
    name="static",
)


class IsYesOrNo(str, Enum):
    """
    Перечисление вариантов ответа «да» или «нет».
    """
    YES = "✔️ Да"
    NO = "❌ Нет"


class SearchQuery(LetterFilterModel):
    """
    Модель параметров поиска для веб-формы.
    """

    is_save_file: bool = False
    is_web_save_file: IsYesOrNo = IsYesOrNo.NO

    @staticmethod
    def _clear_spaces(check_clear: list[str] | str) -> list[str] | str:
        """
        Удаляет пробелы из строки или элементов списка строк.

        Args:
            check_clear: Строка или список строк, из которых нужно
                удалить пробелы.

        Returns:
            Обработанная строка или список строк без пробелов.
        """
        if isinstance(check_clear, str):
            return "".join(check_clear.split())
        return [item.replace(" ", "") for item in check_clear]

    @classmethod
    async def _search_query_form(
        cls,
        is_web_save_file: Annotated[
            IsYesOrNo,
            Query(
                alias="saving file",
                description="💾 Сохранить файл.",
                examples=[IsYesOrNo.NO],
            ),
        ],
        word_length: Annotated[
            int,
            Query(
                alias="word length",
                description="📙 Количество символов слова.",
                examples=3,
            ),
        ],
        letters_included: Annotated[
            str,
            Query(
                alias="included",
                description="✔️ Символы, которые есть в слове.",
                examples="",
            ),
        ] = "",
        letters_excluded: Annotated[
            str,
            Query(
                alias="excluded",
                description="❌ Символы, которых нет в слове.",
                examples="",
            ),
        ] = "",
        letters_fixed_pos: Annotated[
            str,
            Query(
                alias="fixed position",
                description='✔️ Символы на фиксированных позициях. \n✔️ Если символ позиции неизвестен, укажите "+".',
                examples="",
            ),
        ] = "",
        letters_excluded_pos: Annotated[
            list[str] | None,
            Query(
                alias="excluded position",
                description="❌ Исключённые символы по позициям. \n❌ Если символ позиции неизвестен, укажите пробел.",
                examples=[[""]],
            ),
        ] = None,
    ) -> SearchQuery:
        """
        Собирает и нормализует параметры поиска из HTTP-запроса.

        Пробелы удаляются из строковых параметров. Если параметры
        исключённых символов по позициям отсутствуют, используется список
        с одним пустым элементом.

        Args:
            is_web_save_file: Указывает, нужно ли сохранить результат
                поиска в файл.
            word_length: Требуемая длина слова.
            letters_included: Символы, которые есть в слове.
            letters_excluded: Символы, которых нет в слове.
            letters_fixed_pos: Символы на фиксированных позициях.
                Для неизвестной позиции используется символ ``+``.
            letters_excluded_pos: Списки символов, исключенных на
                фиксированных позициях.

        Returns:
            Экземпляр модели ``SearchQuery`` с обработанными параметрами.
        """
        letters_excluded = cls._clear_spaces(check_clear=letters_excluded)
        letters_included = cls._clear_spaces(check_clear=letters_included)
        letters_excluded_pos = cls._clear_spaces(
            check_clear=(
                letters_excluded_pos if letters_excluded_pos is not None else [""]
            )
        )
        letters_fixed_pos = cls._clear_spaces(check_clear=letters_fixed_pos)

        return cls(
            word_length=word_length,
            letters_excluded=letters_excluded,
            letters_included=letters_included,
            letters_excluded_pos=letters_excluded_pos,
            letters_fixed_pos=letters_fixed_pos,
            is_web_save_file=is_web_save_file,
        )


@web.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """
    Перенаправляет пользователя на HTML-форму поиска слов.

    Returns:
        HTTP-редирект на страницу ``/search-word/new``.
    """
    return RedirectResponse(
        url="/search-word/new", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@web.get("/search-word/new", include_in_schema=False)
async def new_search(request: Request) -> Response:
    """
    Отображает HTML-форму поиска слов.

    Args:
        request: Текущий HTTP-запрос.

    Returns:
        HTML-страница с формой параметров поиска.
    """
    return templates.TemplateResponse(
        request=request,
        name="search-word-form.html",
        status_code=status.HTTP_200_OK,
    )


@web.get(
    "/shutdown",
    description="Посылает запрос на остановку веб-сервера.",
    tags=["⚙️ Конфигурация"],
    summary="Остановить веб-сервер",
)
async def shutdown(request: Request) -> Response:
    """
    Отправляет текущему процессу сигнал остановки веб-сервера.

    Args:
        request: Текущий HTTP-запрос. Используется для выбора формата
            ответа: HTML или JSON.

    Returns:
        HTML-страница или JSON-ответ с подтверждением отправки сигнала.
    """
    uvicorn_server.should_exit = True
    log.info(msg="Запрос на остановку сервера отправлен...", pretty=True)
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request=request,
            name="shutdown.html",
            status_code=status.HTTP_202_ACCEPTED,
        )
    return JSONResponse(
        content={
            "status": "ok",
            "message": "Запрос на остановку сервера отправлен",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@web.get("/cleanup", include_in_schema=False)
async def get_cleanup(request: Request) -> Response:
    """
     Отображает HTML-форму очистки папки отчётов.

    Args:
        request: Текущий HTTP-запрос.

    Returns:
        HTML-страница с формой запуска очистки отчётов.
    """
    return templates.TemplateResponse(
        request=request,
        name="cleanup.html",
        status_code=status.HTTP_200_OK,
    )


@web.post(
    "/cleanup",
    description="Очищает папку для отчетов от файлов.",
    tags=["⚙️ Конфигурация"],
    summary="Очистить от файлов директорию для формирования отчётов",
)
async def post_cleanup(request: Request) -> Response:
    """
    Очищает папку отчётов и возвращает результат операции.

    Args:
        request: Текущий HTTP-запрос. Используется для выбора формата
            ответа: HTML или JSON.

    Returns:
        HTML-страница с отчётом об очистке или JSON-ответ со сводкой
        операции.
    """
    path_report_folder = cfg.path_report_folder
    if path_report_folder.exists():
        report = await app_clear.cleanup()
    else:
        report = {"success": 0, "errors": 0, "names of errors": ()}
        log.debug(msg=f"Сводка выполнения очистки:\n{report}", pretty=True)
    if "text/html" in request.headers.get("accept", ""):
        report["pretty json"] = json_dumps(report, indent=2, ensure_ascii=False)
        context = {
            "report": report,
        }
        return templates.TemplateResponse(
            request=request,
            name="cleanup.html",
            context=context,
            status_code=status.HTTP_200_OK,
        )
    return JSONResponse(
        content={
            "status": "ok",
            "message": "Ручка очистки директории отчетов от файлов доступна через POST /cleanup",
            "report": report,
        },
        status_code=status.HTTP_200_OK,
    )


def _void_found(
    request: Request,
    docs_content: str = "Совпадений не обнаружено.\nКоличество найденных слов: 0",
) -> Response:
    """
    Формирует ответ при отсутствии найденных слов.

    Args:
        request: Текущий HTTP-запрос. Используется для выбора формата
            ответа: HTML или обычный текст.
        docs_content: Текст ответа для клиентов, не использующих HTML.

    Returns:
        HTML-страница или текстовый HTTP-ответ со статусом ``404``.
    """
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request=request,
            name="search-word-result.html",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return PlainTextResponse(
        content=docs_content,
        status_code=status.HTTP_404_NOT_FOUND,
    )


@web.get(
    path="/search-word/search-result",
    description="Получение списка русских существительных, соответствующих заданным параметрам.",
    tags=["📝 Поиск и фильтрация слов"],
    summary="Фильтрация слов по критериям",
)
async def search_word(
    search_query: Annotated[SearchQuery, Depends(SearchQuery._search_query_form)],
    request: Request,
) -> Response:
    """
    Ищет русские существительные по заданным критериям.

    При необходимости сохраняет результат в текстовый файл. Формат ответа
    определяется заголовком ``Accept``: для HTML-клиентов возвращается
    HTML-страница, для остальных клиентов — текстовый ответ.

    Args:
        search_query: Нормализованные параметры поиска.
        request: Текущий HTTP-запрос. Используется для определения формата
            ответа.

    Returns:
        HTML-страница, текстовый ответ или файл с найденными словами.

    Raises:
        HTTPException: Возникает со статусом ``400``, если параметры поиска
            имеют недопустимые значения.
    """
    try:
        if search_query.is_web_save_file == IsYesOrNo.YES:
            search_query.is_save_file = True

        if search_query.word_length <= 1:
            return _void_found(request=request)

        found_words, quantity_words, report_path = app_report.generate_report(
            cfg=cfg, lfm=search_query
        )

        if not found_words:
            return _void_found(request=request)

        if search_query.is_save_file:
            return FileResponse(
                path=report_path,
                filename=report_path.name,
                media_type="text/plain",
                headers={"Quantity-Found-Words": str(quantity_words)},
                status_code=status.HTTP_200_OK,
            )

        context = {
            "quantity_words": quantity_words,
            "found_words": found_words,
        }
        if "text/html" in request.headers.get("accept", ""):
            return templates.TemplateResponse(
                request=request,
                name="search-word-result.html",
                context=context,
                status_code=status.HTTP_200_OK,
            )

        content = f"Количество найденных слов: {quantity_words}\n\n{found_words}"
        return PlainTextResponse(content=content, status_code=status.HTTP_200_OK)

    except ValueError as err:
        log.error(msg=f"ValueError: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err


def start_web_server() -> None:
    """
    Запускает FastAPI-приложение с помощью Uvicorn.

    Параметры хоста, порта, режима перезагрузки и журнала доступа
    считываются из конфигурации приложения.
    """
    try:
        uvicorn_server.run()
    except KeyboardInterrupt:
        log.debug(
            "🛑 Сервер остановлен пользователем через `Ctrl+Shift+C`.", pretty=True
        )


if __name__ == "__main__":
    start_web_server()
