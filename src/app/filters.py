# ----------------------------------------------------------------------------#
# Embedded libraries                                                          #
# ----------------------------------------------------------------------------#
from abc import ABC, abstractmethod
from re import escape as re_escape
from re import sub as re_sub

# ----------------------------------------------------------------------------#
# Project modules                                                             #
# ----------------------------------------------------------------------------#
from src.config import Config, LetterFilterModel
from src.logs import SmartLogger

# ----------------------------------------------------------------------------#
# Application code                                                            #
# ----------------------------------------------------------------------------#


class FilterBuilder(ABC):
    """
    Абстрактный интерфейс строителей параметров фильтрации.
    """

    @abstractmethod
    def build(self) -> LetterFilterModel:
        """
        Создаёт модель фильтра из доступного источника данных.

        Returns:
            Заполненная модель параметров фильтрации.
        """
        raise NotImplementedError


class InputFilterBuilder(FilterBuilder):
    """
    Собирает параметры фильтра из интерактивного пользовательского ввода.

    Внутренние методы класса последовательно получают отдельные параметры
    фильтра. Полностью собранная модель возвращается методом ``build()``.
    """

    def __init__(self, *, cfg: Config, lfm: LetterFilterModel, log: SmartLogger):
        """Инициализирует строитель фильтра пользовательского ввода.

        Args:
            cfg: Конфигурация приложения. Если не передана,
                используется конфигурация по умолчанию.
            lfm: Начальные параметры фильтра. Если не передана,
                используется модель фильтрации по умолчанию.
            log: Логгер приложения. Если не передан,
                создаётся новый экземпляр.
        """

        self._cfg = cfg if cfg is not None else Config()
        self._lfm = lfm if lfm is not None else LetterFilterModel()
        self._log = log if log is not None else SmartLogger()
        self._lfm.letters_fixed_pos = (
            [""]
            if isinstance(self._lfm.letters_fixed_pos, str)
            else self._lfm.letters_fixed_pos
        )

    @staticmethod
    def _normalize_unique_chars(letters: str) -> str:
        """
        Возвращает строку уникальных символов в нижнем регистре.
        Порядок первого появления символов сохраняется.

        Args:
            letters: Исходная строка символов.

        Returns:
            Строка уникальных символов в нижнем регистре.
        """
        return "".join(dict.fromkeys(letters.lower()))

    def _word_length(self, provided_input: str | None = None) -> None:
        """
        Получает и сохраняет длину искомого слова.

        При интерактивном вводе повторяет запрос, пока не будет
        введено целое число не менее двух. При переданном
        ``provided_input`` некорректное значение приводит к ``ValueError``.

        Args:
            provided_input: Значение для автоматизированного сценария
                или теста. Если не передано, значение читается из консоли.

        Raises:
            ValueError: Если переданное значение некорректно или меньше двух.
        """
        while True:
            self._log.info(
                msg="Введите количество символов искомого слова (не менее 2).",
                pretty=True,
            )
            raw: str = provided_input if provided_input is not None else input()
            cleaned = re_sub(pattern=r"\D", repl="", string=raw)

            if not cleaned:
                if provided_input is not None:
                    self._log.error(
                        msg="В `provided_input` указано некорректное значение числа."
                    )
                    raise ValueError(
                        "В `provided_input` указано некорректное значение числа."
                    )
                self._log.warning(
                    msg="Не удалось распознать число. Повторите ввод.",
                    pretty=True,
                )
                continue

            quantity = int(cleaned)
            if quantity < 2:
                if provided_input is not None:
                    self._log.error(
                        msg="В `provided_input` указано слишком малое значение числа."
                    )
                    raise ValueError(
                        "В `provided_input` указано слишком малое значение числа."
                    )
                self._log.warning(
                    msg="Слишком короткое слово. Введите число не менее 2.",
                    pretty=True,
                )
                continue

            self._log.info(msg=f"Введено число: '{quantity}'.", pretty=True)
            self._lfm.word_length = quantity
            return

    def _letters_excluded(self, provided_input: str | None = None) -> None:
        """
        Получает символы, которых гарантированно нет в искомом слове.

        Введённые символы приводятся к нижнему регистру, очищаются
        в соответствии с шаблоном конфигурации и сохраняются в поле
        ``letters_excluded`` текущей модели фильтра.

        Args:
            provided_input: Значение для автоматизированного сценария
                или теста. Если не передано, значение читается из консоли.
        """
        self._log.info(msg="Введите символы, которых нет в слове.", pretty=True)
        raw: str = provided_input if provided_input is not None else input()
        letters_excluded = re_sub(
            pattern=self._cfg.pattern_ru_letters,
            repl="",
            string=self._normalize_unique_chars(letters=raw),
        )
        self._log.info(
            msg=f"Были обнаружены символы: {list(letters_excluded)}.",
            pretty=True,
        )
        self._lfm.letters_excluded = letters_excluded

    def _letters_included(self, provided_input: str | None = None) -> None:
        """
        Получает символы, которые гарантированно присутствуют в слове.

        Символы, уже указанные в ``letters_excluded``, удаляются.
        Оставшиеся символы нормализуются и сохраняются в поле
        ``letters_included`` текущей модели фильтра.

        Args:
            provided_input: Значение для автоматизированного сценария
                или теста. Если не передано, значение читается из консоли.
        """

        self._log.info(
            msg="Введите символы, которые есть в слове.",
            pretty=True,
        )
        raw: str = provided_input if provided_input is not None else input()
        if self._lfm.letters_excluded:
            pattern = rf"[{re_escape(self._lfm.letters_excluded)}]|{self._cfg.pattern_ru_letters}"
        else:
            pattern = self._cfg.pattern_ru_letters
        letters_included = re_sub(
            pattern=pattern, repl="", string=self._normalize_unique_chars(letters=raw)
        )
        self._log.info(
            msg=f"Были обнаружены символы: {list(letters_included)}.",
            pretty=True,
        )
        self._lfm.letters_included = letters_included

    def _validate_bounds(self, provided_input: list[str] | None = None) -> None:
        """
        Проверяет соответствие количества позиционных ограничений длине слова.

        Args:
            provided_input: Ограничения для отдельных позиций. Если значение
                не передано, проверка количества не выполняется.

        Raises:
            ValueError: Если количество переданных ограничений не совпадает
                с длиной слова.
        """

        if provided_input is not None and len(provided_input) != self._lfm.word_length:
            raise ValueError(
                "Количество ограничений позиций должно совпадать с длиной слова."
            )

    def _position_constraints(
        self,
        *,
        start_msg: str,
        is_fixed_pos: bool = False,
        provided_input: list[str] | None = None,
    ) -> list[str]:
        """
        Получает и обрабатывает ограничения для каждой позиции слова.

        Для каждой позиции считывает значение из консоли или использует
        соответствующее значение из ``provided_input``. Из введённых данных
        удаляются недопустимые символы.

        Args:
            start_msg: Сообщение, отображаемое перед началом ввода.
            is_fixed_pos: Если ``True``, для каждой позиции сохраняется
                не более одного символа.
            provided_input: Предварительно заданные значения для позиций.
                Если не переданы, значения считываются из консоли.

        Returns:
            Список ограничений по позициям. Пустая строка означает,
            что для соответствующей позиции ограничение не задано.

        Raises:
            ValueError: Если количество предварительно заданных значений
                не совпадает с длиной слова.
        """
        self._validate_bounds(provided_input=provided_input)
        letters_pos: list[str] = []

        self._log.info(
            msg=start_msg,
            pretty=True,
        )
        for index in range(self._lfm.word_length):
            self._log.info(
                msg=f"Позиция {index + 1} ({index * '+'}*{(self._lfm.word_length - index - 1) * '+'}):",
                pretty=True,
            )
            raw: str = provided_input[index] if provided_input is not None else input()
            letters_pos_item = re_sub(
                pattern=rf"[^{re_escape(self._lfm.letters_included)}]",
                repl="",
                string=self._normalize_unique_chars(letters=raw),
            )
            if is_fixed_pos:
                letters_pos_item = letters_pos_item[:1]
            self._log.info(
                msg=f"Были обнаружены символы: {list(letters_pos_item)}.",
                pretty=True,
            )
            letters_pos.append(letters_pos_item)
        return letters_pos

    def _letters_excluded_pos(
        self,
        provided_input: list[str] | None = None,
    ) -> None:
        """
        Получает исключенные символы для каждой позиции слова.

        Для каждой позиции вводится набор символов, выбранных из
        ``letters_included``. Эти символы не должны находиться на
        соответствующей позиции. Повторы удаляются, а символы, отсутствующие
        в ``letters_included``, отбрасываются.

        Результат сохраняется в поле ``letters_excluded_pos`` текущей
        модели фильтра.

        Args:
            provided_input: Список предварительно заданных значений,
                обычно используемый в тестах. Количество элементов должно
                совпадать с длиной слова.

        Raises:
            ValueError: Если количество переданных значений не совпадает
                с длиной слова.
        """
        self._lfm.letters_excluded_pos = self._position_constraints(
            start_msg="Введите исключённые символы по позициям.",
            provided_input=provided_input,
        )

    def _letters_fixed_pos(
        self,
        provided_input: list[str] | None = None,
    ) -> None:
        """
        Получает фиксированный символ для каждой позиции слова.

        Для каждой позиции обрабатывается строка из ``letters_included``.
        Повторы удаляются, недопустимые символы отбрасываются, после чего
        сохраняется только первый подходящий символ.

        Если подходящий символ отсутствует, для позиции сохраняется пустая
        строка, обозначающая отсутствие фиксированного ограничения.

        Результат сохраняется в поле ``letters_fixed_pos`` текущей модели
        в формате ``list[str]``.

        Args:
            provided_input: Список предварительно заданных значений,
                обычно используемый в тестах. Количество элементов должно
                совпадать с длиной слова.

        Raises:
            ValueError: Если количество переданных значений не совпадает
                с длиной слова.
        """
        self._lfm.letters_fixed_pos = self._position_constraints(
            start_msg=(
                "Введите символы на фиксированных позициях. "
                "Будет считан первый подходящий символ для каждой позиции."
            ),
            provided_input=provided_input,
            is_fixed_pos=True,
        )

    def _confirmation(
        self,
        *,
        prompt: str,
        provided_input: str | None = None,
    ) -> bool:
        """
        Получает подтверждение пользователя в формате «да» или «нет».

        При интерактивном режиме метод повторяет запрос после некорректного
        ответа. Если значение передано через ``provided_input``, некорректный
        ответ приводит к исключению.

        Args:
            prompt: Текст вопроса пользователю.
            provided_input: Предварительно заданный ответ. Поддерживаются
                русские и английские варианты «да» и «нет».

        Returns:
            ``True`` для положительного ответа и ``False`` для отрицательного.

        Raises:
            ValueError: Если ``provided_input`` содержит некорректный ответ.
        """
        yes = {"yes", "y", "да", "д"}
        no = {"no", "n", "нет", "не", "н"}
        self._log.info(
            msg=f"{prompt} [Y/n]",
            pretty=True,
        )
        while True:
            raw: str = provided_input if provided_input is not None else input()
            raw = raw.lower()
            if raw in yes:
                return True
            elif raw in no:
                return False
            if provided_input is not None:
                self._log.error(msg="В `provided_input` указано некорректное значение.")
                raise ValueError("В `provided_input` указано некорректное значение.")
            self._log.warning(
                msg=f"Ошибка ввода.\n{prompt} [Y/n]",
                pretty=True,
            )

    def build(self) -> LetterFilterModel:
        """
        Собирает модель фильтра из интерактивного ввода.

        Метод последовательно получает общие и позиционные ограничения,
        а также параметры сохранения и вывода результата.

        Returns:
            Заполненная модель фильтра.

        Raises:
            ValueError: Если переданное тестовое значение имеет некорректный
                формат.
        """

        self._word_length()
        self._letters_excluded()
        self._letters_included()

        if self._lfm.letters_included:
            self._letters_excluded_pos()
            self._letters_fixed_pos()
        else:
            self._lfm.letters_excluded_pos = [""] * self._lfm.word_length
            self._lfm.letters_fixed_pos = [""] * self._lfm.word_length

        self._lfm.is_save_file = self._confirmation(prompt="Сохранить файл?")
        self._lfm.is_output_terminal = self._confirmation(
            prompt="Вывести найденные слова в терминал?"
        )

        return LetterFilterModel(
            word_length=self._lfm.word_length,
            letters_excluded=self._lfm.letters_excluded,
            letters_included=self._lfm.letters_included,
            letters_excluded_pos=self._lfm.letters_excluded_pos,
            letters_fixed_pos=self._lfm.letters_fixed_pos,
            is_save_file=self._lfm.is_save_file,
            is_output_terminal=self._lfm.is_output_terminal,
        )


