"""
Модуль управления игровыми сессиями для игры «Шахматы».
"""

from __future__ import annotations
import uuid
import time
from enum import Enum
from typing import Optional

from games.chess.board import (
    Board, WHITE, BLACK, EMPTY,
    piece_color, piece_type, PIECE_EMOJI,
)
from games.chess.ai import AI


class ChessMode(Enum):
    PVP = "pvp"
    PVE = "pve"


class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class Game:
    """Одна игровая сессия в Шахматы."""

    def __init__(
        self,
        game_id: str,
        player1_id: int,
        player1_name: str,
        mode: ChessMode,
    ) -> None:
        self.game_id = game_id
        self.board = Board()
        self.mode = mode
        self.state = (
            GameState.WAITING if mode == ChessMode.PVP else GameState.PLAYING
        )

        self.player1_id = player1_id
        self.player1_name = player1_name
        self.player2_id: Optional[int] = None
        self.player2_name: str = (
            "🤖 Бот" if mode == ChessMode.PVE else ""
        )

        self.player1_chat_id: Optional[int] = None
        self.player2_chat_id: Optional[int] = None
        self.player1_message_id: Optional[int] = None
        self.player2_message_id: Optional[int] = None

        self.is_inline: bool = False
        self.inline_message_id: Optional[str] = None

        if mode == ChessMode.PVE:
            self.player2_id = -1
            self.ai = AI(color=BLACK, depth=3)
        else:
            self.ai = None

        # Белые ходят первыми
        self.current_turn: int = WHITE
        self.selected_piece: Optional[tuple[int, int]] = None
        self.valid_moves: list[tuple[int, int]] = []

        # Статистика
        self.move_count_w: int = 0
        self.move_count_b: int = 0
        self.start_time: float = time.time()

        # Результат
        self.winner: int = 0
        self.winner_name: str = ""
        self.finish_reason: str = ""
        self.show_hints: bool = True

    # ─── Игроки ─────────────────────────────────────────────
    def get_player_number(self, user_id: int) -> int:
        """Получить цвет игрока (WHITE/BLACK)."""
        if user_id == self.player1_id:
            return WHITE
        return BLACK

    def is_players_turn(self, user_id: int) -> bool:
        return self.get_player_number(user_id) == self.current_turn

    def is_participant(self, user_id: int) -> bool:
        return user_id in (self.player1_id, self.player2_id)

    def get_current_player_name(self) -> str:
        if self.current_turn == WHITE:
            return self.player1_name
        return self.player2_name

    # ─── Присоединение ──────────────────────────────────────
    def join(
        self, player2_id: int, player2_name: str,
        chat_id: Optional[int] = None,
    ) -> bool:
        if self.state != GameState.WAITING:
            return False
        if player2_id == self.player1_id:
            return False
        self.player2_id = player2_id
        self.player2_name = player2_name
        self.player2_chat_id = chat_id
        self.state = GameState.PLAYING
        self.start_time = time.time()
        return True

    # ─── Таймер ─────────────────────────────────────────────
    def get_elapsed_time_str(self) -> str:
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes:02d}:{seconds:02d} ⏱"

    # ─── Сдача ──────────────────────────────────────────────
    def surrender(self, user_id: int) -> None:
        if self.state != GameState.PLAYING:
            return
        self.state = GameState.FINISHED
        self.finish_reason = "surrender"
        if user_id == self.player1_id:
            self.winner = BLACK
            self.winner_name = self.player2_name
        else:
            self.winner = WHITE
            self.winner_name = self.player1_name

    # ─── Обработка клика ────────────────────────────────────
    def handle_click(self, user_id: int, row: int, col: int) -> str:
        """
        Обработать клик по клетке (row, col).
        Возвращает строку-результат.
        """
        if self.state != GameState.PLAYING:
            return "stop"

        player_color = self.get_player_number(user_id)
        if player_color != self.current_turn:
            return "not_your_turn"

        if not (0 <= row < self.board.SIZE and 0 <= col < self.board.SIZE):
            return "invalid_pos"

        piece = self.board.get_piece(row, col)

        # Если уже выбрана фигура
        if self.selected_piece is not None:
            # Кликнули на ту же фигуру — снять выделение
            if (row, col) == self.selected_piece:
                self.selected_piece = None
                self.valid_moves = []
                return "deselected"

            # Кликнули на свою другую фигуру — переключить
            if piece_color(piece) == player_color:
                self.selected_piece = (row, col)
                self.valid_moves = self.board.get_legal_moves_from(row, col)
                return "selected" if self.valid_moves else "no_moves"

            # Кликнули на допустимый ход — выполнить
            if (row, col) in self.valid_moves:
                from_pos = self.selected_piece
                result = self.board.make_move(from_pos, (row, col))

                # Обновляем счётчик ходов
                if self.current_turn == WHITE:
                    self.move_count_w += 1
                else:
                    self.move_count_b += 1

                self.selected_piece = None
                self.valid_moves = []

                # Проверяем конец игры
                if "checkmate" in result:
                    self._finish_game(player_color, "checkmate")
                    return "checkmate"
                elif result == "stalemate":
                    self._finish_draw("stalemate")
                    return "stalemate"

                # Проверяем ничью
                if self.board.is_fifty_move_draw():
                    self._finish_draw("fifty_moves")
                    return "fifty_moves_draw"

                if self.board.is_threefold_repetition():
                    self._finish_draw("threefold_repetition")
                    return "threefold_draw"

                if self.board.is_insufficient_material():
                    self._finish_draw("insufficient_material")
                    return "insufficient_material"

                # Переход хода
                self.current_turn = (
                    BLACK if self.current_turn == WHITE else WHITE
                )
                return result

            return "invalid"

        # Ничего не выбрано — выбираем фигуру
        if piece == EMPTY:
            return "empty"

        if piece_color(piece) != player_color:
            return "not_yours"

        moves = self.board.get_legal_moves_from(row, col)
        if not moves:
            return "no_moves"

        self.selected_piece = (row, col)
        self.valid_moves = moves
        return "selected"

    def _finish_game(self, winner_color: int, reason: str) -> None:
        """Завершить игру с победителем."""
        self.state = GameState.FINISHED
        self.winner = winner_color
        self.finish_reason = reason
        if winner_color == WHITE:
            self.winner_name = self.player1_name
        else:
            self.winner_name = self.player2_name

    def _finish_draw(self, reason: str) -> None:
        """Завершить игру вничью."""
        self.state = GameState.FINISHED
        self.winner = 0
        self.finish_reason = reason

    # ─── Ход ИИ ─────────────────────────────────────────────
    def make_ai_move(self) -> str:
        """Выполнить ход ИИ."""
        if self.ai is None or self.state != GameState.PLAYING:
            return "no_ai"

        move = self.ai.get_best_move(self.board)
        if move is None:
            return "no_moves"

        from_pos, to_pos = move
        result = self.board.make_move(from_pos, to_pos)
        self.move_count_b += 1

        # Проверяем конец игры
        if "checkmate" in result:
            self._finish_game(BLACK, "checkmate")
            return "ai_checkmate"
        elif result == "stalemate":
            self._finish_draw("stalemate")
            return "ai_stalemate"

        if self.board.is_fifty_move_draw():
            self._finish_draw("fifty_moves")
            return "ai_fifty_draw"

        if self.board.is_threefold_repetition():
            self._finish_draw("threefold_repetition")
            return "ai_threefold_draw"

        if self.board.is_insufficient_material():
            self._finish_draw("insufficient_material")
            return "ai_insufficient"

        # Переход хода
        self.current_turn = WHITE
        return f"ai_moved"

    # ─── Текст статуса ──────────────────────────────────────
    def get_status_text(self, for_user_id: Optional[int] = None) -> str:
        """Текст статуса для сообщения над доской."""
        if self.state == GameState.WAITING:
            return "⏳ Ожидание второго игрока...\nОтправьте ссылку другу!"

        if self.state == GameState.FINISHED:
            if self.winner:
                emoji = "♔" if self.winner == WHITE else "♚"
                reason_text = ""
                if self.finish_reason == "checkmate":
                    reason_text = "\n♛ Мат!"
                elif self.finish_reason == "surrender":
                    reason_text = "\n🏳 Соперник сдался!"
                return (
                    f"🏆 Победитель: {emoji} {self.winner_name}!"
                    f"{reason_text}\n"
                    f"Ходов: ♔ {self.move_count_w} | "
                    f"♚ {self.move_count_b}"
                )
            else:
                reason_map = {
                    "stalemate": "Пат!",
                    "fifty_moves": "Правило 50 ходов!",
                    "threefold_repetition": "Троекратное повторение!",
                    "insufficient_material": "Недостаточно фигур!",
                    "agreed": "По соглашению!",
                }
                reason = reason_map.get(
                    self.finish_reason, "Ничья!"
                )
                return f"🤝 Ничья! {reason}"

        # Игра идёт
        turn_emoji = "♔" if self.current_turn == WHITE else "♚"
        turn_name = self.get_current_player_name()

        check_text = ""
        if self.board.is_in_check(self.current_turn):
            check_text = " ⚠️ ШАХ!"

        return (
            f"♛ Шахматы | {self.player1_name} ♔ vs "
            f"{self.player2_name} ♚\n"
            f"Ход: {turn_emoji} {turn_name}{check_text}\n"
            f"♔ {self.move_count_w} | "
            f"♚ {self.move_count_b}"
        )

    # ─── Сообщение ──────────────────────────────────────────
    def set_message_info(
        self, user_id: int, chat_id: int, message_id: int
    ) -> None:
        if user_id == self.player1_id:
            self.player1_chat_id = chat_id
            self.player1_message_id = message_id
        elif user_id == self.player2_id:
            self.player2_chat_id = chat_id
            self.player2_message_id = message_id

    def update_message_id(self, user_id: int, message_id: int) -> None:
        if user_id == self.player1_id:
            self.player1_message_id = message_id
        elif user_id == self.player2_id:
            self.player2_message_id = message_id


class GameManager:
    """Управление шахматными сессиями."""

    def __init__(self) -> None:
        self.games: dict[str, Game] = {}
        self.user_games: dict[int, str] = {}
        self.chat_games: dict[int, str] = {}

    def create_game(
        self,
        player1_id: int,
        player1_name: str,
        mode: ChessMode,
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
            game = self.games.get(game_id)
            if game and game.state != GameState.FINISHED:
                return game
            # Очищаем завершённую игру
            if game_id in self.user_games:
                del self.user_games[user_id]
        return None

    def get_inline_game(self, inline_message_id: str) -> Optional[Game]:
        """Получить или создать inline-игру по inline_message_id."""
        if inline_message_id in self.games:
            return self.games[inline_message_id]

        game = Game(inline_message_id, 0, "", ChessMode.PVP)
        game.is_inline = True
        game.inline_message_id = inline_message_id
        game.show_hints = False
        self.games[inline_message_id] = game
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

    def join_game(
        self, game_id: str, player2_id: int, player2_name: str,
        chat_id: Optional[int] = None,
    ) -> Optional[Game]:
        game = self.get_game_by_id(game_id)
        if game and game.join(player2_id, player2_name, chat_id):
            self.user_games[player2_id] = game_id
            return game
        return None
