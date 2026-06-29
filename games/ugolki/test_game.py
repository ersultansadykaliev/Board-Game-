import unittest
from games.ugolki.board import Board
from games.ugolki.game import Game, GameMode, GameState
from config import MAX_MOVES_PER_PLAYER, BOARD_SIZE, HOME_CLEAR_LIMIT


class TestUgolki(unittest.TestCase):
    def setUp(self):
        self.board = Board()
        self.game = Game("test_id", 111, "Player1", GameMode.PVP)
        self.game.join(222, "Player2")

    def test_initial_state(self):
        self.assertEqual(self.game.state, GameState.PLAYING)
        self.assertEqual(self.game.current_turn, Board.PLAYER1)
        self.assertEqual(len(self.board.get_player_pieces(Board.PLAYER1)), 12)
        self.assertEqual(len(self.board.get_player_pieces(Board.PLAYER2)), 12)

    def test_out_of_bounds_move(self):
        # Piece at (0,0) cannot move left or up
        moves = self.board.get_valid_moves(0, 0)
        for r, c in moves:
            self.assertTrue(0 <= r < BOARD_SIZE)
            self.assertTrue(0 <= c < BOARD_SIZE)

    def test_infinite_jump_loop(self):
        # Create a loop of jumps to ensure get_jump_moves doesn't recurse infinitely
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.board.grid[0][0] = Board.PLAYER1
        self.board.grid[0][1] = Board.PLAYER2
        self.board.grid[1][2] = Board.PLAYER2
        self.board.grid[2][1] = Board.PLAYER2
        self.board.grid[1][0] = Board.PLAYER2
        # This setup allows a piece at (0,0) to jump in a circle: (0,0) -> (0,2) -> (2,2) -> (2,0) -> (0,0)
        # Because we use 'visited' set, it should not loop infinitely.
        moves = self.board.get_jump_moves(0, 0)
        self.assertIn((0, 2), moves)
        self.assertIn((2, 2), moves)
        self.assertIn((2, 0), moves)

    def test_orthogonal_only(self):
        # Ensure diagonal moves are not allowed
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.board.grid[1][1] = Board.PLAYER1
        moves = self.board.get_valid_moves(1, 1)
        # Should only be (0,1), (2,1), (1,0), (1,2)
        expected_moves = {(0, 1), (2, 1), (1, 0), (1, 2)}
        self.assertEqual(set(moves), expected_moves)

    def test_wrong_player_turn(self):
        # It's P1's turn. P2 tries to click.
        res = self.game.handle_click(222, 7, 7)
        self.assertEqual(res, "not_your_turn")

    def test_select_opponent_piece(self):
        # P1 tries to select P2's piece at (7,7)
        res = self.game.handle_click(111, 7, 7)
        self.assertEqual(res, "not_yours")

    def test_select_empty(self):
        # P1 tries to select empty cell at (3,3)
        res = self.game.handle_click(111, 3, 3)
        self.assertEqual(res, "empty")

    def test_max_moves_tiebreak_win(self):
        """На 80-м ходу побеждает тот, у кого больше фишек в доме соперника."""
        # Set up: P1 has more pieces in goal than P2
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        # P1 has 3 pieces in P2's home (home1)
        home1_list = list(self.game.board.home1)
        for i in range(3):
            r, c = home1_list[i]
            self.game.board.grid[r][c] = Board.PLAYER1
        # Remaining P1 pieces elsewhere
        self.game.board.grid[3][0] = Board.PLAYER1

        # P2 has 1 piece in P1's home (home2)
        home2_list = list(self.game.board.home2)
        r, c = home2_list[0]
        self.game.board.grid[r][c] = Board.PLAYER2
        # Remaining P2 pieces elsewhere
        self.game.board.grid[4][0] = Board.PLAYER2

        # Set move counts to just under limit
        self.game.move_count_p1 = MAX_MOVES_PER_PLAYER
        self.game.move_count_p2 = MAX_MOVES_PER_PLAYER - 1

        # It's P2's turn; make one more move to reach 80 total
        self.game.current_turn = Board.PLAYER2
        self.game.handle_click(222, 4, 0)  # Select P2 piece
        res = self.game.handle_click(222, 4, 1)  # Move it

        self.assertEqual(res, "win")
        self.assertEqual(self.game.winner, Board.PLAYER1)  # P1 has more in goal
        self.assertEqual(self.game.state, GameState.FINISHED)

    def test_max_moves_tiebreak_draw(self):
        """На 80-м ходу при равном числе фишек — ничья."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        # Equal pieces in goals
        home1_list = list(self.game.board.home1)
        home2_list = list(self.game.board.home2)
        for i in range(2):
            r, c = home1_list[i]
            self.game.board.grid[r][c] = Board.PLAYER1
            r, c = home2_list[i]
            self.game.board.grid[r][c] = Board.PLAYER2

        # Remaining pieces elsewhere
        self.game.board.grid[3][0] = Board.PLAYER1
        self.game.board.grid[4][0] = Board.PLAYER2

        self.game.move_count_p1 = MAX_MOVES_PER_PLAYER
        self.game.move_count_p2 = MAX_MOVES_PER_PLAYER - 1
        self.game.current_turn = Board.PLAYER2

        self.game.handle_click(222, 4, 0)
        res = self.game.handle_click(222, 4, 1)

        self.assertEqual(res, "draw")
        self.assertEqual(self.game.state, GameState.FINISHED)

    def test_win_condition(self):
        # Manually move all P1 pieces to P1 goal (home1)
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for r, c in self.board.home1:
            self.board.grid[r][c] = Board.PLAYER1

        # Manually move all P1 pieces to P1 goal (home1)
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        for r, c in self.game.board.home1:
            self.game.board.grid[r][c] = Board.PLAYER1

        # Move one piece outside the goal. (5,4) is the corner of home1.
        # (5,3) is outside.
        self.game.board.grid[5][4] = Board.EMPTY
        self.game.board.grid[5][3] = Board.PLAYER1

        # Also need P2 pieces somewhere so game is valid
        self.game.board.grid[3][0] = Board.PLAYER2

        # Ensure it is Player 1's turn and nothing is selected
        self.game.current_turn = Board.PLAYER1
        self.game.selected_piece = None

        # Player 1 selects the piece at (5,3)
        self.game.handle_click(111, 5, 3)
        # Player 1 moves it to (5,4), which completes the goal
        res = self.game.handle_click(111, 5, 4)

        # P1 won but P2 gets a response move
        self.assertEqual(res, "p1_won_pending")
        self.assertTrue(self.game.p1_won_pending)
        self.assertEqual(self.game.current_turn, Board.PLAYER2)

    def test_piece_locking_prohibited(self):
        """Нельзя запирать фишку соперника со всех 4 сторон."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # P2 piece in corner at (0,0) — only 2 neighbors (right and down)
        self.game.board.grid[0][0] = Board.PLAYER2

        # P1 pieces: one blocks right, need to block down
        self.game.board.grid[0][1] = Board.PLAYER1  # right of (0,0)
        self.game.board.grid[0][2] = Board.PLAYER1  # blocks jump right to (0,2)
        # P1 piece about to block downward
        self.game.board.grid[2][0] = Board.PLAYER1  # blocks jump down to (2,0)
        self.game.board.grid[3][0] = Board.PLAYER1  # will move to (1,0) to lock

        self.game.current_turn = Board.PLAYER1
        self.game.selected_piece = None

        # Select the piece at (3,0)
        self.game.handle_click(111, 3, 0)
        # Try to move to (1,0) which would lock P2's piece at (0,0)
        res = self.game.handle_click(111, 1, 0)

        self.assertEqual(res, "locks_opponent")

    def test_piece_locking_allowed_if_can_jump(self):
        """Запирание не считается, если фишка может прыгнуть."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # P2 piece at (4,4)
        self.game.board.grid[4][4] = Board.PLAYER2

        # P1 pieces surrounding 3 sides
        self.game.board.grid[3][4] = Board.PLAYER1
        self.game.board.grid[5][4] = Board.PLAYER1
        self.game.board.grid[4][5] = Board.PLAYER1
        # (4,6) is empty so P2 can jump right

        self.game.board.grid[4][2] = Board.PLAYER1

        self.game.current_turn = Board.PLAYER1
        self.game.selected_piece = None

        self.game.handle_click(111, 4, 2)
        res = self.game.handle_click(111, 4, 3)

        # This should be allowed because P2 can jump (4,4) -> (4,6) via (4,5)
        self.assertEqual(res, "moved")

    def test_home_return_banned_after_limit(self):
        """После 40 ходов нельзя возвращать фишки в свой дом."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # P1 piece just outside home at (3,0)
        self.game.board.grid[3][0] = Board.PLAYER1
        # Home position (2,0) is empty — should be banned after 40 moves

        # Need a P2 piece so game is valid
        self.game.board.grid[7][7] = Board.PLAYER2

        self.game.move_count_p1 = HOME_CLEAR_LIMIT  # Already at 40 moves
        self.game.current_turn = Board.PLAYER1

        # Select piece at (3,0)
        res = self.game.handle_click(111, 3, 0)
        self.assertEqual(res, "selected")

        # (2,0) is in P1's home — should not be in valid moves
        self.assertNotIn((2, 0), self.game.valid_moves)

    def test_simultaneous_finish_draw(self):
        """Если P2 завершает сразу после P1 — ничья."""
        # Set up both players very close to finishing
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # P1 fills home1 except one spot
        for r, c in self.game.board.home1:
            self.game.board.grid[r][c] = Board.PLAYER1
        # Move one P1 piece out — use (5,4) which is in home1
        self.game.board.grid[5][4] = Board.EMPTY
        self.game.board.grid[4][4] = Board.PLAYER1  # just outside home1

        # P2 fills home2 except one spot
        for r, c in self.game.board.home2:
            self.game.board.grid[r][c] = Board.PLAYER2
        # Move one P2 piece out — use (2,3) which is in home2
        self.game.board.grid[2][3] = Board.EMPTY
        self.game.board.grid[3][3] = Board.PLAYER2  # just outside home2

        # P1's turn — complete the goal
        self.game.current_turn = Board.PLAYER1
        self.game.handle_click(111, 4, 4)
        res = self.game.handle_click(111, 5, 4)
        self.assertEqual(res, "p1_won_pending")
        self.assertEqual(self.game.current_turn, Board.PLAYER2)

        # P2's turn — also complete the goal
        self.game.handle_click(222, 3, 3)
        res = self.game.handle_click(222, 2, 3)
        self.assertEqual(res, "draw")
        self.assertEqual(self.game.state, GameState.FINISHED)

    def test_threefold_repetition(self):
        """Трёхкратное повторение позиции — ничья."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.game.board.grid[3][3] = Board.PLAYER1
        self.game.board.grid[4][4] = Board.PLAYER2

        # Move P1 back and forth: (3,3) <-> (3,4), P2: (4,4) <-> (4,3)
        # Each full cycle returns to same position
        for _ in range(2):
            self.game.current_turn = Board.PLAYER1
            self.game.handle_click(111, 3, 3)
            self.game.handle_click(111, 3, 4)

            self.game.handle_click(222, 4, 4)
            self.game.handle_click(222, 4, 3)

            # Move back
            self.game.handle_click(111, 3, 4)
            self.game.handle_click(111, 3, 3)

            self.game.handle_click(222, 4, 3)
            self.game.handle_click(222, 4, 4)

        # Third repetition should trigger draw
        self.game.handle_click(111, 3, 3)
        self.game.handle_click(111, 3, 4)

        self.game.handle_click(222, 4, 4)
        self.game.handle_click(222, 4, 3)

        # At this point the position should have repeated 3 times
        # The exact move that triggers it depends on when the hash matches
        self.assertEqual(self.game.state, GameState.FINISHED)
        self.assertEqual(self.game.finish_reason, "threefold_repetition")

    def test_is_piece_locked(self):
        """Проверка метода is_piece_locked_by."""
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # Piece at (4,4) surrounded by P1 AND all jump destinations also blocked by P1
        self.board.grid[4][4] = Board.PLAYER2
        self.board.grid[3][4] = Board.PLAYER1  # above
        self.board.grid[5][4] = Board.PLAYER1  # below
        self.board.grid[4][3] = Board.PLAYER1  # left
        self.board.grid[4][5] = Board.PLAYER1  # right
        # Block all jump destinations too
        self.board.grid[2][4] = Board.PLAYER1  # blocks jump up
        self.board.grid[6][4] = Board.PLAYER1  # blocks jump down
        self.board.grid[4][2] = Board.PLAYER1  # blocks jump left
        self.board.grid[4][6] = Board.PLAYER1  # blocks jump right

        self.assertTrue(self.board.is_piece_locked_by(4, 4, Board.PLAYER1))

    def test_is_piece_not_locked_can_jump(self):
        """Фишка не заблокирована если может прыгнуть."""
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        self.board.grid[4][4] = Board.PLAYER2
        self.board.grid[3][4] = Board.PLAYER1
        self.board.grid[5][4] = Board.PLAYER1
        self.board.grid[4][3] = Board.PLAYER1
        self.board.grid[4][5] = Board.PLAYER1
        # But (4,6) is empty — can jump via (4,5)

        self.assertFalse(self.board.is_piece_locked_by(4, 4, Board.PLAYER1))

    def test_is_piece_locked_corner(self):
        """Фишка в углу не заблокирована если можно прыгнуть."""
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        self.board.grid[0][0] = Board.PLAYER2
        self.board.grid[0][1] = Board.PLAYER1
        self.board.grid[1][0] = Board.PLAYER1
        # Can jump to (0,2) via (0,1) if empty
        # Can jump to (2,0) via (1,0) if empty

        self.assertFalse(self.board.is_piece_locked_by(0, 0, Board.PLAYER1))

    def test_is_piece_locked_corner_fully(self):
        """Фишка в углу заблокирована если прыжки тоже заблокированы."""
        self.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        self.board.grid[0][0] = Board.PLAYER2
        self.board.grid[0][1] = Board.PLAYER1
        self.board.grid[1][0] = Board.PLAYER1
        self.board.grid[0][2] = Board.PLAYER1  # blocks jump right
        self.board.grid[2][0] = Board.PLAYER1  # blocks jump down

        self.assertTrue(self.board.is_piece_locked_by(0, 0, Board.PLAYER1))

    def test_position_hash(self):
        """Хэш позиции должен быть одинаковым для одинаковых позиций."""
        board2 = self.board.clone()
        self.assertEqual(self.board.position_hash(), board2.position_hash())

        board2.grid[3][3] = Board.PLAYER1
        self.assertNotEqual(self.board.position_hash(), board2.position_hash())

    def test_has_pieces_in_home(self):
        """Проверка наличия фишек в собственном доме."""
        # At start, both players have pieces in their homes
        self.assertTrue(self.board.has_pieces_in_home(Board.PLAYER1))
        self.assertTrue(self.board.has_pieces_in_home(Board.PLAYER2))

        # Clear P1 home
        from config import PLAYER1_START

        for r, c in PLAYER1_START:
            self.board.grid[r][c] = Board.EMPTY
        self.assertFalse(self.board.has_pieces_in_home(Board.PLAYER1))

    def test_mirror_strategy_detection(self):
        """Зеркальная стратегия: Game._mirror_of и _is_mirror_move."""
        self.assertEqual(Game._mirror_of((0, 0)), (7, 7))
        self.assertEqual(Game._mirror_of((2, 3)), (5, 4))

        game = Game("mirror_test", 111, "P1", GameMode.PVP)
        game.join(222, "P2")
        self.assertTrue(game._is_mirror_move((7, 7), (7, 6), (0, 0), (0, 1)))
        self.assertFalse(game._is_mirror_move((7, 7), (6, 7), (0, 0), (0, 1)))

    def test_home_clear_loss(self):
        """Игрок проигрывает если не вывел фишки из дома к 40-му ходу."""
        self.game.board.grid = [[Board.EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]

        # P1 still has a piece in its own home at (0,0)
        self.game.board.grid[0][0] = Board.PLAYER1
        # P1 has another piece outside
        self.game.board.grid[4][0] = Board.PLAYER1
        # P2 piece
        self.game.board.grid[7][7] = Board.PLAYER2

        # P1 is at move 39, about to reach 40
        self.game.move_count_p1 = HOME_CLEAR_LIMIT - 1
        self.game.current_turn = Board.PLAYER1

        # P1 moves the piece at (4,0) to (4,1) — reaching 40 moves
        # P1 still has a piece at (0,0) in home
        self.game.handle_click(111, 4, 0)
        res = self.game.handle_click(111, 4, 1)

        self.assertEqual(res, "home_clear_loss")
        self.assertEqual(self.game.winner, Board.PLAYER2)
        self.assertEqual(self.game.state, GameState.FINISHED)


if __name__ == "__main__":
    unittest.main()
