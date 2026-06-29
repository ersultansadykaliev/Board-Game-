"""
Модуль AI для игры «Шахматы».
Реализует искусственный интеллект на основе Minimax с альфа-бета отсечением,
оценочной функцией на основе ценности фигур и позиционных таблиц.
"""

from __future__ import annotations
import random
from typing import Optional

from games.chess.board import (
    Board, WHITE, BLACK, EMPTY,
    piece_color, piece_type, PIECE_VALUES,
)

# ─── Позиционные таблицы (бонусы за позицию на доске) ───────
# Значения с точки зрения БЕЛЫХ (для чёрных зеркально)

PAWN_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5,  5, 10, 25, 25, 10,  5,  5],
    [0,  0,  0, 20, 20,  0,  0,  0],
    [5, -5,-10,  0,  0,-10, -5,  5],
    [5, 10, 10,-20,-20, 10, 10,  5],
    [0,  0,  0,  0,  0,  0,  0,  0],
]

KNIGHT_TABLE = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50],
]

BISHOP_TABLE = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20],
]

ROOK_TABLE = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [0,  0,  0,  5,  5,  0,  0,  0],
]

QUEEN_TABLE = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [-5,   0,  5,  5,  5,  5,  0, -5],
    [0,    0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20],
]

KING_TABLE_MID = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [20, 20,  0,  0,  0,  0, 20, 20],
    [20, 30, 10,  0,  0, 10, 30, 20],
]

POSITION_TABLES = {
    1: PAWN_TABLE,
    2: ROOK_TABLE,
    3: KNIGHT_TABLE,
    4: BISHOP_TABLE,
    5: QUEEN_TABLE,
    6: KING_TABLE_MID,
}


class AI:
    """Искусственный интеллект для шахмат."""

    def __init__(self, color: int, depth: int = 3) -> None:
        self.color = color
        self.opponent = BLACK if color == WHITE else WHITE
        self.depth = depth

    def get_best_move(
        self, board: Board
    ) -> Optional[tuple[tuple[int, int], tuple[int, int]]]:
        """Выбрать лучший ход."""
        legal_moves = board.get_legal_moves(self.color)
        if not legal_moves:
            return None

        # Сортируем ходы: взятия первыми (для лучшего альфа-бета отсечения)
        legal_moves.sort(
            key=lambda m: self._move_priority(board, m),
            reverse=True,
        )

        best_score = float("-inf")
        best_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []

        for from_pos, to_pos in legal_moves:
            cloned = board.clone()
            cloned.make_move(from_pos, to_pos)

            score = self._minimax(
                cloned, self.depth - 1, False,
                float("-inf"), float("inf"),
            )

            if score > best_score:
                best_score = score
                best_moves = [(from_pos, to_pos)]
            elif score == best_score:
                best_moves.append((from_pos, to_pos))

        return random.choice(best_moves) if best_moves else None

    def _move_priority(
        self, board: Board,
        move: tuple[tuple[int, int], tuple[int, int]],
    ) -> int:
        """Приоритет хода для сортировки (взятия ценных фигур первыми)."""
        _, (tr, tc) = move
        target = board.grid[tr][tc]
        if target != EMPTY:
            return PIECE_VALUES.get(abs(target), 0)
        return 0

    def _minimax(
        self, board: Board, depth: int, is_maximizing: bool,
        alpha: float, beta: float,
    ) -> float:
        """Minimax с альфа-бета отсечением."""
        current_color = self.color if is_maximizing else self.opponent

        # Терминальные состояния
        if board.is_checkmate(current_color):
            return -20000 - depth if is_maximizing else 20000 + depth
        if board.is_stalemate(current_color):
            return 0
        if board.is_fifty_move_draw() or board.is_insufficient_material():
            return 0

        if depth == 0:
            return self._evaluate(board)

        moves = board.get_legal_moves(current_color)
        # Сортируем для лучшего отсечения
        moves.sort(
            key=lambda m: self._move_priority(board, m),
            reverse=True,
        )

        if is_maximizing:
            max_eval = float("-inf")
            for from_pos, to_pos in moves:
                cloned = board.clone()
                cloned.make_move(from_pos, to_pos)
                score = self._minimax(cloned, depth - 1, False, alpha, beta)
                max_eval = max(max_eval, score)
                alpha = max(alpha, score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float("inf")
            for from_pos, to_pos in moves:
                cloned = board.clone()
                cloned.make_move(from_pos, to_pos)
                score = self._minimax(cloned, depth - 1, True, alpha, beta)
                min_eval = min(min_eval, score)
                beta = min(beta, score)
                if beta <= alpha:
                    break
            return min_eval

    def _evaluate(self, board: Board) -> float:
        """Оценка позиции доски."""
        score = 0.0

        for r in range(board.SIZE):
            for c in range(board.SIZE):
                piece = board.grid[r][c]
                if piece == EMPTY:
                    continue

                color = piece_color(piece)
                pt = piece_type(piece)
                value = PIECE_VALUES.get(pt, 0)

                # Позиционный бонус
                table = POSITION_TABLES.get(pt)
                if table:
                    if color == WHITE:
                        pos_bonus = table[r][c]
                    else:
                        pos_bonus = table[7 - r][c]
                else:
                    pos_bonus = 0

                if color == self.color:
                    score += value + pos_bonus
                else:
                    score -= value + pos_bonus

        # Бонус за подвижность (количество ходов)
        my_moves = len(board.get_legal_moves(self.color))
        opp_moves = len(board.get_legal_moves(self.opponent))
        score += (my_moves - opp_moves) * 5

        return score
