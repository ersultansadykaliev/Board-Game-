"""
Модуль управления игровыми сессиями «Уголки».
Поддерживает PvP через личные чаты (deep link) и PvE.
"""

from __future__ import annotations
import uuid
import time
from collections import Counter
from enum import Enum
from typing import Optional

from games.ugolki.board import Board
from games.ugolki.ai import AI
from config import (
    MAX_MOVES_PER_PLAYER,
    EMOJI_PLAYER1,
    EMOJI_PLAYER2,
    HOME_CLEAR_LIMIT,
    MIRROR_MAX_COPIES,
    MIRROR_CHECK_MOVES,
    PLAYER1_START_SET,
    PLAYER2_START_SET,
)


class GameMode(Enum):
    """Режим игры."""

    PVP = "pvp"  # Два игрока
    PVE = "pve"  # Против ИИ


class GameState(Enum):
    """Состояние игры."""

    WAITING = "waiting"  # Ждём второго игрока (PvP)
    PLAYING = "playing"  # Игра идёт
    FINISHED = "finished"  # Игра завершена


class Game:
    """Одна игровая сессия."""

    def __init__(
        self, game_id: str, player1_id: int, player1_name: str, mode: GameMode, variant: str = "classic"
    ) -> None:
        """Инициализация новой игры."""
        self.game_id = game_id
        self.board = Board(variant=variant)
        self.mode = mode
        self.variant = variant
        self.state = GameState.WAITING if mode == GameMode.PVP else GameState.PLAYING

        # Игроки
        self.player1_id = player1_id
        self.player1_name = player1_name
        self.player2_id: Optional[int] = None
        self.player2_name: str = "🤖 Бот" if mode == GameMode.PVE else ""

        # Chat IDs для каждого игрока (для обновления досок)
        self.player1_chat_id: Optional[int] = None
        self.player2_chat_id: Optional[int] = None

        # Message IDs для каждого игрока (для edit_message)
        self.player1_message_id: Optional[int] = None
        self.player2_message_id: Optional[int] = None

        # Для Inline режима (общая доска в чате)
        self.is_inline: bool = False
        self.inline_message_id: Optional[str] = None

        # Если PvE — бот = игрок 2
        if mode == GameMode.PVE:
            self.player2_id = -1
            self.ai = AI(player=Board.PLAYER2, depth=2)
            self.state = GameState.PLAYING
        else:
            self.ai: Optional[AI] = None

        # Состояние хода
        self.current_turn: int = Board.PLAYER1
        self.move_count_p1: int = 0
        self.move_count_p2: int = 0
        self.selected_piece: Optional[tuple[int, int]] = None
        self.valid_moves: list[tuple[int, int]] = []

        # История ходов (для зеркальной стратегии)
        self.move_history_p1: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.move_history_p2: list[tuple[tuple[int, int], tuple[int, int]]] = []

        # История позиций (для трёхкратного повторения)
        self.position_history: Counter[str] = Counter()

        # Флаг: P1 только что выиграл, P2 получает ответный ход
        self.p1_won_pending: bool = False

        # Результат
        self.winner: int = 0
        self.winner_name: str = ""
        self.finish_reason: str = ""
        self.start_time: float = time.time()
        self.max_moves: int = MAX_MOVES_PER_PLAYER
        self.show_hints: bool = True

    def extend_game(self, extra: int) -> None:
        """Продлить игру на extra ходов или сделать бесконечной (extra=0)."""
        self.state = GameState.PLAYING
        self.finish_reason = ""
        self.winner = 0
        self.winner_name = ""
        if extra == 0:
            self.max_moves = 0
        else:
            self.max_moves += extra

    def get_elapsed_time_str(self) -> str:
        elapsed = int(time.time() - self.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        return f"{mins:02d}:{secs:02d} ⏱"

    def surrender(self, user_id: int) -> None:
        self.state = GameState.FINISHED
        if user_id == self.player1_id:
            self.winner = Board.PLAYER2
            self.winner_name = self.player2_name
        else:
            self.winner = Board.PLAYER1
            self.winner_name = self.player1_name
        self.finish_reason = "surrender"

    # ─── Управление игроками ────────────────────────────────────

    def join(self, player2_id: int, player2_name: str) -> bool:
        """Второй игрок присоединяется к игре (PvP)."""
        if self.mode != GameMode.PVP:
            return False
        if self.state != GameState.WAITING:
            return False
        if player2_id == self.player1_id:
            return False

        self.player2_id = player2_id
        self.player2_name = player2_name
        self.state = GameState.PLAYING
        return True

    def get_current_player_id(self) -> int:
        """ID игрока, чей сейчас ход."""
        if self.current_turn == Board.PLAYER1:
            return self.player1_id
        return self.player2_id or -1

    def get_current_player_name(self) -> str:
        """Имя текущего игрока."""
        if self.current_turn == Board.PLAYER1:
            return self.player1_name
        return self.player2_name

    def is_players_turn(self, user_id: int) -> bool:
        """Проверить, ходит ли этот пользователь."""
        return self.get_current_player_id() == user_id

    def is_participant(self, user_id: int) -> bool:
        """Проверить, является ли пользователь участником игры."""
        return user_id == self.player1_id or user_id == self.player2_id

    def get_player_number(self, user_id: int) -> int:
        """Получить номер игрока (1 или 2) по user_id."""
        if user_id == self.player1_id:
            return Board.PLAYER1
        if user_id == self.player2_id:
            return Board.PLAYER2
        return 0

    def get_opponent_chat_id(self, user_id: int) -> Optional[int]:
        """Получить chat_id противника."""
        if user_id == self.player1_id:
            return self.player2_chat_id
        return self.player1_chat_id

    def get_opponent_message_id(self, user_id: int) -> Optional[int]:
        """Получить message_id противника."""
        if user_id == self.player1_id:
            return self.player2_message_id
        return self.player1_message_id

    def set_message_info(self, user_id: int, chat_id: int, message_id: int) -> None:
        """Сохранить chat_id и message_id для игрока."""
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

    # ─── Обработка кликов ───────────────────────────────────────

    def handle_click(self, user_id: int, row: int, col: int) -> str:
        """
        Обработать нажатие на клетку.
        Returns: Текстовое сообщение о результате действия.
        """
        if self.state != GameState.PLAYING:
            return "stop"

        if not self.is_players_turn(user_id):
            return "not_your_turn"

        if not (0 <= row < 8 and 0 <= col < 8):
            return "invalid_pos"

        piece = self.board.get_piece(row, col)
        pos = (row, col)

        # ─── Если уже выбрана шашка ─────────────────────────────
        if self.selected_piece is not None:
            if pos in self.valid_moves:
                return self._execute_move(pos)

            if pos == self.selected_piece:
                self.selected_piece = None
                self.valid_moves = []
                return "deselected"

            if piece == self.current_turn:
                return self._select_piece(row, col)

            self.selected_piece = None
            self.valid_moves = []
            return "invalid"

        # ─── Шашка ещё не выбрана ────────────────────────────────
        if piece == self.current_turn:
            return self._select_piece(row, col)

        if piece != Board.EMPTY:
            return "not_yours"

        return "empty"

    def _select_piece(self, row: int, col: int) -> str:
        """Выбрать шашку и подсветить доступные ходы."""
        moves = self.board.get_valid_moves(row, col)

        # Запрет возврата в свой дом после HOME_CLEAR_LIMIT ходов
        player = self.current_turn
        move_count = (
            self.move_count_p1 if player == Board.PLAYER1 else self.move_count_p2
        )
        if move_count >= HOME_CLEAR_LIMIT:
            own_home = (
                PLAYER1_START_SET if player == Board.PLAYER1 else PLAYER2_START_SET
            )
            moves = [m for m in moves if m not in own_home]

        if not moves:
            return "no_moves"

        self.selected_piece = (row, col)
        self.valid_moves = moves
        return "selected"

    # ─── Зеркальная стратегия ────────────────────────────────────

    @staticmethod
    def _mirror_of(pos: tuple[int, int]) -> tuple[int, int]:
        """Зеркальное отражение координаты (r,c) → (7-r, 7-c)."""
        return (7 - pos[0], 7 - pos[1])

    def _is_mirror_move(
        self,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        ref_from: tuple[int, int],
        ref_to: tuple[int, int],
    ) -> bool:
        """Проверить, является ли ход зеркальным отражением другого хода."""
        return from_pos == self._mirror_of(ref_from) and to_pos == self._mirror_of(
            ref_to
        )

    # ─── Выполнение хода ────────────────────────────────────────

    def _execute_move(self, to_pos: tuple[int, int]) -> str:
        """
        Выполнить ход и переключить очередь.
        Реализует все правила из справочника:
        - Запирание фишки соперника
        - Одновременная ничья
        - Лимит вывода из дома
        - 80-й ход с подсчётом фишек
        - Трёхкратное повторение
        - Зеркальная стратегия
        """
        from_pos = self.selected_piece
        if from_pos is None:
            return "error"

        # ─── Проверка запрета запирания ──────────────────────────
        # Временно выполняем ход, проверяем, откатываем если нужно
        player = self.current_turn
        old_from = self.board.grid[from_pos[0]][from_pos[1]]
        old_to = self.board.grid[to_pos[0]][to_pos[1]]

        self.board.grid[to_pos[0]][to_pos[1]] = old_from
        self.board.grid[from_pos[0]][from_pos[1]] = Board.EMPTY

        locked = self.board.has_any_locked_opponent(player)
        if locked:
            # Откатываем ход
            self.board.grid[from_pos[0]][from_pos[1]] = old_from
            self.board.grid[to_pos[0]][to_pos[1]] = old_to
            self.selected_piece = None
            self.valid_moves = []
            return "locks_opponent"

        # Ход уже выполнен (grid обновлён выше), обновляем счётчики
        if player == Board.PLAYER1:
            self.move_count_p1 += 1
            self.move_history_p1.append((from_pos, to_pos))
        else:
            self.move_count_p2 += 1
            self.move_history_p2.append((from_pos, to_pos))

        self.selected_piece = None
        self.valid_moves = []

        # ─── Проверка зеркальной стратегии (чёрные) ──────────────
        if player == Board.PLAYER2 and len(self.move_history_p2) <= MIRROR_CHECK_MOVES:
            mirror_count = 0
            check_up_to = min(
                len(self.move_history_p2), len(self.move_history_p1), MIRROR_CHECK_MOVES
            )
            for i in range(check_up_to):
                p1_from, p1_to = self.move_history_p1[i]
                p2_from, p2_to = self.move_history_p2[i]
                if self._is_mirror_move(p2_from, p2_to, p1_from, p1_to):
                    mirror_count += 1
            if mirror_count > MIRROR_MAX_COPIES:
                # Чёрные нарушили правило зеркала — белые побеждают
                self.state = GameState.FINISHED
                self.winner = Board.PLAYER1
                self.winner_name = self.player1_name
                self.finish_reason = "mirror_violation"
                return "mirror_violation"

        # ─── Трёхкратное повторение ──────────────────────────────
        pos_hash = self.board.position_hash()
        self.position_history[pos_hash] += 1
        if self.position_history[pos_hash] >= 3:
            self.state = GameState.FINISHED
            self.finish_reason = "threefold_repetition"
            return "draw"

        # ─── Проверка победы ─────────────────────────────────────
        winner = self.board.check_winner()
        if winner == 3:
            # Оба игрока завершили одновременно — ничья
            self.state = GameState.FINISHED
            self.p1_won_pending = False
            self.finish_reason = "simultaneous_finish"
            return "draw"
        if winner:
            if winner == Board.PLAYER1 and player == Board.PLAYER1:
                # P1 выиграл на своём ходу — P2 получает ответный ход
                self.p1_won_pending = True
                self.current_turn = Board.PLAYER2
                return "p1_won_pending"
            elif winner == Board.PLAYER2 and self.p1_won_pending:
                # P2 тоже завершил после P1 — ничья!
                self.state = GameState.FINISHED
                self.p1_won_pending = False
                self.finish_reason = "simultaneous_finish"
                return "draw"
            else:
                # Чистая победа
                self.state = GameState.FINISHED
                self.winner = winner
                self.winner_name = (
                    self.player1_name if winner == Board.PLAYER1 else self.player2_name
                )
                self.finish_reason = "win"
                return "win"

        # Если P1 выиграл на прошлом ходу, а P2 не смог завершить — P1 побеждает
        if self.p1_won_pending and player == Board.PLAYER2:
            self.state = GameState.FINISHED
            self.winner = Board.PLAYER1
            self.winner_name = self.player1_name
            self.p1_won_pending = False
            self.finish_reason = "win"
            return "win"

        # ─── Лимит вывода шашек из дома ──────────────────────────
        move_count = (
            self.move_count_p1 if player == Board.PLAYER1 else self.move_count_p2
        )
        if move_count >= HOME_CLEAR_LIMIT:
            if self.board.has_pieces_in_home(player):
                # Игрок не вывел все фишки из дома к лимиту — проигрыш
                self.state = GameState.FINISHED
                opponent = Board.PLAYER2 if player == Board.PLAYER1 else Board.PLAYER1
                self.winner = opponent
                self.winner_name = (
                    self.player1_name
                    if opponent == Board.PLAYER1
                    else self.player2_name
                )
                self.finish_reason = "home_clear_violation"
                return "home_clear_loss"

        # ─── Лимит ходов: подсчёт фишек ────────────────────────────
        if self.max_moves > 0:
            total_moves = self.move_count_p1 + self.move_count_p2
            if total_moves >= self.max_moves * 2:
                self.state = GameState.FINISHED
                # Считаем фишки в доме соперника
                p1_in_goal = self.board.count_pieces_in_zone(Board.PLAYER1, self.board.home1)
                p2_in_goal = self.board.count_pieces_in_zone(Board.PLAYER2, self.board.home2)
                if p1_in_goal > p2_in_goal:
                    self.winner = Board.PLAYER1
                    self.winner_name = self.player1_name
                    self.finish_reason = "move_limit_score"
                    return "win"
                elif p2_in_goal > p1_in_goal:
                    self.winner = Board.PLAYER2
                    self.winner_name = self.player2_name
                    self.finish_reason = "move_limit_score"
                    return "win"
                else:
                    self.finish_reason = "move_limit_draw"
                    return "draw"

        # ─── Переключить ход ─────────────────────────────────────
        if not self.p1_won_pending:
            self.current_turn = (
                Board.PLAYER2 if self.current_turn == Board.PLAYER1 else Board.PLAYER1
            )

        return "moved"

    # ─── Ход ИИ ─────────────────────────────────────────────────

    def make_ai_move(self) -> str:
        """ИИ делает ход (для режима PvE). Использует _execute_move для проверки правил."""
        if self.ai is None:
            return ""
        if self.state != GameState.PLAYING:
            return ""
        if self.current_turn != Board.PLAYER2:
            return ""

        move = self.ai.get_best_move(self.board)
        if move is None:
            return "ai_stuck"

        from_pos, to_pos = move

        # Используем _execute_move для проверки всех правил
        self.selected_piece = from_pos
        self.valid_moves = self.board.get_valid_moves(*from_pos)

        result = self._execute_move(to_pos)

        fr, fc = from_pos
        tr, tc = to_pos

        if result in ("win", "draw", "home_clear_loss", "p1_won_pending"):
            return result

        return f"ai_moved_{fr}_{fc}_{tr}_{tc}"

    # ─── Текст статуса ──────────────────────────────────────────

    def get_status_text(self, for_user_id: Optional[int] = None) -> str:
        """Текст статуса для сообщения над доской."""
        from config import UGOLKI_VARIANTS
        var_name = UGOLKI_VARIANTS.get(self.variant, {}).get("name", "Классика")
        
        if self.state == GameState.WAITING:
            return f"⏳ Ожидание второго игрока ({var_name})...\nОтправьте ссылку другу!"

        if self.state == GameState.FINISHED:
            if self.winner:
                emoji = EMOJI_PLAYER1 if self.winner == Board.PLAYER1 else EMOJI_PLAYER2
                reason_text = ""
                if self.finish_reason == "home_clear_violation":
                    reason_text = "\n⚠️ Соперник не вывел фишки из дома вовремя!"
                elif self.finish_reason == "move_limit_score":
                    p1_in = self.board.count_pieces_in_zone(
                        Board.PLAYER1, self.board.home1
                    )
                    p2_in = self.board.count_pieces_in_zone(
                        Board.PLAYER2, self.board.home2
                    )
                    reason_text = f"\n📊 Лимит ходов! Фишек в доме: {EMOJI_PLAYER1}{p1_in} vs {EMOJI_PLAYER2}{p2_in}"
                elif self.finish_reason == "mirror_violation":
                    reason_text = "\n🪞 Чёрные нарушили запрет зеркальной стратегии!"
                elif self.finish_reason == "surrender":
                    reason_text = "\n🏳️ Противник сдался!"
                return (
                    f"🏆 Победитель: {emoji} {self.winner_name}{reason_text}\n"
                    f"Ходов: {EMOJI_PLAYER1} {self.move_count_p1} | "
                    f"{EMOJI_PLAYER2} {self.move_count_p2}\n"
                    f"Нажмите /play для новой игры!"
                )
            # Ничья
            reason_text = ""
            if self.finish_reason == "simultaneous_finish":
                reason_text = "\n🤝 Оба игрока завершили одновременно!"
            elif self.finish_reason == "threefold_repetition":
                reason_text = "\n🔄 Трёхкратное повторение позиции!"
            elif self.finish_reason == "move_limit_draw":
                reason_text = "\n⏰ Лимит ходов! Одинаковое число фишек в доме."
            return f"🤝 Ничья!{reason_text}\nНажмите /play для новой игры!"

        # Игра идёт
        turn_emoji = (
            EMOJI_PLAYER1 if self.current_turn == Board.PLAYER1 else EMOJI_PLAYER2
        )
        turn_name = self.get_current_player_name()
        mode_text = f"PvP | {var_name}" if self.mode == GameMode.PVP else f"vs 🤖 | {var_name}"

        # Показываем кто вы (только для обычных игр, так как в inline оба видят один текст)
        you_info = ""
        if for_user_id and self.mode == GameMode.PVP and not self.is_inline:
            pnum = self.get_player_number(for_user_id)
            you_emoji = EMOJI_PLAYER1 if pnum == Board.PLAYER1 else EMOJI_PLAYER2
            is_your_turn = self.is_players_turn(for_user_id)
            you_info = f"\nВы: {you_emoji} | {'🎯 Ваш ход!' if is_your_turn else '⏳ Ход противника'}"

        limit_str = f"/{self.max_moves}" if self.max_moves > 0 else ""
        return (
            f"🎮 Уголки | {mode_text}\n"
            f"Ход: {turn_emoji} {turn_name}"
            f"{you_info}\n"
            f"{EMOJI_PLAYER1} {self.player1_name}: {self.move_count_p1}{limit_str} | "
            f"{EMOJI_PLAYER2} {self.player2_name}: {self.move_count_p2}{limit_str}"
        )


class GameManager:
    """Управление игровыми сессиями."""

    def __init__(self) -> None:
        self.games: dict[str, Game] = {}  # game_id → Game
        self.user_games: dict[int, str] = {}  # user_id → game_id
        self.chat_games: dict[int, str] = {}  # chat_id → game_id (для групп)

    def create_game(
        self,
        player1_id: int,
        player1_name: str,
        mode: GameMode,
        chat_id: Optional[int] = None,
        variant: str = "classic",
    ) -> Game:
        """Создать новую игру. Возвращает Game с уникальным game_id."""
        game_id = uuid.uuid4().hex[:8]
        game = Game(game_id, player1_id, player1_name, mode, variant=variant)

        self.games[game_id] = game
        self.user_games[player1_id] = game_id

        if chat_id:
            self.chat_games[chat_id] = game_id

        return game

    def get_game_by_id(self, game_id: str) -> Optional[Game]:
        """Получить игру по ID."""
        return self.games.get(game_id)

    def get_game_by_user(self, user_id: int) -> Optional[Game]:
        """Получить текущую игру пользователя."""
        game_id = self.user_games.get(user_id)
        if game_id:
            return self.games.get(game_id)
        return None

    def get_game_by_chat(self, chat_id: int) -> Optional[Game]:
        """Получить игру по chat_id (для групп)."""
        game_id = self.chat_games.get(chat_id)
        if game_id:
            return self.games.get(game_id)
        return None

    def get_inline_game(self, inline_message_id: str, variant: str = "classic") -> Optional[Game]:
        """Получить или создать inline-игру по inline_message_id."""
        if inline_message_id in self.games:
            return self.games[inline_message_id]

        game = Game(inline_message_id, 0, "", GameMode.PVP, variant=variant)
        game.is_inline = True
        game.inline_message_id = inline_message_id
        game.show_hints = False
        self.games[inline_message_id] = game
        return game

    def join_game(
        self, game_id: str, player2_id: int, player2_name: str
    ) -> Optional[Game]:
        """Второй игрок присоединяется к игре по game_id."""
        game = self.games.get(game_id)
        if game is None:
            return None
        if not game.join(player2_id, player2_name):
            return None
        self.user_games[player2_id] = game_id
        return game

    def remove_game_for_user(self, user_id: int) -> None:
        """Удалить привязку игры для пользователя."""
        game_id = self.user_games.pop(user_id, None)
        if game_id and game_id in self.games:
            game = self.games[game_id]
            # Удаляем игру полностью если оба ушли
            other_id = (
                game.player2_id if user_id == game.player1_id else game.player1_id
            )
            if other_id and other_id not in self.user_games:
                del self.games[game_id]

    def remove_game(self, game_id: str) -> None:
        """Полностью удалить игру."""
        game = self.games.pop(game_id, None)
        if game:
            self.user_games.pop(game.player1_id, None)
            if game.player2_id:
                self.user_games.pop(game.player2_id, None)

    def has_active_game(self, user_id: int) -> bool:
        """Есть ли у пользователя активная игра."""
        game = self.get_game_by_user(user_id)
        return game is not None and game.state != GameState.FINISHED
