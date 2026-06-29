"""
Модуль доски для игры «Русские шашки».
"""

from __future__ import annotations
from typing import Optional, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Board:
    """Игровая доска 8×8 для Русских шашек."""

    EMPTY = 0
    WHITE = 1  # Белая простая
    BLACK = 2  # Чёрная простая
    WHITE_KING = 3  # Белая дамка
    BLACK_KING = 4  # Чёрная дамка

    SIZE = 8

    # Направления для ходов
    DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    def __init__(self) -> None:
        """Инициализация доски со стандартной расстановкой."""
        self.grid: list[list[int]] = [
            [self.EMPTY] * self.SIZE for _ in range(self.SIZE)
        ]
        self.reset()

    def reset(self) -> None:
        """Сбросить доску к начальному состоянию."""
        self.grid = [[self.EMPTY] * self.SIZE for _ in range(self.SIZE)]

        # Чёрные шашки сверху (ряды 0, 1, 2)
        for r in range(3):
            for c in range(self.SIZE):
                if (r + c) % 2 == 1:
                    self.grid[r][c] = self.BLACK

        # Белые шашки снизу (ряды 5, 6, 7)
        for r in range(5, self.SIZE):
            for c in range(self.SIZE):
                if (r + c) % 2 == 1:
                    self.grid[r][c] = self.WHITE

    def get_piece(self, row: int, col: int) -> int:
        """Получить фигуру на клетке."""
        return self.grid[row][col]

    def set_piece(self, row: int, col: int, piece: int) -> None:
        """Установить фигуру на клетку."""
        self.grid[row][col] = piece

    def is_valid_pos(self, row: int, col: int) -> bool:
        """Проверить, находятся ли координаты в пределах доски."""
        return 0 <= row < self.SIZE and 0 <= col < self.SIZE

    def is_dark_cell(self, row: int, col: int) -> bool:
        """Проверить, является ли клетка темной (игровой)."""
        return (row + col) % 2 == 1

    def is_opponent(self, piece1: int, piece2: int) -> bool:
        """Проверяет, являются ли две фигуры враждебными друг другу."""
        if piece1 == self.EMPTY or piece2 == self.EMPTY:
            return False
        p1_is_white = piece1 in (self.WHITE, self.WHITE_KING)
        p2_is_white = piece2 in (self.WHITE, self.WHITE_KING)
        return p1_is_white != p2_is_white

    def get_player_pieces(self, player: int) -> list[tuple[int, int]]:
        """Получить координаты всех шашек игрока."""
        pieces = []
        target_types = (
            (self.WHITE, self.WHITE_KING)
            if player == self.WHITE
            else (self.BLACK, self.BLACK_KING)
        )
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                if self.grid[r][c] in target_types:
                    pieces.append((r, c))
        return pieces

    # ─── Логика ходов ───────────────────────────────────────────

    def get_normal_moves_for_piece(self, row: int, col: int) -> list[tuple[int, int]]:
        """Получить список обычных (не бьющих) ходов для шашки на (row, col)."""
        piece = self.grid[row][col]
        if piece == self.EMPTY:
            return []

        moves = []
        is_king = piece in (self.WHITE_KING, self.BLACK_KING)

        if is_king:
            # Дамка ходит на любое расстояние по 4 диагоналям
            for dr, dc in self.DIRECTIONS:
                nr, nc = row + dr, col + dc
                while self.is_valid_pos(nr, nc) and self.grid[nr][nc] == self.EMPTY:
                    moves.append((nr, nc))
                    nr += dr
                    nc += dc
        else:
            # Простая шашка ходит только на 1 клетку вперед по диагонали
            # Белые идут вверх (-1), Чёрные вниз (+1)
            direction = -1 if piece == self.WHITE else 1
            for dc in (-1, 1):
                nr, nc = row + direction, col + dc
                if self.is_valid_pos(nr, nc) and self.grid[nr][nc] == self.EMPTY:
                    moves.append((nr, nc))
        return moves

    def get_captures_for_piece(
        self, row: int, col: int, ignored_captured: set[tuple[int, int]] = None
    ) -> list[tuple[int, int]]:
        """
        Получить список доступных взятий (прыжков) для конкретной шашки.
        ignored_captured: координаты фигур, которые уже побиты в этой серии (их нельзя бить повторно,
        и они не блокируют приземление, хотя в русских шашках они остаются на доске до конца хода).
        """
        if ignored_captured is None:
            ignored_captured = set()

        piece = self.grid[row][col]
        if piece == self.EMPTY:
            return []

        captures = []
        is_king = piece in (self.WHITE_KING, self.BLACK_KING)

        if is_king:
            # Дамка бьет на любое расстояние
            for dr, dc in self.DIRECTIONS:
                nr, nc = row + dr, col + dc
                piece_to_jump = None

                while self.is_valid_pos(nr, nc):
                    current_cell = self.grid[nr][nc]

                    if current_cell != self.EMPTY:
                        if (nr, nc) in ignored_captured:
                            # Пролетаем сквозь уже сбитую шашку как сквозь пустую
                            nr += dr
                            nc += dc
                            continue

                        if self.is_opponent(piece, current_cell):
                            piece_to_jump = (nr, nc)
                            # Ищем клетки для приземления за ней
                            land_r, land_c = nr + dr, nc + dc
                            while self.is_valid_pos(land_r, land_c):
                                land_cell = self.grid[land_r][land_c]
                                # Если наткнулись на другую фигуру (не из списка сбитых), путь перекрыт
                                if (
                                    land_cell != self.EMPTY
                                    and (land_r, land_c) not in ignored_captured
                                ):
                                    break
                                captures.append((land_r, land_c))
                                land_r += dr
                                land_c += dc
                            break
                        else:
                            # Наткнулись на свою фигуру — дальше бить нельзя
                            break
                    nr += dr
                    nc += dc
        else:
            # Простая шашка бьет на 2 клетки в любом направлении
            for dr, dc in self.DIRECTIONS:
                mid_r, mid_c = row + dr, col + dc
                land_r, land_c = row + 2 * dr, col + 2 * dc

                if self.is_valid_pos(land_r, land_c):
                    mid_piece = self.grid[mid_r][mid_c]
                    land_piece = self.grid[land_r][land_c]

                    if (
                        mid_piece != self.EMPTY
                        and (mid_r, mid_c) not in ignored_captured
                        and self.is_opponent(piece, mid_piece)
                        and (
                            land_piece == self.EMPTY
                            or (land_r, land_c) in ignored_captured
                        )
                    ):
                        captures.append((land_r, land_c))

        return captures

    def get_all_valid_captures(
        self, player: int, ignored_captured: set[tuple[int, int]] = None
    ) -> dict[tuple[int, int], list[tuple[int, int]]]:
        """Получить все доступные взятия для всех фигур игрока."""
        pieces = self.get_player_pieces(player)
        valid_captures = {}
        for r, c in pieces:
            caps = self.get_captures_for_piece(r, c, ignored_captured)
            if caps:
                valid_captures[(r, c)] = caps
        return valid_captures

    def get_valid_moves(
        self,
        row: int,
        col: int,
        active_piece: Optional[tuple[int, int]] = None,
        ignored_captured: set[tuple[int, int]] = None,
    ) -> list[tuple[int, int]]:
        """
        Получить все валидные ходы для шашки на (row, col).
        Если на доске есть взятия, то возвращаются только взятия.
        Если активен режим мульти-прыжка (active_piece задана), то ходить может ТОЛЬКО эта фигура и только взятиями.
        """
        piece = self.grid[row][col]
        if piece == self.EMPTY:
            return []

        player = self.WHITE if piece in (self.WHITE, self.WHITE_KING) else self.BLACK

        # Если идет серия прыжков конкретной шашкой
        if active_piece is not None:
            if active_piece != (row, col):
                return []  # Ходить может только активная шашка
            return self.get_captures_for_piece(row, col, ignored_captured)

        # Проверяем, есть ли вообще взятия на доске для этого игрока
        all_caps = self.get_all_valid_captures(player)
        if all_caps:
            # Если взятия есть, то обычные ходы запрещены
            return all_caps.get((row, col), [])

        # Если взятий нет, возвращаем обычные ходы
        return self.get_normal_moves_for_piece(row, col)

    # ─── Выполнение хода ────────────────────────────────────────

    def move_piece(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int]
    ) -> tuple[bool, Optional[tuple[int, int]]]:
        """
        Переместить фигуру. Выполняет базовое перемещение и превращение в дамку.
        Возвращает:
            (успех_хода: bool, координата_сбитой_шашки: Optional[tuple[int, int]])
        """
        fr, fc = from_pos
        tr, tc = to_pos

        piece = self.grid[fr][fc]
        if piece == self.EMPTY:
            return False, None

        # Проверяем, было ли это взятием
        captured_pos = None
        dr = 1 if tr > fr else -1
        dc = 1 if tc > fc else -1

        if abs(tr - fr) > 1:
            # Это прыжок (взятие)
            # Ищем сбитую фигуру на диагонали
            curr_r, curr_c = fr + dr, fc + dc
            while (curr_r, curr_c) != to_pos:
                if self.grid[curr_r][curr_c] != self.EMPTY:
                    captured_pos = (curr_r, curr_c)
                    break
                curr_r += dr
                curr_c += dc

        # Перемещаем
        self.grid[tr][tc] = piece
        self.grid[fr][fc] = self.EMPTY

        # Проверяем превращение в дамку
        self.promote_if_needed(tr, tc)
        return True, captured_pos

    def promote_if_needed(self, r: int, c: int) -> None:
        """Превращает простую шашку в дамку при достижении последней горизонтали."""
        piece = self.grid[r][c]
        if piece == self.WHITE and r == 0:
            self.grid[r][c] = self.WHITE_KING
        elif piece == self.BLACK and r == 7:
            self.grid[r][c] = self.BLACK_KING
    # ─── Проверка окончания игры ────────────────────────────────

    def check_winner(self) -> int:
        """
        Проверить победителя.
        Возвращает: 0 — игра идет, 1 (WHITE) — победа Белых, 2 (BLACK) — победа Чёрных.
        """
        white_pieces = self.get_player_pieces(self.WHITE)
        black_pieces = self.get_player_pieces(self.BLACK)

        if not white_pieces:
            return self.BLACK
        if not black_pieces:
            return self.WHITE

        # Проверяем, заблокирован ли игрок, чей ход (это проверяется в Game, но здесь дадим базовый статус)
        # Если у одного из игроков вообще нет ходов, побеждает другой
        has_white_moves = False
        for r, c in white_pieces:
            if self.get_valid_moves(r, c):
                has_white_moves = True
                break

        has_black_moves = False
        for r, c in black_pieces:
            if self.get_valid_moves(r, c):
                has_black_moves = True
                break

        if not has_white_moves and not has_black_moves:
            return 0  # Ничья (редко, но возможно при полной взаимной блокировке)
        if not has_white_moves:
            return self.BLACK
        if not has_black_moves:
            return self.WHITE

        return 0

    # ─── Отрисовка ──────────────────────────────────────────────

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
        """Отрисовка доски в Telegram через Inline-кнопки."""
        if valid_moves is None:
            valid_moves = []

        if not show_hints:
            selected = None
            valid_set = set()
        else:
            valid_set = set(valid_moves)
            
        keyboard = []

        # Текстовые эмодзи
        EMOJI_WHITE = "⚪"
        EMOJI_BLACK = "⚫"
        EMOJI_WHITE_KING = "♕"
        EMOJI_BLACK_KING = "♛"
        EMOJI_SELECTED = "🟡"
        EMOJI_VALID = "🟢"
        EMOJI_LIGHT_CELL = "⠀"
        EMOJI_DARK_CELL = "·"

        for r in range(self.SIZE):
            row_buttons = []
            for c in range(self.SIZE):
                pos = (r, c)
                piece = self.grid[r][c]

                # 1. Сначала определяем подсветки (выбранная или доступный ход)
                if pos == selected:
                    emoji = EMOJI_SELECTED
                elif pos in valid_set:
                    emoji = EMOJI_VALID
                # 2. Затем фигуры
                elif piece == self.WHITE:
                    emoji = EMOJI_WHITE
                elif piece == self.BLACK:
                    emoji = EMOJI_BLACK
                elif piece == self.WHITE_KING:
                    emoji = EMOJI_WHITE_KING
                elif piece == self.BLACK_KING:
                    emoji = EMOJI_BLACK_KING
                # 3. Пустые клетки (чередование)
                else:
                    if (r + c) % 2 == 1:
                        emoji = EMOJI_DARK_CELL
                    else:
                        emoji = EMOJI_LIGHT_CELL

                # callback_data
                cb = f"noop_{r}_{c}" if game_over else f"cell_{r}_{c}"
                row_buttons.append(InlineKeyboardButton(emoji, callback_data=cb))
            keyboard.append(row_buttons)

        # Добавляем кнопки управления (Сдаться, Ничья, Таймер)
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

        return InlineKeyboardMarkup(keyboard)

    def clone(self) -> "Board":
        """Создать копию доски."""
        new_board = Board.__new__(Board)
        new_board.grid = [row[:] for row in self.grid]
        return new_board