class ReceivedFilterBuilder(FilterBuilder):
    """
    Нормализует модель фильтра, полученную из внешнего источника.

    Внешняя модель может содержать позиционные ограничения в формате
    ``list[str]`` или ``str``. Builder приводит их к длине искомого слова
    и удаляет недопустимые символы.
    """

    def __init__(self, *, lfm: LetterFilterModel, log: SmartLogger):
        """Инициализирует строитель фильтра из внешней модели.

        Args:
            lfm: Начальные параметры фильтра. Если не передана,
                используется модель фильтрации по умолчанию.
            log: Логгер приложения. Если не передан,
                создаётся новый экземпляр.
        """
        self._lfm = lfm if lfm is not None else LetterFilterModel()
        self._log = log if log is not None else SmartLogger()

    @staticmethod
    def _normalize_position_filters(
        *, filters: list[str] | str, allowed_letters: str
    ) -> list[str] | str:
        """
        Нормализует позиционные фильтры.

        Для строкового формата недопустимые символы заменяются на ``+``.
        Символ ``+`` обозначает свободную позицию. Для списочного формата
        недопустимые символы удаляются из каждого элемента.

        Args:
            filters: Фильтры в формате строки или списка строк.
            allowed_letters: Буквы, разрешённые в позиционных ограничениях.

        Returns:
            Нормализованные фильтры в том же формате, что и
            ``filters``.
        """
        if isinstance(filters, str):
            correct = set(f"{allowed_letters}+")
            return "".join(char if char in correct else "+" for char in filters)
        else:
            invalid_symbols = "".join(set("".join(filters)) - set(allowed_letters))
            table_excluded = str.maketrans("", "", invalid_symbols)
            return [elem.translate(table_excluded) for elem in filters]

    def build(self) -> LetterFilterModel:
        """
        Нормализует модель фильтра, полученную из внешнего источника.

        Исключённые символы удаляются из списка обязательных символов.
        Позиционные ограничения, которые короче длины слова, дополняются.
        Для строкового ``letters_fixed_pos`` свободные позиции обозначаются
        символом ``+``.

        Returns:
            Нормализованная модель фильтра.

        Raises:
            ValueError: Если позиционное ограничение длиннее слова.
        """
        len_letters_excluded_pos: int = len(self._lfm.letters_excluded_pos)
        len_letters_fixed_pos: int = len(self._lfm.letters_fixed_pos)

        if (
            self._lfm.word_length < len_letters_excluded_pos
            or self._lfm.word_length < len_letters_fixed_pos
        ):
            raise ValueError(
                "letters_fixed_pos и letters_excluded_pos должны соответствовать длине слова."
            )

        if self._lfm.word_length > len_letters_excluded_pos:
            for _ in range(self._lfm.word_length - len_letters_excluded_pos):
                self._lfm.letters_excluded_pos.append("")

        if self._lfm.word_length > len_letters_fixed_pos:
            self._lfm.letters_fixed_pos = f"{self._lfm.letters_fixed_pos}{(self._lfm.word_length - len_letters_fixed_pos) * '+'}"

        table_excluded = str.maketrans("", "", self._lfm.letters_excluded)
        self._lfm.letters_included = self._lfm.letters_included.translate(
            table_excluded
        )

        self._lfm.letters_excluded_pos = self._normalize_position_filters(
            filters=self._lfm.letters_excluded_pos,
            allowed_letters=self._lfm.letters_included,
        )

        self._lfm.letters_fixed_pos = self._normalize_position_filters(
            filters=self._lfm.letters_fixed_pos,
            allowed_letters=self._lfm.letters_included,
        )

        return self._lfm


