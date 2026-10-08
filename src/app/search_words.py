# ----------------------------------------------------------------------------#
# Embedded libraries                                                          #
# ----------------------------------------------------------------------------#
from pathlib import Path

# ----------------------------------------------------------------------------#
# Project modules                                                             #
# ----------------------------------------------------------------------------#
from src.app.filters import FilterBuilderFactory
from src.config import Config, LetterFilterModel
from src.logs import SmartLogger
from src.utilities import Utilities as uts

# ----------------------------------------------------------------------------#
# Application code                                                            #
# ----------------------------------------------------------------------------#


class SearchWordsService:
    """Ищет слова в словаре по параметрам фильтрации."""

    def __init__(self, *, cfg: Config, lfm: LetterFilterModel, log: SmartLogger):
        """
        Инициализирует сервис поиска слов.

        Args:
            cfg: Конфигурация приложения, включая путь к словарю.
            lfm: Модель параметров фильтрации.
            log: Логгер приложения.
        """
        self._cfg = cfg
        self._lfm = lfm
        self._log = log

    @staticmethod
    def _matches_position_constraints(
        *,
        word: str,
        letters_fixed_pos: list[str] | str,
        letters_excluded_pos: list[str],
    ) -> bool:
        """
        Проверяет соответствие слова позиционным ограничениям.

        Для каждой позиции проверяется, что:

        - фиксированный символ совпадает с символом слова;
        - символ слова отсутствует среди запрещённых для этой позиции.

        В строковом формате ``letters_fixed_pos`` символ ``+`` означает,
        что позиция не имеет фиксированного ограничения.

        Args:
            word: Проверяемое слово.
            letters_fixed_pos: Фиксированные символы в формате строки
                или списка строк.
            letters_excluded_pos: Запрещённые символы для каждой позиции.

        Returns:
            ``True``, если слово соответствует всем ограничениям,
            иначе ``False``.
        """
        if not letters_fixed_pos and not letters_excluded_pos:
            return True

        for index, letter in enumerate(word):
            required = letters_fixed_pos[index]
            forbidden = letters_excluded_pos[index]

            if required and required != "+" and letter != required:
                return False

            if letter in forbidden:
                return False

        return True

    def search_words(self) -> list[str]:
        """
        Ищет слова в словаре по заданной модели фильтра.

        Каждая строка словаря приводится к нижнему регистру и проверяется
        по длине, обязательным и запрещённым символам, а также по
        позиционным ограничениям.

        Returns:
            Отсортированный список уникальных найденных слов.
        """
        path_file_ru_words: Path = uts.resource_path(
            relative_path=self._cfg.path_file_ru_words
        )
        encoding_ru_words: str = self._cfg.encoding_ru_words

        set_included: set[str] = set(self._lfm.letters_included)
        set_excluded: set[str] = set(self._lfm.letters_excluded)
        words: set[str] = set()

        for line in uts.read_file_line_by_line(
            file_path=path_file_ru_words, encoding=encoding_ru_words
        ):
            if (word := line.lower()) and (
                len(word) == self._lfm.word_length
                and set_included.issubset(word)
                and set_excluded.isdisjoint(word)
                and self._matches_position_constraints(
                    word=word,
                    letters_fixed_pos=self._lfm.letters_fixed_pos,
                    letters_excluded_pos=self._lfm.letters_excluded_pos,
                )
            ):
                words.add(word)

        return sorted(words)


