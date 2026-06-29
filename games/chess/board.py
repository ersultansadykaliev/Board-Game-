"""
Модуль доски для игры «Шахматы».
Содержит класс Board с логикой доски, генерацией ходов,
проверкой шаха/мата/пата, рокировкой, взятием на проходе
и превращением пешки.
"""

from __future__ import annotations
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─── Константы фигур ────────────────────────────────────────
# Положительные = белые, отрицательные = чёрные
# |1|=пешка, |2|=ладья, |3|=конь, |4|=слон, |5|=ферзь, |6|=король
EMPTY = 0
W_PAWN, W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING = 1, 2, 3, 4, 5, 6
B_PAWN, B_ROOK, B_KNIGHT, B_BISHOP, B_QUEEN, B_KING = -1, -2, -3, -4, -5, -6

WHITE = 1
BLACK = -1

# ─── Эмодзи фигур ──────────────────────────────────────────
# В Telegram (темная тема) сплошные символы заливаются белым шрифтом, а контурные остаются темными.
# Поэтому для Белых используем сплошные фигуры, а для Черных — контурные.
# ВАЖНО: символ ♟ (пешка) — единственная шахматная фигура с эмодзи-вариантом.
# Telegram ИГНОРИРУЕТ \uFE0E и всегда рисует её как цветную картинку (черную).
# Поэтому мы заменяем пешку на ▲/△ (треугольники без эмодзи-варианта),
# чтобы гарантировать одинаковый цвет со всеми фигурами на стороне.
PIECE_EMOJI = {
    W_KING: "♚\uFE0E", W_QUEEN: "♛\uFE0E", W_ROOK: "♜\uFE0E",
    W_BISHOP: "♝\uFE0E", W_KNIGHT: "♞\uFE0E", W_PAWN: "▲",
    B_KING: "♔\uFE0E", B_QUEEN: "♕\uFE0E", B_ROOK: "♖\uFE0E",
    B_BISHOP: "♗\uFE0E", B_KNIGHT: "♘\uFE0E", B_PAWN: "△",
}

# ─── Эмодзи для пустых клеток (шахматная раскраска) ─────────
EMPTY_LIGHT = "·"
EMPTY_DARK = "·"
EMOJI_SELECTED = "🟡"
EMOJI_VALID_MOVE = "🟢"
EMOJI_CAPTURE = "🔴"

# ─── Начальная расстановка ──────────────────────────────────
INITIAL_BOARD = [
    [B_ROOK, B_KNIGHT, B_BISHOP, B_QUEEN, B_KING, B_BISHOP, B_KNIGHT, B_ROOK],
    [B_PAWN] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [W_PAWN] * 8,
    [W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING, W_BISHOP, W_KNIGHT, W_ROOK],
]

# Ценность фигур для ИИ
PIECE_VALUES = {
    W_PAWN: 100, W_KNIGHT: 320, W_BISHOP: 330,
    W_ROOK: 500, W_QUEEN: 900, W_KING: 20000,
    B_PAWN: 100, B_KNIGHT: 320, B_BISHOP: 330,
    B_ROOK: 500, B_QUEEN: 900, B_KING: 20000,
}


def piece_color(piece: int) -> int:
    """Возвращает цвет фигуры: WHITE(1), BLACK(-1) или 0 для пустой."""
    if piece > 0:
        return WHITE
    elif piece < 0:
        return BLACK
    return 0


def piece_type(piece: int) -> int:
    """Возвращает тип фигуры (всегда положительный)."""
    return abs(piece)


