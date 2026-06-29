"""
Модуль управления игровыми сессиями для игры «Русские шашки».
"""

from __future__ import annotations
import uuid
import time
from enum import Enum
from typing import Optional
from games.checkers.board import Board
from games.checkers.ai import AI


class GameMode(Enum):
    PVP = "pvp"
    PVE = "pve"


class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class Game:
    """Одна игровая сессия в Шашки."""

    def __init__(
        self,
        game_id: str,
        player1_id: int,
        player1_name: str,
        mode: GameMode,
    ) -> None:
        self.game_id = game_id
        self.board = Board()
        self.mode = mode
        self.state = GameState.WAITING if mode == GameMode.PVP else GameState.PLAYING

        self.player1_id = player1_id
        self.player1_name = player1_name
        self.player2_id: Optional[int] = None
        self.player2_name: str = (
            "Искусственный интеллект" if mode == GameMode.PVE else ""
        )

        self.player1_chat_id: Optional[int] = None
        self.player2_chat_id: Optional[int] = None
        self.player1_message_id: Optional[int] = None
        self.player2_message_id: Optional[int] = None

        self.is_inline: bool = False
        self.inline_message_id: Optional[str] = None

        if mode == GameMode.PVE:
            self.player2_id = -1
            self.ai = AI(player=Board.BLACK, depth=3)
        else:
            self.ai = None

        self.current_turn: int = Board.WHITE
        self.selected_piece: Optional[tuple[int, int]] = None
        self.valid_moves: list[tuple[int, int]] = []

        # Мульти-взятие
        self.active_capture_piece: Optional[tuple[int, int]] = None
        self.ignored_captured: set[tuple[int, int]] = (
            set()
        )  # Побитые шашки, еще не убранные с доски

        # Статистика
        self.move_count_w: int = 0
        self.move_count_b: int = 0
        self.draw_counter: int = (
            0  # Считает ходы без взятий и без ходов простых шашек (для правила 15 ходов дамок)
        )

        # Результат
        self.winner: int = 0
        self.winner_name: str = ""
        self.finish_reason: str = ""
        self.start_time: float = time.time()
        self.show_hints: bool = True

    def get_elapsed_time_str(self) -> str:
        elapsed = int(time.time() - self.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        return f"{mins:02d}:{secs:02d} ⏱"

    def surrender(self, user_id: int) -> None:
        self.state = GameState.FINISHED
        if user_id == self.player1_id:
            self.winner = Board.BLACK
            self.winner_name = self.player2_name
        else:
            self.winner = Board.WHITE
            self.winner_name = self.player1_name
        self.finish_reason = "surrender"

    def join(self, player2_id: int, player2_name: str) -> bool:
        """Второй игрок присоединяется к PvP игре."""
        if self.mode != GameMode.PVP or self.state != GameState.WAITING:
            return False
        if player2_id == self.player1_id:
            return False

        self.player2_id = player2_id
        self.player2_name = player2_name
        self.state = GameState.PLAYING
        return True

    def get_current_player_id(self) -> int:
        """ID игрока, чей ход."""
        return (
            self.player1_id
            if self.current_turn == Board.WHITE
            else (self.player2_id or -1)
        )

    def get_current_player_name(self) -> str:
        """Имя текущего игрока."""
        return (
            self.player1_name if self.current_turn == Board.WHITE else self.player2_name
        )

    def is_players_turn(self, user_id: int) -> bool:
        """Проверить, ход ли этого игрока."""
        return self.get_current_player_id() == user_id

    def is_participant(self, user_id: int) -> bool:
        """Является ли игрок участником игры."""
        return user_id == self.player1_id or user_id == self.player2_id

    def get_player_number(self, user_id: int) -> int:
        """Получить номер игрока (WHITE или BLACK) по его ID."""
        if user_id == self.player1_id:
            return Board.WHITE
        if user_id == self.player2_id:
            return Board.BLACK
        return Board.EMPTY

    def handle_click(self, user_id: int, row: int, col: int) -> str:
        """
        Обработка нажатия на клетку (row, col) игроком user_id.
        Возвращает текстовый статус результата:
        - "selected": шашка выбрана
        - "moved": выполнен ход, переход хода
        - "moved_serial": выполнен ход, но серия прыжков продолжается
        - "win", "draw": игра окончена
        - "not_your_turn", "not_yours", "no_moves", "invalid", "empty": ошибки
        """
        if self.state != GameState.PLAYING:
            return "stop"
        if not self.is_players_turn(user_id):
            return "not_your_turn"

        if not (0 <= row < self.board.SIZE and 0 <= col < self.board.SIZE):
            return "invalid_pos"

        player = self.get_player_number(user_id)
        piece = self.board.get_piece(row, col)

        # Если идет серия прыжков конкретной шашки — нельзя выбирать другие
        if self.active_capture_piece is not None:
            if (row, col) in self.valid_moves:
                res = self._make_move(self.active_capture_piece, (row, col))
                return res
            return "invalid"

        # Обычный выбор шашки
        piece_owner = (
            Board.WHITE if piece in (Board.WHITE, Board.WHITE_KING) else Board.BLACK
        )
        if piece != Board.EMPTY and piece_owner == player:
            moves = self.board.get_valid_moves(row, col)
            if moves:
                self.selected_piece = (row, col)
                self.valid_moves = moves
                return "selected"
            return "no_moves"

        # Клик по доступному ходу для выбранной шашки
        if self.selected_piece is not None and (row, col) in self.valid_moves:
            res = self._make_move(self.selected_piece, (row, col))
            return res

        # Сброс выбора при клике на пустое поле
        if self.selected_piece is not None:
            self.selected_piece = None
            self.valid_moves = []
            return "empty"

        return "empty"

    def _make_move(self, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> str:
        """Внутренний метод выполнения хода."""
        fr, fc = from_pos
        tr, tc = to_pos
        piece_before = self.board.get_piece(fr, fc)

        # Выполняем ход
        success, captured_pos = self.board.move_piece(from_pos, to_pos)
        if not success:
            return "error"

        piece_after = self.board.get_piece(tr, tc)
        promoted = (piece_before in (Board.WHITE, Board.BLACK)) and (
            piece_after in (Board.WHITE_KING, Board.BLACK_KING)
        )

        # Обновляем счетчик ходов без взятий / простых шашек (для ничьей)
        is_simple_move = (piece_before in (Board.WHITE, Board.BLACK)) and (
            captured_pos is None
        )
        if is_simple_move or captured_pos is not None:
            self.draw_counter = 0
        else:
            self.draw_counter += 1

        res_status = "moved"

        if captured_pos is not None:
            # Запоминаем сбитую фигуру
            self.ignored_captured.add(captured_pos)

            if promoted:
                # По правилам русских шашек, если шашка превращается в дамку во время серийного взятия,
                # ход завершается.
                self._end_turn()
            else:
                # Проверяем, может ли эта шашка бить дальше
                next_caps = self.board.get_captures_for_piece(
                    tr, tc, self.ignored_captured
                )
                if next_caps:
                    # Серийное взятие продолжается
                    self.active_capture_piece = (tr, tc)
                    self.selected_piece = (tr, tc)
                    self.valid_moves = next_caps
                    res_status = "moved_serial"
                else:
                    self._end_turn()
        else:
            # Обычный ход — просто завершаем ход
            self._end_turn()

        # Проверяем условия победы
        self._check_game_over()
        if self.state == GameState.FINISHED:
            return "win" if self.winner != 0 else "draw"

        return res_status

    def _end_turn(self) -> None:
        """Завершить текущий полуход, убрать сбитые шашки, сменить ход."""
        # Убираем все сбитые шашки
        for r, c in self.ignored_captured:
            self.board.set_piece(r, c, Board.EMPTY)
        self.ignored_captured.clear()

        # Сброс активной шашки
        self.active_capture_piece = None
        self.selected_piece = None
        self.valid_moves = []

        # Смена хода
        if self.current_turn == Board.WHITE:
            self.move_count_w += 1
            self.current_turn = Board.BLACK
        else:
            self.move_count_b += 1
            self.current_turn = Board.WHITE

    def _check_game_over(self) -> None:
        """Проверить, закончилась ли игра."""
        winner = self.board.check_winner()

        if winner != 0:
            self.state = GameState.FINISHED
            self.winner = winner
            self.winner_name = (
                self.player1_name if winner == Board.WHITE else self.player2_name
            )
            self.finish_reason = "no_pieces"
            return

        # Проверяем заблокирован ли текущий игрок
        pieces = self.board.get_player_pieces(self.current_turn)
        has_moves = False
        for r, c in pieces:
            if self.board.get_valid_moves(r, c):
                has_moves = True
                break

        if not has_moves:
            self.state = GameState.FINISHED
            self.winner = (
                Board.BLACK if self.current_turn == Board.WHITE else Board.WHITE
            )
            self.winner_name = (
                self.player1_name if self.winner == Board.WHITE else self.player2_name
            )
            self.finish_reason = "blocked"
            return

        # Проверка правила 15 ходов (30 полуходов без взятий и ходов простых шашек)
        if self.draw_counter >= 30:
            self.state = GameState.FINISHED
            self.winner = 0
            self.finish_reason = "move_limit_draw"

    def make_ai_move(self) -> str:
        """Ход ИИ для режима PvE."""
        if (
            self.ai is None
            or self.state != GameState.PLAYING
            or self.current_turn != Board.BLACK
        ):
            return ""

        turns_made = 0
        first_move = None

        # Цикл для выполнения мульти-прыжков
        while (
            self.current_turn == Board.BLACK
            and self.state == GameState.PLAYING
            and turns_made < 10
        ):
            move = self.ai.get_best_move(self.board, self.active_capture_piece, self.ignored_captured)
            if move is None:
                if turns_made > 0:
                    self._end_turn()
                    break
                return "ai_stuck"

            from_pos, to_pos = move
            if first_move is None:
                first_move = (from_pos, to_pos)

            self.selected_piece = from_pos
            self.valid_moves = self.board.get_valid_moves(
                from_pos[0],
                from_pos[1],
                self.active_capture_piece,
                self.ignored_captured,
            )

            self._make_move(from_pos, to_pos)
            turns_made += 1

        if self.state == GameState.FINISHED:
            return "win" if self.winner == Board.BLACK else "draw"

        if first_move:
            fr, fc = first_move[0]
            tr, tc = first_move[1]
            return f"ai_moved_{fr}_{fc}_{tr}_{tc}"
        return "error"

    def get_status_text(self, for_user_id: Optional[int] = None) -> str:
        """Получить текстовое состояние игры."""
        if self.state == GameState.WAITING:
            return (
                "⏳ **Ожидание соперника...**\n"
                "Поделитесь ссылкой ниже, чтобы пригласить друга."
            )

        if self.state == GameState.FINISHED:
            if self.winner != 0:
                emoji = "⚪" if self.winner == Board.WHITE else "⚫"
                reason_text = ""
                if self.finish_reason == "no_pieces":
                    reason_text = "\n💀 Все фигуры соперника уничтожены!"
                elif self.finish_reason == "blocked":
                    reason_text = "\n🚫 Соперник заблокирован и не может сделать ход!"
                elif self.finish_reason == "surrender":
                    reason_text = "\n🏳️ Противник сдался!"

                return (
                    f"🏆 **Победитель:** {emoji} {self.winner_name}{reason_text}\n"
                    f"Ходов: ⚪ {self.move_count_w} | ⚫ {self.move_count_b}\n"
                    f"Нажмите /play для новой игры!"
                )
            else:
                reason_text = ""
                if self.finish_reason == "move_limit_draw":
                    reason_text = "\n⏰ 15 ходов дамок без взятий!"
                return f"🤝 **Ничья!**{reason_text}\nНажмите /play для новой игры!"

        # Игра идет
        turn_name = self.get_current_player_name()

        if for_user_id and self.mode == GameMode.PVP and not self.is_inline:
            pnum = self.get_player_number(for_user_id)
            you_emoji = "⚪" if pnum == Board.WHITE else "⚫"
            is_your_turn = self.is_players_turn(for_user_id)

        warning = ""
        if self.board.get_all_valid_captures(self.current_turn, self.ignored_captured):
            warning = "\n⚠️ **Обязательное взятие! Вы должны бить.**"

        return (
            f"{self.player1_name} ⚪ VS {self.player2_name} ⚫\n"
            f"Ходит: 👉 {turn_name}{warning}"
        )

    def set_message_info(self, user_id: int, chat_id: int, message_id: int) -> None:
        """Сохранить информацию о сообщении игрока для обновления доски."""
        if user_id == self.player1_id:
            self.player1_chat_id = chat_id
            self.player1_message_id = message_id
        elif user_id == self.player2_id:
            self.player2_chat_id = chat_id
            self.player2_message_id = message_id

    def update_message_id(self, user_id: int, message_id: int) -> None:
        """Обновить message_id для игрока."""
        if user_id == self.player1_id:
            self.player1_message_id = message_id
        elif user_id == self.player2_id:
            self.player2_message_id = message_id


class GameManager:
    """Управление игровыми сессиями в Шашки."""

    def __init__(self) -> None:
        self.games: dict[str, Game] = {}
        self.user_games: dict[int, str] = {}
        self.chat_games: dict[int, str] = {}

    def create_game(
        self,
        player1_id: int,
        player1_name: str,
        mode: GameMode,
        chat_id: Optional[int] = None,
    ) -> Game:
        game_id = uuid.uuid4().hex[:8]
        game = Game(game_id, player1_id, player1_name, mode)
        self.games[game_id] = game
        self.user_games[player1_id] = game_id
        if chat_id:
            self.chat_games[chat_id] = game_id
        return game

    def get_game_by_id(self, game_id: str) -> Optional[Game]:
        return self.games.get(game_id)

    def get_game_by_user(self, user_id: int) -> Optional[Game]:
        game_id = self.user_games.get(user_id)
        if game_id:
            return self.games.get(game_id)
        return None

    def get_game_by_chat(self, chat_id: int) -> Optional[Game]:
        game_id = self.chat_games.get(chat_id)
        if game_id:
            return self.games.get(game_id)
        return None

    def get_inline_game(self, inline_message_id: str) -> Optional[Game]:
        if inline_message_id in self.games:
            return self.games[inline_message_id]

        game = Game(inline_message_id, 0, "", GameMode.PVP)
        game.is_inline = True
        game.inline_message_id = inline_message_id
        game.show_hints = False
        self.games[inline_message_id] = game
        return game

    def join_game(
        self, game_id: str, player2_id: int, player2_name: str
    ) -> Optional[Game]:
        game = self.games.get(game_id)
        if game is None or not game.join(player2_id, player2_name):
            return None
        self.user_games[player2_id] = game_id
        return game

    def remove_game(self, game_id: str) -> None:
        game = self.games.pop(game_id, None)
        if game:
            self.user_games.pop(game.player1_id, None)
            if game.player2_id:
                self.user_games.pop(game.player2_id, None)

    def has_active_game(self, user_id: int) -> bool:
        game = self.get_game_by_user(user_id)
        return game is not None and game.state != GameState.FINISHED