class FilterBuilderFactory:
    """
    Фабрика строителей фильтра.

    В зависимости от режима работы фабрика возвращает строитель
    для интерактивного ввода или для внешней модели фильтра.
    """

    def __init__(self, *, cfg: Config, lfm: LetterFilterModel, log: SmartLogger):
        """
        Инициализирует фабрику строителей фильтра.

        Args:
            cfg: Конфигурация приложения. Если не передана,
                используется конфигурация по умолчанию.
            lfm: Начальные параметры фильтра. Если не передана,
                используется модель фильтрации по умолчанию.
            log: Логгер приложения. Если не передан,
                создаётся новый экземпляр.
        """
        self._cfg = cfg if cfg is not None else Config()
        self._lfm = lfm if lfm is not None else LetterFilterModel()
        self._log = log if log is not None else SmartLogger()

    def create_filter_builder(
        self,
        is_interactive: bool,
    ) -> FilterBuilder:
        """
        Создаёт строитель фильтра для выбранного режима.

        Args:
            is_interactive: Если ``True``, используется интерактивный ввод.
                Если ``False``, используется внешняя модель фильтра.

        Returns:
            Строитель, соответствующий выбранному режиму.
        """
        if is_interactive:
            return InputFilterBuilder(cfg=self._cfg, lfm=self._lfm, log=self._log)

        return ReceivedFilterBuilder(lfm=self._lfm, log=self._log)

    def build_filter_model(self, is_interactive: bool) -> LetterFilterModel:
        """
        Создаёт модель фильтра из выбранного источника данных.

        Args:
            is_interactive: Если ``True``, параметры получают из консоли.
                Если ``False``, используется внешняя модель фильтра.

        Returns:
            Заполненная модель для интерактивного режима или нормализованная
            модель для внешнего режима.
        """

        filter_builder = self.create_filter_builder(is_interactive=is_interactive)

        return filter_builder.build()