class Board:
    """Шахматная доска 8×8."""

    SIZE = 8

    def __init__(self) -> None:
        """Инициализация доски с начальной расстановкой."""
        self.grid: list[list[int]] = [row[:] for row in INITIAL_BOARD]

        # Права на рокировку
        self.white_king_moved = False
        self.black_king_moved = False
        self.white_rook_a_moved = False  # a1 (левая белая ладья)
        self.white_rook_h_moved = False  # h1 (правая белая ладья)
        self.black_rook_a_moved = False  # a8 (левая чёрная ладья)
        self.black_rook_h_moved = False  # h8 (правая чёрная ладья)

        # Взятие на проходе: координаты клетки, куда можно взять
        self.en_passant_target: Optional[tuple[int, int]] = None

        # Позиции королей (для быстрой проверки шаха)
        self.white_king_pos: tuple[int, int] = (7, 4)
        self.black_king_pos: tuple[int, int] = (0, 4)

        # Счётчик ходов для правила 50 ходов
        self.halfmove_clock: int = 0

        # История позиций для троекратного повторения
        self.position_history: list[str] = []

        # Последний ход (для подсветки)
        self.last_move_from: Optional[tuple[int, int]] = None
        self.last_move_to: Optional[tuple[int, int]] = None

    # ─── Основные методы ────────────────────────────────────
    def is_valid(self, r: int, c: int) -> bool:
        return 0 <= r < self.SIZE and 0 <= c < self.SIZE

    def get_piece(self, r: int, c: int) -> int:
        return self.grid[r][c]

    def _position_hash(self) -> str:
        """Хеш текущей позиции для троекратного повторения."""
        return str(self.grid)

    # ─── Генерация ходов ────────────────────────────────────
    def get_pseudo_legal_moves(
        self, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """
        Генерирует все псевдо-легальные ходы для цвета.
        Не проверяет, остаётся ли король под шахом.
        Возвращает список (from_pos, to_pos).
        """
        moves = []
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                piece = self.grid[r][c]
                if piece_color(piece) != color:
                    continue
                pt = piece_type(piece)
                if pt == 1:  # Пешка
                    moves.extend(self._pawn_moves(r, c, color))
                elif pt == 2:  # Ладья
                    moves.extend(self._sliding_moves(r, c, color, [(0, 1), (0, -1), (1, 0), (-1, 0)]))
                elif pt == 3:  # Конь
                    moves.extend(self._knight_moves(r, c, color))
                elif pt == 4:  # Слон
                    moves.extend(self._sliding_moves(r, c, color, [(1, 1), (1, -1), (-1, 1), (-1, -1)]))
                elif pt == 5:  # Ферзь
                    moves.extend(self._sliding_moves(r, c, color, [
                        (0, 1), (0, -1), (1, 0), (-1, 0),
                        (1, 1), (1, -1), (-1, 1), (-1, -1)
                    ]))
                elif pt == 6:  # Король
                    moves.extend(self._king_moves(r, c, color))
        return moves

    def get_legal_moves(
        self, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Генерирует все легальные ходы (исключает те, что оставляют короля под шахом)."""
        legal = []
        for from_pos, to_pos in self.get_pseudo_legal_moves(color):
            if self._is_move_legal(from_pos, to_pos, color):
                legal.append((from_pos, to_pos))
        return legal

    def get_legal_moves_from(
        self, r: int, c: int
    ) -> list[tuple[int, int]]:
        """Получить все легальные ходы для конкретной фигуры."""
        piece = self.grid[r][c]
        if piece == EMPTY:
            return []
        color = piece_color(piece)
        destinations = []
        for from_pos, to_pos in self.get_legal_moves(color):
            if from_pos == (r, c):
                destinations.append(to_pos)
        return destinations

    # ─── Ходы пешки ─────────────────────────────────────────
    def _pawn_moves(
        self, r: int, c: int, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        moves = []
        direction = -1 if color == WHITE else 1  # Белые идут вверх, чёрные вниз
        start_row = 6 if color == WHITE else 1

        # Ход вперёд на 1
        nr = r + direction
        if self.is_valid(nr, c) and self.grid[nr][c] == EMPTY:
            moves.append(((r, c), (nr, c)))
            # Ход вперёд на 2 с начальной позиции
            nnr = r + 2 * direction
            if r == start_row and self.grid[nnr][c] == EMPTY:
                moves.append(((r, c), (nnr, c)))

        # Взятие по диагонали
        for dc in (-1, 1):
            nc = c + dc
            if not self.is_valid(nr, nc):
                continue
            target = self.grid[nr][nc]
            if target != EMPTY and piece_color(target) != color:
                moves.append(((r, c), (nr, nc)))

        # Взятие на проходе
        if self.en_passant_target:
            ep_r, ep_c = self.en_passant_target
            if ep_r == r + direction and abs(ep_c - c) == 1:
                moves.append(((r, c), (ep_r, ep_c)))

        return moves

    # ─── Ходы коня ──────────────────────────────────────────
    def _knight_moves(
        self, r: int, c: int, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        moves = []
        offsets = [
            (-2, -1), (-2, 1), (-1, -2), (-1, 2),
            (1, -2), (1, 2), (2, -1), (2, 1)
        ]
        for dr, dc in offsets:
            nr, nc = r + dr, c + dc
            if self.is_valid(nr, nc):
                target = self.grid[nr][nc]
                if target == EMPTY or piece_color(target) != color:
                    moves.append(((r, c), (nr, nc)))
        return moves

    # ─── Скользящие ходы (ладья, слон, ферзь) ───────────────
    def _sliding_moves(
        self, r: int, c: int, color: int,
        directions: list[tuple[int, int]]
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        moves = []
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while self.is_valid(nr, nc):
                target = self.grid[nr][nc]
                if target == EMPTY:
                    moves.append(((r, c), (nr, nc)))
                elif piece_color(target) != color:
                    moves.append(((r, c), (nr, nc)))  # Взятие
                    break
                else:
                    break  # Своя фигура блокирует
                nr += dr
                nc += dc
        return moves

    # ─── Ходы короля ────────────────────────────────────────
    def _king_moves(
        self, r: int, c: int, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        moves = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self.is_valid(nr, nc):
                    target = self.grid[nr][nc]
                    if target == EMPTY or piece_color(target) != color:
                        moves.append(((r, c), (nr, nc)))

        # Рокировка
        moves.extend(self._castling_moves(r, c, color))
        return moves

    def _castling_moves(
        self, r: int, c: int, color: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Генерация ходов рокировки."""
        moves = []
        if self.is_in_check(color):
            return moves

        if color == WHITE:
            if self.white_king_moved:
                return moves
            king_row = 7
            # Короткая рокировка (O-O): король e1 -> g1
            if (
                not self.white_rook_h_moved
                and self.grid[king_row][5] == EMPTY
                and self.grid[king_row][6] == EMPTY
                and self.grid[king_row][7] == W_ROOK
                and not self._is_square_attacked(king_row, 5, BLACK)
                and not self._is_square_attacked(king_row, 6, BLACK)
            ):
                moves.append(((r, c), (king_row, 6)))

            # Длинная рокировка (O-O-O): король e1 -> c1
            if (
                not self.white_rook_a_moved
                and self.grid[king_row][3] == EMPTY
                and self.grid[king_row][2] == EMPTY
                and self.grid[king_row][1] == EMPTY
                and self.grid[king_row][0] == W_ROOK
                and not self._is_square_attacked(king_row, 3, BLACK)
                and not self._is_square_attacked(king_row, 2, BLACK)
            ):
                moves.append(((r, c), (king_row, 2)))
        else:
            if self.black_king_moved:
                return moves
            king_row = 0
            # Короткая рокировка
            if (
                not self.black_rook_h_moved
                and self.grid[king_row][5] == EMPTY
                and self.grid[king_row][6] == EMPTY
                and self.grid[king_row][7] == B_ROOK
                and not self._is_square_attacked(king_row, 5, WHITE)
                and not self._is_square_attacked(king_row, 6, WHITE)
            ):
                moves.append(((r, c), (king_row, 6)))

            # Длинная рокировка
            if (
                not self.black_rook_a_moved
                and self.grid[king_row][3] == EMPTY
                and self.grid[king_row][2] == EMPTY
                and self.grid[king_row][1] == EMPTY
                and self.grid[king_row][0] == B_ROOK
                and not self._is_square_attacked(king_row, 3, WHITE)
                and not self._is_square_attacked(king_row, 2, WHITE)
            ):
                moves.append(((r, c), (king_row, 2)))
        return moves

    # ─── Проверка шаха ──────────────────────────────────────
    def _is_square_attacked(self, r: int, c: int, by_color: int) -> bool:
        """Проверяет, атакована ли клетка (r, c) фигурами цвета by_color."""
        # Атака конём
        for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                        (1, -2), (1, 2), (2, -1), (2, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_valid(nr, nc):
                p = self.grid[nr][nc]
                if piece_type(p) == 3 and piece_color(p) == by_color:
                    return True

        # Атака по диагонали (слон, ферзь)
        for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            nr, nc = r + dr, c + dc
            while self.is_valid(nr, nc):
                p = self.grid[nr][nc]
                if p != EMPTY:
                    if piece_color(p) == by_color and piece_type(p) in (4, 5):
                        return True
                    break
                nr += dr
                nc += dc

        # Атака по линиям (ладья, ферзь)
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            while self.is_valid(nr, nc):
                p = self.grid[nr][nc]
                if p != EMPTY:
                    if piece_color(p) == by_color and piece_type(p) in (2, 5):
                        return True
                    break
                nr += dr
                nc += dc

        # Атака королём
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if self.is_valid(nr, nc):
                    p = self.grid[nr][nc]
                    if piece_type(p) == 6 and piece_color(p) == by_color:
                        return True

        # Атака пешкой
        pawn_dir = 1 if by_color == WHITE else -1
        for dc in (-1, 1):
            nr, nc = r - pawn_dir, c + dc
            if self.is_valid(nr, nc):
                p = self.grid[nr][nc]
                if piece_type(p) == 1 and piece_color(p) == by_color:
                    return True

        return False

    def is_in_check(self, color: int) -> bool:
        """Проверяет, находится ли король данного цвета под шахом."""
        king_pos = self.white_king_pos if color == WHITE else self.black_king_pos
        opponent = BLACK if color == WHITE else WHITE
        return self._is_square_attacked(king_pos[0], king_pos[1], opponent)

    def _is_move_legal(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int], color: int
    ) -> bool:
        """Проверяет, является ли ход легальным (не оставляет короля под шахом)."""
        # Делаем ход на копии
        cloned = self.clone()
        cloned._apply_move_raw(from_pos, to_pos)
        return not cloned.is_in_check(color)

    # ─── Выполнение хода ────────────────────────────────────
    def make_move(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int],
        promotion_piece: int = 5  # По умолчанию превращение в ферзя
    ) -> str:
        """
        Выполнить ход. Возвращает строку-результат:
        'move', 'capture', 'castling_short', 'castling_long',
        'en_passant', 'promotion', 'check', 'checkmate', 'stalemate'
        """
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.grid[fr][fc]
        color = piece_color(piece)
        pt = piece_type(piece)
        captured = self.grid[tr][tc]
        result = "capture" if captured != EMPTY else "move"

        # Обновляем счётчик 50 ходов
        if pt == 1 or captured != EMPTY:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # ─── Специальные ходы ───────────────────────────────

        # Рокировка
        if pt == 6 and abs(tc - fc) == 2:
            if tc == 6:  # Короткая
                # Перемещаем ладью
                rook = self.grid[fr][7]
                self.grid[fr][7] = EMPTY
                self.grid[fr][5] = rook
                result = "castling_short"
            elif tc == 2:  # Длинная
                rook = self.grid[fr][0]
                self.grid[fr][0] = EMPTY
                self.grid[fr][3] = rook
                result = "castling_long"

        # Взятие на проходе
        if pt == 1 and to_pos == self.en_passant_target:
            # Убираем пешку противника
            captured_pawn_row = tr + (1 if color == WHITE else -1)
            self.grid[captured_pawn_row][tc] = EMPTY
            result = "en_passant"

        # Обновляем en passant target
        self.en_passant_target = None
        if pt == 1 and abs(tr - fr) == 2:
            # Пешка прошла на 2 клетки — отмечаем поле для взятия на проходе
            self.en_passant_target = ((fr + tr) // 2, fc)

        # Перемещаем фигуру
        self.grid[tr][tc] = piece
        self.grid[fr][fc] = EMPTY

        # Превращение пешки
        promo_row = 0 if color == WHITE else 7
        if pt == 1 and tr == promo_row:
            self.grid[tr][tc] = promotion_piece * color
            result = "promotion"

        # Обновляем права на рокировку
        self._update_castling_rights(from_pos, to_pos, piece)

        # Обновляем позицию короля
        if pt == 6:
            if color == WHITE:
                self.white_king_pos = (tr, tc)
            else:
                self.black_king_pos = (tr, tc)

        # Запоминаем последний ход
        self.last_move_from = from_pos
        self.last_move_to = to_pos

        # Сохраняем позицию в историю
        self.position_history.append(self._position_hash())

        # Проверяем шах/мат/пат для ПРОТИВНИКА
        opponent = BLACK if color == WHITE else WHITE
        if self.is_in_check(opponent):
            if not self.get_legal_moves(opponent):
                return "checkmate"
            return "check" if result == "move" else f"{result}_check"

        if not self.get_legal_moves(opponent):
            return "stalemate"

        return result

    def _apply_move_raw(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int]
    ) -> None:
        """Применить ход без проверок (для тестирования легальности)."""
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.grid[fr][fc]
        pt = piece_type(piece)
        color = piece_color(piece)

        # Рокировка
        if pt == 6 and abs(tc - fc) == 2:
            if tc == 6:
                rook = self.grid[fr][7]
                self.grid[fr][7] = EMPTY
                self.grid[fr][5] = rook
            elif tc == 2:
                rook = self.grid[fr][0]
                self.grid[fr][0] = EMPTY
                self.grid[fr][3] = rook

        # Взятие на проходе
        if pt == 1 and to_pos == self.en_passant_target:
            captured_pawn_row = tr + (1 if color == WHITE else -1)
            self.grid[captured_pawn_row][tc] = EMPTY

        # Перемещение
        self.grid[tr][tc] = piece
        self.grid[fr][fc] = EMPTY

        # Превращение
        promo_row = 0 if color == WHITE else 7
        if pt == 1 and tr == promo_row:
            self.grid[tr][tc] = 5 * color  # Ферзь

        # Обновляем позицию короля
        if pt == 6:
            if color == WHITE:
                self.white_king_pos = (tr, tc)
            else:
                self.black_king_pos = (tr, tc)

    def _update_castling_rights(
        self, from_pos: tuple[int, int], to_pos: tuple[int, int], piece: int
    ) -> None:
        """Обновить права на рокировку после хода."""
        fr, fc = from_pos
        pt = piece_type(piece)
        color = piece_color(piece)

        if pt == 6:  # Король сходил
            if color == WHITE:
                self.white_king_moved = True
            else:
                self.black_king_moved = True

        if pt == 2:  # Ладья сходила
            if color == WHITE:
                if from_pos == (7, 0):
                    self.white_rook_a_moved = True
                elif from_pos == (7, 7):
                    self.white_rook_h_moved = True
            else:
                if from_pos == (0, 0):
                    self.black_rook_a_moved = True
                elif from_pos == (0, 7):
                    self.black_rook_h_moved = True

        # Если ладью съели — тоже теряем право на рокировку
        tr, tc = to_pos
        if to_pos == (7, 0):
            self.white_rook_a_moved = True
        elif to_pos == (7, 7):
            self.white_rook_h_moved = True
        elif to_pos == (0, 0):
            self.black_rook_a_moved = True
        elif to_pos == (0, 7):
            self.black_rook_h_moved = True

    # ─── Проверки конца игры ────────────────────────────────
    def is_checkmate(self, color: int) -> bool:
        """Проверяет, стоит ли мат игроку color."""
        return self.is_in_check(color) and not self.get_legal_moves(color)

    def is_stalemate(self, color: int) -> bool:
        """Проверяет пат (нет легальных ходов, но нет шаха)."""
        return not self.is_in_check(color) and not self.get_legal_moves(color)

    def is_fifty_move_draw(self) -> bool:
        """Проверяет правило 50 ходов (100 полуходов)."""
        return self.halfmove_clock >= 100

    def is_threefold_repetition(self) -> bool:
        """Проверяет троекратное повторение позиции."""
        if len(self.position_history) < 3:
            return False
        current = self.position_history[-1]
        return self.position_history.count(current) >= 3

    def is_insufficient_material(self) -> bool:
        """Проверяет недостаточность материала для мата."""
        pieces = []
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                p = self.grid[r][c]
                if p != EMPTY:
                    pieces.append(p)

        # Король против короля
        if len(pieces) == 2:
            return True
        # Король + слон/конь против короля
        if len(pieces) == 3:
            for p in pieces:
                if piece_type(p) in (3, 4):  # Конь или слон
                    return True
        return False

    # ─── Подсчёт материала ──────────────────────────────────
    def count_material(self, color: int) -> int:
        """Подсчёт общей ценности фигур цвета."""
        total = 0
        for r in range(self.SIZE):
            for c in range(self.SIZE):
                p = self.grid[r][c]
                if p != EMPTY and piece_color(p) == color:
                    total += PIECE_VALUES.get(abs(p), 0)
        return total

    # ─── Отображение ────────────────────────────────────────
    def to_inline_keyboard(
        self,
        selected: Optional[tuple[int, int]] = None,
        valid_moves: Optional[list[tuple[int, int]]] = None,
        game_over: bool = False,
        timer_text: str = "00:00 ⏱",
        finish_reason: str = "",
        flip_board: bool = False,
        show_hints: bool = True,
        **kwargs,
    ) -> InlineKeyboardMarkup:
        """Генерация InlineKeyboardMarkup для Telegram."""
        if valid_moves is None:
            valid_moves = []

        if not show_hints:
            selected = None
            valid_set = set()
        else:
            valid_set = set(valid_moves)
            
        keyboard = []

        rows = range(self.SIZE) if not flip_board else reversed(range(self.SIZE))
        cols = range(self.SIZE) if not flip_board else reversed(range(self.SIZE))

        for r in rows:
            row_buttons = []
            for c in cols:
                pos = (r, c)
                piece = self.grid[r][c]

                if pos == selected:
                    emoji = EMOJI_SELECTED
                elif pos in valid_set:
                    if piece != EMPTY:
                        emoji = EMOJI_CAPTURE  # Можно взять фигуру
                    else:
                        emoji = EMOJI_VALID_MOVE
                elif piece != EMPTY:
                    emoji = PIECE_EMOJI[piece]
                else:
                    # Шахматная раскраска пустых клеток
                    emoji = EMPTY_LIGHT if (r + c) % 2 == 0 else EMPTY_DARK

                cb = f"noop_{r}_{c}" if game_over else f"cell_{r}_{c}"
                row_buttons.append(
                    InlineKeyboardButton(emoji, callback_data=cb)
                )
            keyboard.append(row_buttons)

        # Кнопки управления
        if not game_over:
            hints_btn = InlineKeyboardButton(
                "💡 Вкл" if show_hints else "💡 Выкл", callback_data="toggle_hints"
            )
            keyboard.append([
                InlineKeyboardButton("🏳 Сдаться", callback_data="surrender"),
                InlineKeyboardButton("🤝 Ничья", callback_data="draw"),
                hints_btn,
                InlineKeyboardButton(timer_text, callback_data="noop_time"),
            ])

        return InlineKeyboardMarkup(keyboard)

    # ─── Клонирование ───────────────────────────────────────
    def clone(self) -> Board:
        """Создать глубокую копию доски."""
        new = Board.__new__(Board)
        new.grid = [row[:] for row in self.grid]
        new.white_king_moved = self.white_king_moved
        new.black_king_moved = self.black_king_moved
        new.white_rook_a_moved = self.white_rook_a_moved
        new.white_rook_h_moved = self.white_rook_h_moved
        new.black_rook_a_moved = self.black_rook_a_moved
        new.black_rook_h_moved = self.black_rook_h_moved
        new.en_passant_target = self.en_passant_target
        new.white_king_pos = self.white_king_pos
        new.black_king_pos = self.black_king_pos
        new.halfmove_clock = self.halfmove_clock
        new.position_history = self.position_history[:]
        new.last_move_from = self.last_move_from
        new.last_move_to = self.last_move_to
        return new

    def __str__(self) -> str:
        """Текстовое представление доски (для отладки)."""
        lines = ["  a b c d e f g h"]
        for r in range(self.SIZE):
            row_str = " ".join(
                PIECE_EMOJI.get(self.grid[r][c], "·")
                for c in range(self.SIZE)
            )
            lines.append(f"{8 - r} {row_str}")
        return "\n".join(lines)