class ApplicationService:
    """Группирует прикладные сервисы работы с результатами поиска."""

    class ClearReportService:
        """Очищает директорию для хранения отчетов от файлов."""

        def __init__(self, cfg: Config | None = None):
            """
            Инициализирует сервис удаления отчётов.

            Args:
                cfg: Конфигурация приложения. Если не передана,
                    используется конфигурация по умолчанию.
            """
            self._cfg = cfg if cfg is not None else Config()

        async def cleanup(
            self, report_files_directory: str | Path | None = None
        ) -> dict[str, int | tuple[str]]:
            """
            Очищает директорию временных файлов.

            Args:
                report_files_directory: Директория отчетов. Если не передана,
                    используется директория отчетов из конфигурации.

            Returns:
                Словарь со статистикой удаления: количеством успешно
                удалённых файлов и количеством ошибок.
            """
            if report_files_directory is None:
                report_files_directory = self._cfg.report_folder
            return await uts.clearing_folder(clear_folder=report_files_directory)

    class ReportService:
        """Формирует отчёты по результатам поиска слов."""

        def __init__(
            self,
            *,
            cfg: Config | None = None,
            lfm: LetterFilterModel | None = None,
            log: SmartLogger | None = None,
        ) -> None:
            """
            Инициализирует сервис формирования отчётов.

            Args:
                cfg: Конфигурация приложения.
                lfm: Модель фильтра по умолчанию.
                log: Логгер приложения.
            """

            self._cfg = cfg if cfg is not None else Config()
            self._lfm = lfm if lfm is not None else LetterFilterModel()
            self._log = log if log is not None else SmartLogger()

        @staticmethod
        def _format_words_as_lines(*, cfg: Config, words: list[str]) -> str:
            """
            Форматирует список слов в строки ограниченной длины.

            Слова разделяются пробелами. При превышении лимита
            ``cfg.report_line_limit`` начинается новая строка.

            Args:
                cfg: Конфигурация с ограничением длины строки.
                words: Список слов для форматирования.

            Returns:
                Многострочная строка с найденными словами. Для пустого списка
                возвращается пустая строка.
            """

            current_line: str = ""
            lines: list[str] = []
            extra_len: int

            for word in words:
                extra_len = len(word) + (1 if current_line else 0)
                if len(current_line) + extra_len > cfg.report_line_limit:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = f"{current_line} {word}" if current_line else word

            if current_line:
                lines.append(current_line)

            return "\n".join(lines)

        def _save_report(
            self, *, cfg: Config, log: SmartLogger, report_text: str
        ) -> Path:
            """
            Сохраняет текст отчёта в файл.

            Каталог отчётов создаётся автоматически, если он отсутствует.
            После успешной записи в лог отправляется информационное сообщение.

            Args:
                cfg: Конфигурация с путями к каталогу и файлу отчёта.
                log: Логгер приложения.
                report_text: Подготовленный текст отчёта.

            Returns:
                Путь к созданному файлу отчёта.
            """
            path_report_folder: Path = cfg.path_report_folder
            path_report_file: Path = cfg.path_report_file

            path_report_folder.mkdir(parents=True, exist_ok=True)

            with path_report_file.open("w", encoding="utf-8") as words_file:
                words_file.write(report_text)

            log.debug(
                msg=(
                    f"Файл с отобранными словами создан по пути: "
                    f'"{path_report_file.relative_to(Path.cwd())}".'
                ),
                pretty=True,
            )
            return path_report_file

        def generate_report(
            self,
            *,
            cfg: Config | None = None,
            is_interactive: bool = False,
            fbf: FilterBuilderFactory | None = None,
            lfm: LetterFilterModel | None = None,
            log: SmartLogger | None = None,
        ) -> tuple[str, int, Path | None]:
            """
            Формирует отчёт по результатам поиска слов.

            При необходимости получает параметры фильтра из интерактивного
            ввода, ищет подходящие слова, выводит результат в терминал и
            сохраняет его в файл.

            Args:
                cfg: Конфигурация приложения. Если не передана,
                    используется конфигурация экземпляра.
                is_interactive: Если ``True``, параметры фильтра получают
                    из интерактивного ввода.
                fbf: Фабрика построителей фильтра. Если не передана,
                    создаётся фабрика на основе текущих конфигурации,
                    модели фильтра и логгера.
                lfm: Модель фильтра. Если не передана,
                    используется модель экземпляра.
                log: Логгер приложения. Если не передан,
                    используется логгер экземпляра.

            Returns:
                Кортеж из трёх значений:

                - текста отчёта;
                - количества найденных слов;
                - пути к сохранённому файлу или ``None``.

                Если слова не найдены, файл не создаётся.
            """
            if cfg is None:
                cfg = self._cfg
            if lfm is None:
                lfm = self._lfm
            if log is None:
                log = self._log
            if fbf is None:
                fbf = FilterBuilderFactory(cfg=cfg, lfm=lfm, log=log)

            log.info(msg="Начат перебор слов.", pretty=True)
            lfm = fbf.build_filter_model(is_interactive=is_interactive)
            sw = SearchWordsService(cfg=cfg, lfm=lfm, log=log)
            words = sw.search_words()
            log.info(msg="Перебор слов завершен.", pretty=True)

            quantity_words = len(words)
            log.info(msg=f"Найдено слов: {quantity_words}.", pretty=True)

            word_lines: str = self._format_words_as_lines(cfg=cfg, words=words)

            if quantity_words != 0:
                if lfm.is_output_terminal:
                    log.info(msg=f"\n{word_lines}", pretty=True)
                if lfm.is_save_file:
                    path_report_file: Path = self._save_report(
                        cfg=cfg, log=log, report_text=word_lines
                    )
                    return word_lines, quantity_words, path_report_file

            return word_lines, quantity_words, None
