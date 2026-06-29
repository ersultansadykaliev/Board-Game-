"""
Юнит-тесты для игры «Шахматы».
"""
import unittest

from games.chess.board import (
    Board, WHITE, BLACK, EMPTY,
    W_PAWN, W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING,
    B_PAWN, B_ROOK, B_KNIGHT, B_BISHOP, B_QUEEN, B_KING
)
from games.chess.game import Game, ChessMode

class TestChess(unittest.TestCase):
    def setUp(self):
        self.game = Game("test_chess", 111, "Player1", ChessMode.PVP)
        self.game.join(222, "Player2")
        self.board = self.game.board

    def test_initial_board_setup(self):
        self.assertEqual(self.board.get_piece(0, 0), B_ROOK)
        self.assertEqual(self.board.get_piece(7, 4), W_KING)
        self.assertEqual(self.board.get_piece(1, 4), B_PAWN)
        self.assertEqual(self.board.get_piece(6, 4), W_PAWN)

    def test_pawn_movement(self):
        self.game.board.grid = [[EMPTY] * 8 for _ in range(8)]
        self.game.board.grid[6][4] = W_PAWN
        
        # Белая пешка со стартовой позиции может пойти на 1 и на 2 клетки
        moves = self.game.board.get_legal_moves_from(6, 4)
        self.assertIn((5, 4), moves)
        self.assertIn((4, 4), moves)
        self.assertEqual(len(moves), 2)
        
        # Чёрная пешка перед ней блокирует движение на 2 клетки
        self.game.board.grid[4][4] = B_KNIGHT
        moves = self.game.board.get_legal_moves_from(6, 4)
        self.assertEqual(moves, [(5, 4)])

    def test_knight_movement(self):
        self.game.board.grid = [[EMPTY] * 8 for _ in range(8)]
        self.game.board.grid[4][4] = W_KNIGHT
        moves = self.game.board.get_legal_moves_from(4, 4)
        expected_moves = [
            (2, 3), (2, 5), (6, 3), (6, 5),
            (3, 2), (5, 2), (3, 6), (5, 6)
        ]
        for m in expected_moves:
            self.assertIn(m, moves)
        self.assertEqual(len(moves), 8)

    def test_check_and_mate(self):
        # Детский мат
        # 1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7#
        self.game.handle_click(111, 6, 4) # W_PAWN e2
        self.game.handle_click(111, 4, 4) # to e4
        
        self.game.handle_click(222, 1, 4) # B_PAWN e7
        self.game.handle_click(222, 3, 4) # to e5
        
        self.game.handle_click(111, 7, 5) # W_BISHOP f1
        self.game.handle_click(111, 4, 2) # to c4
        
        self.game.handle_click(222, 0, 1) # B_KNIGHT b8
        self.game.handle_click(222, 2, 2) # to c6
        
        self.game.handle_click(111, 7, 3) # W_QUEEN d1
        self.game.handle_click(111, 3, 7) # to h5
        
        self.game.handle_click(222, 0, 6) # B_KNIGHT g8
        self.game.handle_click(222, 2, 5) # to f6
        
        res = self.game.handle_click(111, 3, 7) # W_QUEEN h5
        self.assertEqual(res, "selected")
        res2 = self.game.handle_click(111, 1, 5) # to f7 (mate)
        self.assertEqual(res2, "checkmate")
        
        self.assertEqual(self.game.state.name, "FINISHED")
        self.assertEqual(self.game.winner, WHITE)
        self.assertEqual(self.game.finish_reason, "checkmate")

if __name__ == '__main__':
    unittest.main()
