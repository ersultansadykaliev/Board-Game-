"""
Модуль ИИ для игры «Русские шашки».
"""

from __future__ import annotations
import random
from typing import Optional

from games.checkers.board import Board


class AI:
    """Искусственный интеллект для игры в Шашки на основе алгоритма Минимакс."""

    def __init__(self, player: int, depth: int = 3) -> None:
        """
        Args:
            player: номер игрока ИИ (Board.WHITE или Board.BLACK)
            depth: глубина поиска
        """
        self.player = player
        self.opponent = Board.WHITE if player == Board.BLACK else Board.BLACK
        self.depth = depth

    def get_best_move(
        self, board: Board, active_piece: Optional[tuple[int, int]] = None, ignored_captured: set[tuple[int, int]] = None
    ) -> Optional[tuple[tuple[int, int], tuple[int, int]]]:
        """
        Выбрать лучший ход для ИИ.
        """
        # Находим все фигуры, которые могут ходить
        if active_piece is not None:
            pieces = [active_piece]
        else:
            pieces = board.get_player_pieces(self.player)

        best_score = float("-inf")
        best_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []

        # Сначала проверяем, есть ли обязательные взятия на доске
        # Если есть, get_valid_moves вернет только взятия
        has_any_moves = False
        for r, c in pieces:
            valid_moves = board.get_valid_moves(r, c, active_piece, ignored_captured)
            if valid_moves:
                has_any_moves = True
                for move in valid_moves:
                    # Симулируем ход
                    cloned = board.clone()
                    _, captured_pos = cloned.move_piece((r, c), move)

                    ignored = {captured_pos} if captured_pos else set()

                    # Проверяем, продолжается ли серия взятий
                    # (в разработке: для простоты первого уровня дерева проверяем дальнейшие прыжки)
                    is_maximizing_next = False
                    next_active = None

                    if captured_pos:
                        # Проверяем превращение в дамку
                        is_king = cloned.get_piece(move[0], move[1]) in (
                            Board.WHITE_KING,
                            Board.BLACK_KING,
                        )
                        # И наличие дальнейших прыжков
                        next_caps = cloned.get_captures_for_piece(
                            move[0], move[1], ignored
                        )
                        if next_caps and not is_king:
                            is_maximizing_next = True
                            next_active = move

                    # Вычисляем минимакс
                    score = self._minimax(
                        cloned,
                        self.depth - 1,
                        is_maximizing_next,
                        next_active,
                        ignored,
                        float("-inf"),
                        float("inf"),
                    )

                    if score > best_score:
                        best_score = score
                        best_moves = [((r, c), move)]
                    elif score == best_score:
                        best_moves.append(((r, c), move))

        if not has_any_moves or not best_moves:
            return None

        return random.choice(best_moves)

    def _minimax(
        self,
        board: Board,
        depth: int,
        is_maximizing: bool,
        active_piece: Optional[tuple[int, int]],
        ignored_captured: set[tuple[int, int]],
        alpha: float,
        beta: float,
    ) -> float:
        """Алгоритм минимакса с альфа-бета отсечением."""
        winner = board.check_winner()
        if winner == self.player:
            return 10000 + depth
        if winner == self.opponent:
            return -10000 - depth

        if depth == 0:
            return self._evaluate(board)

        current_player = self.player if is_maximizing else self.opponent

        # Получаем фигуры игрока, который ходит
        if active_piece is not None:
            pieces = [active_piece]
        else:
            pieces = board.get_player_pieces(current_player)

        # Собираем все ходы для этого игрока
        all_moves = []
        for r, c in pieces:
            valid_moves = board.get_valid_moves(r, c, active_piece, ignored_captured)
            for m in valid_moves:
                all_moves.append(((r, c), m))

        if not all_moves:
            # Если нет ходов — проигрыш текущего игрока
            return -10000 - depth if is_maximizing else 10000 + depth

        if is_maximizing:
            max_eval = float("-inf")
            for from_pos, to_pos in all_moves:
                cloned = board.clone()
                _, captured_pos = cloned.move_piece(from_pos, to_pos)

                next_ignored = ignored_captured.copy()
                if captured_pos:
                    next_ignored.add(captured_pos)

                is_maximizing_next = False
                next_active = None

                if captured_pos:
                    is_king = cloned.get_piece(to_pos[0], to_pos[1]) in (
                        Board.WHITE_KING,
                        Board.BLACK_KING,
                    )
                    next_caps = cloned.get_captures_for_piece(
                        to_pos[0], to_pos[1], next_ignored
                    )
                    if next_caps and not is_king:
                        is_maximizing_next = True
                        next_active = to_pos

                eval_score = self._minimax(
                    cloned,
                    depth - 1,
                    is_maximizing_next,
                    next_active,
                    next_ignored,
                    alpha,
                    beta,
                )
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float("inf")
            for from_pos, to_pos in all_moves:
                cloned = board.clone()
                _, captured_pos = cloned.move_piece(from_pos, to_pos)

                next_ignored = ignored_captured.copy()
                if captured_pos:
                    next_ignored.add(captured_pos)

                is_maximizing_next = True
                next_active = None

                if captured_pos:
                    is_king = cloned.get_piece(to_pos[0], to_pos[1]) in (
                        Board.WHITE_KING,
                        Board.BLACK_KING,
                    )
                    next_caps = cloned.get_captures_for_piece(
                        to_pos[0], to_pos[1], next_ignored
                    )
                    if next_caps and not is_king:
                        is_maximizing_next = False
                        next_active = to_pos

                eval_score = self._minimax(
                    cloned,
                    depth - 1,
                    is_maximizing_next,
                    next_active,
                    next_ignored,
                    alpha,
                    beta,
                )
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def _evaluate(self, board: Board) -> float:
        """Эвристическая оценка состояния доски."""
        score = 0.0

        for r in range(Board.SIZE):
            for c in range(Board.SIZE):
                piece = board.grid[r][c]
                if piece == Board.EMPTY:
                    continue

                # Оценка материала
                if piece == Board.WHITE:
                    val = 100.0
                    # Бонус за продвижение белых вверх (ряд 7 -> ряд 0)
                    val += (7 - r) * 10.0
                elif piece == Board.WHITE_KING:
                    val = 350.0
                elif piece == Board.BLACK:
                    val = -100.0
                    # Бонус за продвижение черных вниз (ряд 0 -> ряд 7)
                    val -= r * 10.0
                elif piece == Board.BLACK_KING:
                    val = -350.0
                else:
                    val = 0.0

                # Небольшой бонус за контроль центра
                if c in (2, 3, 4, 5) and r in (2, 3, 4, 5):
                    if piece in (Board.WHITE, Board.WHITE_KING):
                        val += 10.0
                    else:
                        val -= 10.0

                score += val

        # Если ИИ играет за Черных, инвертируем знак, чтобы максимизировать для Черных
        if self.player == Board.BLACK:
            score = -score

        return score
