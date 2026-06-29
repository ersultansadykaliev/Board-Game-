"""
Модуль AI для игры «Уголки».
Реализует искусственный интеллект на основе minimax с alpha-beta отсечением
и эвристикой расстояния.
"""

from __future__ import annotations
import random
from typing import Optional

from games.ugolki.board import Board


class AI:
    """Искусственный интеллект для игры «Уголки»."""

    def __init__(self, player: int, depth: int = 2) -> None:
        """
        Args:
            player: номер игрока ИИ (Board.PLAYER1 или Board.PLAYER2)
            depth: глубина поиска minimax
        """
        self.player = player
        self.opponent = Board.PLAYER2 if player == Board.PLAYER1 else Board.PLAYER1
        self.depth = depth

        # Целевые позиции для ИИ (куда нужно привести фигуры)
        if player == Board.PLAYER1:
            # Игрок 1 идёт в дом 1 (позиции P2)
            from config import PLAYER1_HOME

            self.target_positions = PLAYER1_HOME
        else:
            from config import PLAYER2_HOME

            self.target_positions = PLAYER2_HOME

    def get_best_move(
        self, board: Board
    ) -> Optional[tuple[tuple[int, int], tuple[int, int]]]:
        """
        Выбрать лучший ход для ИИ.

        Returns:
            Кортеж (from_pos, to_pos) или None если ходов нет.
        """
        pieces = board.get_player_pieces(self.player)
        if not pieces:
            return None

        best_score = float("-inf")
        best_moves: list[tuple[tuple[int, int], tuple[int, int]]] = []

        for piece_pos in pieces:
            valid_moves = board.get_valid_moves(*piece_pos)
            for move_pos in valid_moves:
                # Симулируем ход
                cloned = board.clone()
                cloned.move_piece(piece_pos, move_pos)

                # Оцениваем позицию
                score = self._minimax(
                    cloned, self.depth - 1, False, float("-inf"), float("inf")
                )

                if score > best_score:
                    best_score = score
                    best_moves = [(piece_pos, move_pos)]
                elif score == best_score:
                    best_moves.append((piece_pos, move_pos))

        if not best_moves:
            return None

        # Если есть несколько равных по оценке ходов — выбираем случайный
        return random.choice(best_moves)

    def _minimax(
        self, board: Board, depth: int, is_maximizing: bool, alpha: float, beta: float
    ) -> float:
        """Алгоритм minimax с alpha-beta отсечением."""
        # Проверяем терминальные состояния
        winner = board.check_winner()
        if winner == 3:
            return 0  # Ничья (одновременное завершение)
        if winner == self.player:
            return 10000 + depth  # Чем быстрее победа, тем лучше
        if winner == self.opponent:
            return -10000 - depth

        if depth == 0:
            return self._evaluate(board)

        current_player = self.player if is_maximizing else self.opponent
        pieces = board.get_player_pieces(current_player)

        if is_maximizing:
            max_eval = float("-inf")
            for piece_pos in pieces:
                valid_moves = board.get_valid_moves(*piece_pos)
                for move_pos in valid_moves:
                    cloned = board.clone()
                    cloned.move_piece(piece_pos, move_pos)
                    eval_score = self._minimax(cloned, depth - 1, False, alpha, beta)
                    max_eval = max(max_eval, eval_score)
                    alpha = max(alpha, eval_score)
                    if beta <= alpha:
                        break
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float("inf")
            for piece_pos in pieces:
                valid_moves = board.get_valid_moves(*piece_pos)
                for move_pos in valid_moves:
                    cloned = board.clone()
                    cloned.move_piece(piece_pos, move_pos)
                    eval_score = self._minimax(cloned, depth - 1, True, alpha, beta)
                    min_eval = min(min_eval, eval_score)
                    beta = min(beta, eval_score)
                    if beta <= alpha:
                        break
                if beta <= alpha:
                    break
            return min_eval

    def _evaluate(self, board: Board) -> float:
        """
        Оценка позиции доски.

        Эвристика:
        1. Суммарное расстояние шашек ИИ до целевых позиций (меньше = лучше)
        2. Суммарное расстояние шашек противника до их целей (больше = лучше)
        3. Бонус за шашки, уже находящиеся в «доме»
        4. Бонус за продвижение вперёд
        """
        my_pieces = board.get_player_pieces(self.player)
        opp_pieces = board.get_player_pieces(self.opponent)

        # Целевые позиции для противника
        if self.player == Board.PLAYER1:
            from config import PLAYER2_HOME

            opp_targets = PLAYER2_HOME
            my_targets = self.target_positions
        else:
            from config import PLAYER1_HOME

            opp_targets = PLAYER1_HOME
            my_targets = self.target_positions

        # Оценка моих фигур
        my_score = 0.0
        my_target_set = set(my_targets)
        for piece in my_pieces:
            min_dist = min(
                self._manhattan_distance(piece, target) for target in my_targets
            )
            my_score -= min_dist * 2  # Штраф за расстояние

            # Бонус за фигуры в доме
            if piece in my_target_set:
                my_score += 15

            # Бонус за продвижение вперёд
            if self.player == Board.PLAYER1:
                my_score += piece[0] + piece[1]  # Ближе к (7,7) — лучше
            else:
                my_score += (7 - piece[0]) + (7 - piece[1])  # Ближе к (0,0) — лучше

        # Оценка фигур противника (хотим чтобы они были далеко от цели)
        opp_score = 0.0
        for piece in opp_pieces:
            min_dist = min(
                self._manhattan_distance(piece, target) for target in opp_targets
            )
            opp_score += min_dist  # Чем дальше противник от цели — тем лучше

        return my_score + opp_score * 0.5

    @staticmethod
    def _chebyshev_distance(pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
        """Расстояние Чебышёва (максимум из разностей координат)."""
        return max(abs(pos1[0] - pos2[0]), abs(pos1[1] - pos2[1]))

    @staticmethod
    def _manhattan_distance(pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
        """Манхэттенское расстояние."""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
