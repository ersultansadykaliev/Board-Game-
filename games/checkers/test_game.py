"""
Юнит-тесты для игры «Русские шашки».
"""

import unittest

from games.checkers.board import Board
from games.checkers.game import Game, GameMode


class TestCheckers(unittest.TestCase):
    def setUp(self):
        self.board = Board()
        self.game = Game("test_checkers", 111, "Player1", GameMode.PVP)
        self.game.join(222, "Player2")  # PvP game starts

    def test_initial_board_setup(self):
        """Проверка начальной расстановки шашек."""
        # У белых должно быть 12 шашек
        white_pieces = self.board.get_player_pieces(Board.WHITE)
        self.assertEqual(len(white_pieces), 12)
        for r, c in white_pieces:
            self.assertEqual(self.board.get_piece(r, c), Board.WHITE)
            self.assertTrue((r + c) % 2 == 1)

        # У чёрных должно быть 12 шашек
        black_pieces = self.board.get_player_pieces(Board.BLACK)
        self.assertEqual(len(black_pieces), 12)
        for r, c in black_pieces:
            self.assertEqual(self.board.get_piece(r, c), Board.BLACK)
            self.assertTrue((r + c) % 2 == 1)

    def test_normal_move_validation(self):
        """Простая шашка может ходить только вперед по диагонали на 1 клетку."""
        # Белая шашка на (5, 0)
        # Должна иметь ход на (4, 1)
        moves = self.board.get_valid_moves(5, 0)
        self.assertIn((4, 1), moves)
        self.assertEqual(len(moves), 1)

        # Белая шашка на (5, 2)
        # Должна иметь ходы на (4, 1) и (4, 3)
        moves = self.board.get_valid_moves(5, 2)
        self.assertIn((4, 1), moves)
        self.assertIn((4, 3), moves)
        self.assertEqual(len(moves), 2)

    def test_mandatory_capture(self):
        """Если есть взятие, обычные ходы заблокированы."""
        # Очистим доску и расставим специальную позицию
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]

        # Белая шашка на (4, 4)
        # Чёрная шашка на (3, 3)
        self.game.board.set_piece(4, 4, Board.WHITE)
        self.game.board.set_piece(3, 3, Board.BLACK)

        # Белая шашка на (5, 1) — обычная шашка вдали
        self.game.board.set_piece(5, 1, Board.WHITE)

        # 1. Проверяем, что на всей доске есть взятия
        all_caps = self.game.board.get_all_valid_captures(Board.WHITE)
        self.assertIn((4, 4), all_caps)
        self.assertIn((2, 2), all_caps[(4, 4)])

        # 2. Шашка на (5, 1) не должна иметь ходов вообще (потому что (4, 4) обязана бить)
        moves_far = self.game.board.get_valid_moves(5, 1)
        self.assertEqual(moves_far, [])

        # 3. Шашка на (4, 4) должна иметь только ход-взятие на (2, 2)
        moves_cap = self.game.board.get_valid_moves(4, 4)
        self.assertEqual(moves_cap, [(2, 2)])

    def test_backward_capture_for_simple_piece(self):
        """Простая шашка может бить назад."""
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]
        # Белая на (3, 3), Чёрная на (4, 4)
        # Белые бьют назад на (5, 5)
        self.game.board.set_piece(3, 3, Board.WHITE)
        self.game.board.set_piece(4, 4, Board.BLACK)

        moves = self.game.board.get_valid_moves(3, 3)
        self.assertEqual(moves, [(5, 5)])

    def test_king_movement_and_capture(self):
        """Дамка ходит на любое расстояние и бьет на любое расстояние."""
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]

        # Белая дамка на (3, 3)
        self.game.board.set_piece(3, 3, Board.WHITE_KING)

        # 1. Проверяем обычные ходы дамки по диагонали d1-h5
        moves = self.game.board.get_valid_moves(3, 3)
        # Должна ходить до краев доски
        self.assertIn((0, 0), moves)
        self.assertIn((7, 7), moves)
        self.assertIn((6, 0), moves)
        self.assertIn((0, 6), moves)

        # 2. Поставим соперника на пути
        # Чёрная на (5, 5)
        self.game.board.set_piece(5, 5, Board.BLACK)

        # Теперь дамка обязана бить.
        # Она может приземлиться на (6, 6) или (7, 7) за сбитой фигурой.
        moves_cap = self.game.board.get_valid_moves(3, 3)
        self.assertEqual(len(moves_cap), 2)
        self.assertIn((6, 6), moves_cap)
        self.assertIn((7, 7), moves_cap)

    def test_serial_capture(self):
        """Серия прыжков одной шашкой."""
        # Белые начинают серию прыжков
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]

        self.game.board.set_piece(6, 6, Board.WHITE)
        self.game.board.set_piece(5, 5, Board.BLACK)
        self.game.board.set_piece(3, 3, Board.BLACK)
        self.game.board.set_piece(
            0, 2, Board.BLACK
        )  # Extra piece so White doesn't win immediately

        # Белая на (6, 6) бьет на (4, 4), затем оттуда бьет на (2, 2)
        # 1. Первый клик на (6, 6)
        res = self.game.handle_click(111, 6, 6)
        self.assertEqual(res, "selected")
        self.assertEqual(self.game.valid_moves, [(4, 4)])

        # 2. Ход на (4, 4)
        res2 = self.game.handle_click(111, 4, 4)
        # Серия продолжается, так как с (4, 4) можно побить черную на (3, 3)
        self.assertEqual(res2, "moved_serial")
        self.assertEqual(self.game.active_capture_piece, (4, 4))
        self.assertEqual(self.game.selected_piece, (4, 4))
        self.assertIn((2, 2), self.game.valid_moves)

        # Чёрная шашка на (5, 5) побита, но еще не убрана (турский удар)
        self.assertIn((5, 5), self.game.ignored_captured)
        self.assertEqual(self.game.board.get_piece(5, 5), Board.BLACK)

        # 3. Завершаем ход на (2, 2)
        res3 = self.game.handle_click(111, 2, 2)
        self.assertEqual(res3, "moved")

        # Ход перешел к Чёрным
        self.assertEqual(self.game.current_turn, Board.BLACK)
        self.assertIsNone(self.game.active_capture_piece)

        # Проверяем, что обе сбитые шашки убраны с доски
        self.assertEqual(self.game.board.get_piece(5, 5), Board.EMPTY)
        self.assertEqual(self.game.board.get_piece(3, 3), Board.EMPTY)

    def test_king_conversion(self):
        """Превращение простой шашки в дамку при достижении последней горизонтали."""
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]
        self.game.board.grid[1][1] = Board.WHITE
        self.game.board.grid[0][7] = Board.BLACK  # Добавляем черную шашку, чтобы не было моментальной победы
        
        # Ход белой шашки на последнюю горизонталь (строка 0)
        res = self.game.handle_click(111, 1, 1)
        self.assertEqual(res, "selected")
        res2 = self.game.handle_click(111, 0, 0)
        self.assertEqual(res2, "moved")
        
        # Проверяем, что шашка стала дамкой
        self.assertEqual(self.game.board.get_piece(0, 0), Board.WHITE_KING)

    def test_15_moves_draw(self):
        """Ничья после 15 ходов дамок без взятий."""
        self.game.board.grid = [[Board.EMPTY] * 8 for _ in range(8)]
        self.game.board.grid[0][0] = Board.WHITE_KING
        self.game.board.grid[7][7] = Board.BLACK_KING
        
        self.game.draw_counter = 29
        
        # Белая дамка делает 15-й "пустой" ход
        self.game.handle_click(111, 0, 0)
        res = self.game.handle_click(111, 1, 1)
        
        self.assertEqual(res, "draw")
        self.assertEqual(self.game.state.name, "FINISHED")
        self.assertEqual(self.game.finish_reason, "move_limit_draw")

if __name__ == "__main__":
    unittest.main()
