"""
Модуль доски для игры «Уголки».
Содержит класс Board с логикой доски, валидацией ходов и определением победы.
"""

from __future__ import annotations
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    BOARD_SIZE,
    UGOLKI_VARIANTS,
    DIRECTIONS,
    EMOJI_PLAYER1,
    EMOJI_PLAYER2,
    EMOJI_SELECTED,
    EMOJI_VALID_MOVE,
    EMOJI_EMPTY_LIGHT,
    EMOJI_HOME1_EMPTY,
    EMOJI_HOME2_EMPTY,
)


class Board:
    """Игровая доска 8×8 для «Уголков»."""

    # Константы фигур
    EMPTY = 0
    PLAYER1 = 1
    PLAYER2 = 2

    def __init__(self, variant: str = "classic") -> None:
        """Инициализация доски с начальной расстановкой по выбранной вариации."""
        self.variant = variant
        var_config = UGOLKI_VARIANTS.get(variant, UGOLKI_VARIANTS["classic"])

        self.grid: list[list[int]] = [
            [self.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)
        ]

        # Расставляем шашки
        for r, c in var_config["start1"]:
            self.grid[r][c] = self.PLAYER1

        for r, c in var_config["start2"]:
            self.grid[r][c] = self.PLAYER2

        # Множества «домов» для быстрой проверки
        self.home1: set[tuple[int, int]] = set(var_config["home1"])
        self.home2: set[tuple[int, int]] = set(var_config["home2"])

    # ─── Основные методы ────────────────────────────────────────

    def get_piece(self, row: int, col: int) -> int:
        """Получить фигуру на клетке."""
        return self.grid[row][col]

    def is_valid_pos(self, row: int, col: int) -> bool:
        """Проверить, что координаты в пределах доски."""
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE

    def get_player_pieces(self, player: int) -> list[tuple[int, int]]:
        """Получить все координаты шашек игрока."""
        pieces = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.grid[r][c] == player:
                    pieces.append((r, c))
        return pieces

    # ─── Ходы ───────────────────────────────────────────────────

    def get_simple_moves(self, row: int, col: int) -> list[tuple[int, int]]:
        """Получить все простые ходы (на 1 клетку в 8 направлениях)."""
        moves = []
        for dr, dc in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if self.is_valid_pos(nr, nc) and self.grid[nr][nc] == self.EMPTY:
                moves.append((nr, nc))
        return moves

    def get_jump_moves(
        self, row: int, col: int, visited: Optional[set[tuple[int, int]]] = None
    ) -> list[tuple[int, int]]:
        """
        Получить все прыжки (рекурсивно, цепочки).
        Прыжок: перескок через соседнюю шашку (любую) на свободную клетку за ней.
        """
        if visited is None:
            visited = {(row, col)}

        jumps = []
        for dr, dc in DIRECTIONS:
            # Клетка через которую прыгаем
            mid_r, mid_c = row + dr, col + dc
            # Клетка куда приземляемся
            land_r, land_c = row + 2 * dr, col + 2 * dc

            if (
                self.is_valid_pos(land_r, land_c)
                and self.grid[mid_r][mid_c] != self.EMPTY  # Есть фигура для прыжка
                and self.grid[land_r][land_c]
                == self.EMPTY  # Место приземления свободно
                and (land_r, land_c) not in visited  # Не были здесь
            ):
                jumps.append((land_r, land_c))
                visited.add((land_r, land_c))
                # Рекурсивно ищем продолжение прыжков
                jumps.extend(self.get_jump_moves(land_r, land_c, visited))

        return jumps

    def get_valid_moves(self, row: int, col: int) -> list[tuple[int, int]]:
        """Получить все допустимые ходы для шашки на (row, col)."""
        simple = self.get_simple_moves(row, col)
        jumps = self.get_jump_moves(row, col)
        return simple + jumps

    def move_piece(self, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> bool:
        """
        Выполнить ход: переместить шашку.
        Возвращает True, если ход успешен.
        """
        fr, fc = from_pos
        tr, tc = to_pos

        if self.grid[fr][fc] == self.EMPTY:
            return False

        if to_pos not in self.get_valid_moves(fr, fc):
            return False

        # Перемещаем фигуру
        self.grid[tr][tc] = self.grid[fr][fc]
        self.grid[fr][fc] = self.EMPTY
        return True

    # ─── Проверки правил ─────────────────────────────────────────

    def is_piece_locked_by(self, row: int, col: int, blocker: int) -> bool:
        """
        Проверить, заблокирована ли фишка на (row, col) фишками игрока blocker.
        Фишка заблокирована если у неё нет возможности двигаться,
        И причиной блокировки являются фишки blocker (а не свои или край доски).

        Правило: нельзя окружить фишку противника СВОИМИ шашками со всех сторон.
        Проверяем: все доступные направления заблокированы, и хотя бы одно
        заблокировано именно фишками blocker.
        """
        blocker_involved = False
        for dr, dc in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if not self.is_valid_pos(nr, nc):
                continue  # Край доски
            if self.grid[nr][nc] == self.EMPTY:
                return False  # Есть свободная клетка — можно уйти
            # Клетка занята — проверяем прыжок
            jr, jc = row + 2 * dr, col + 2 * dc
            if self.is_valid_pos(jr, jc) and self.grid[jr][jc] == self.EMPTY:
                return False  # Можно прыгнуть
            # Это направление полностью заблокировано
            if self.grid[nr][nc] == blocker:
                blocker_involved = True
        # Фишка заблокирована И blocker участвует в блокировке
        return blocker_involved

    def has_any_locked_opponent(self, player: int) -> list[tuple[int, int]]:
        """
        Найти все фишки противника, заблокированные фишками player.
        Возвращает список позиций заблокированных фишек.
        """
        opponent = self.PLAYER2 if player == self.PLAYER1 else self.PLAYER1
        locked = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.grid[r][c] == opponent and self.is_piece_locked_by(
                    r, c, player
                ):
                    locked.append((r, c))
        return locked

    def count_pieces_in_zone(self, player: int, zone: set[tuple[int, int]]) -> int:
        """Подсчитать количество фишек игрока в заданной зоне."""
        count = 0
        for r, c in zone:
            if self.grid[r][c] == player:
                count += 1
        return count

    def has_pieces_in_home(self, player: int) -> bool:
        """
        Проверить, есть ли у игрока фишки в собственном стартовом «доме».
        """
        # Стартовый дом игрока 1 — это целевой дом игрока 2 (home2)
        home = self.home2 if player == self.PLAYER1 else self.home1
        for r, c in home:
            if self.grid[r][c] == player:
                return True
        return False

    def position_hash(self) -> str:
        """Получить хэш текущей позиции для правила трёхкратного повторения."""
        return str(self.grid)

    # ─── Проверка победы ────────────────────────────────────────

    def check_winner(self) -> int:
        """
        Проверить, есть ли победитель.
        Возвращает: 0 — нет победителя, 1 — победил игрок 1, 2 — победил игрок 2,
                    3 — оба игрока завершили одновременно.
        """
        # Игрок 1 должен занять дом игрока 2 (home1 = позиции P2)
        p1_won = all(self.grid[r][c] == self.PLAYER1 for r, c in self.home1)
        # Игрок 2 должен занять дом игрока 1 (home2 = позиции P1)
        p2_won = all(self.grid[r][c] == self.PLAYER2 for r, c in self.home2)

        if p1_won and p2_won:
            return 3  # Оба завершили
        if p1_won:
            return self.PLAYER1
        if p2_won:
            return self.PLAYER2
        return 0

    # ─── Отображение ────────────────────────────────────────────

    def to_inline_keyboard(
        self,
        selected: Optional[tuple[int, int]] = None,
        valid_moves: Optional[list[tuple[int, int]]] = None,
        game_over: bool = False,
        timer_text: str = "00:00 ⏱",
        finish_reason: str = "",
        show_hints: bool = True,
        **kwargs,
    ) -> InlineKeyboardMarkup:
        """
        Генерация InlineKeyboardMarkup для отображения доски в Telegram.

        Args:
            selected: координаты выбранной шашки (подсветка)
            valid_moves: список доступных ходов (подсветка зелёным)
            game_over: если True, кнопки неактивны
            timer_text: текст для таймера
            finish_reason: причина завершения игры (для показа кнопок продления)
        """
        if valid_moves is None:
            valid_moves = []

        if not show_hints:
            selected = None
            valid_set = set()
        else:
            valid_set = set(valid_moves)
            
        keyboard = []

        for r in range(BOARD_SIZE):
            row_buttons = []

            for c in range(BOARD_SIZE):
                pos = (r, c)
                piece = self.grid[r][c]

                # Определяем эмодзи для клетки
                if pos == selected:
                    emoji = EMOJI_SELECTED
                elif pos in valid_set:
                    emoji = EMOJI_VALID_MOVE
                elif piece == self.PLAYER1:
                    emoji = EMOJI_PLAYER1
                elif piece == self.PLAYER2:
                    emoji = EMOJI_PLAYER2
                else:
                    # Пустая клетка — показываем подсветку «дома»
                    if pos in self.home1 or pos in self.home2:
                        emoji = EMOJI_HOME1_EMPTY
                    else:
                        emoji = EMOJI_EMPTY_LIGHT

                # callback_data
                if game_over:
                    cb = f"noop_{r}_{c}"
                else:
                    cb = f"cell_{r}_{c}"

                row_buttons.append(InlineKeyboardButton(emoji, callback_data=cb))

            keyboard.append(row_buttons)

        # Добавляем кнопки управления
        if not game_over:
            hints_btn = InlineKeyboardButton(
                "💡 Вкл" if show_hints else "💡 Выкл", callback_data="toggle_hints"
            )
            keyboard.append(
                [
                    InlineKeyboardButton("Сдаться", callback_data="surrender"),
                    InlineKeyboardButton("Ничья", callback_data="draw"),
                    hints_btn,
                    InlineKeyboardButton(timer_text, callback_data="noop_time"),
                ]
            )
        else:
            if finish_reason in ("move_limit_score", "move_limit_draw"):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "Продлить на 40", callback_data="extend_40"
                        ),
                        InlineKeyboardButton("Бесконечно", callback_data="extend_inf"),
                    ]
                )

        return InlineKeyboardMarkup(keyboard)

    def __str__(self) -> str:
        """Текстовое представление доски (для отладки)."""
        symbols = {self.EMPTY: "·", self.PLAYER1: "⚪", self.PLAYER2: "⚫"}
        lines = []
        for r in range(BOARD_SIZE):
            line = " ".join(symbols[self.grid[r][c]] for c in range(BOARD_SIZE))
            lines.append(f"{r + 1} {line}")
        lines.insert(0, "  a b c d e f g h")
        return "\n".join(lines)

    def clone(self) -> "Board":
        """Создать глубокую копию доски."""
        new_board = Board.__new__(Board)
        new_board.grid = [row[:] for row in self.grid]
        new_board.home1 = self.home1.copy()
        new_board.home2 = self.home2.copy()
        return new_board
