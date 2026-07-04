"""
Telegram Bot «Ugolki» (Corners / Halma)

Glavnyy modul: Telegram handlers, zapusk bota.
Podderzhivaet PvP cherez deep link (lichnye chaty) i PvE.
"""

from __future__ import annotations
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, BotCommand, WebAppInfo
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes,
)
from telegram import InlineQueryResultArticle, InputTextMessageContent

from config import BOT_TOKEN, AI_MOVE_DELAY
from games.ugolki.game import GameManager, GameMode, GameState
from games.ugolki.board import Board
from games.checkers.game import GameManager as CheckersManager, GameMode as CheckersMode
from games.checkers.board import Board as CheckersBoard
from games.chess.game import (
    GameManager as ChessManager,
    ChessMode,
    GameState as ChessGameState,
)
from games.chess.board import Board as ChessBoard

# ─── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Game Manager ───────────────────────────────────────────────
manager = GameManager()
checkers_manager = CheckersManager()
chess_manager = ChessManager()


# ═══════════════════════════════════════════════════════════════
#  HELPER: get bot username for deep links
# ═══════════════════════════════════════════════════════════════
_bot_username: str = ""


async def _get_bot_username(bot: Bot) -> str:
    global _bot_username
    if not _bot_username:
        me = await bot.get_me()
        _bot_username = me.username or ""
    return _bot_username


# ═══════════════════════════════════════════════════════════════
#  HELPER: update board for both players
# ═══════════════════════════════════════════════════════════════
async def _update_board_for_player(
    bot: Bot, game, user_id: int, chat_id: int, message_id: int
) -> None:
    """Send updated board to one player."""
    status = game.get_status_text(for_user_id=user_id)
    keyboard = game.board.to_inline_keyboard(
        selected=game.selected_piece if game.is_players_turn(user_id) else None,
        valid_moves=game.valid_moves if game.is_players_turn(user_id) else [],
        game_over=(game.state.name == "FINISHED"),
        timer_text=game.get_elapsed_time_str(),
        finish_reason=game.finish_reason,
        flip_board=(user_id == game.player2_id),
        show_hints=getattr(game, "show_hints", True),
    )
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=status,
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"Failed to update board for {user_id}: {e}")


async def _update_both_boards(bot: Bot, game) -> None:
    """Update boards for both players in PvP, or shared board in inline mode."""
    if getattr(game, "is_inline", False) and getattr(game, "inline_message_id", None):
        status = game.get_status_text()
        keyboard = game.board.to_inline_keyboard(
            selected=game.selected_piece,
            valid_moves=game.valid_moves,
            game_over=(game.state.name == "FINISHED"),
            timer_text=game.get_elapsed_time_str(),
            finish_reason=game.finish_reason,
            show_hints=getattr(game, "show_hints", True),
        )
        try:
            await bot.edit_message_text(
                inline_message_id=game.inline_message_id,
                text=status,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"Failed to update inline board: {e}")
        return

    if game.player1_chat_id and game.player1_message_id:
        await _update_board_for_player(
            bot,
            game,
            game.player1_id,
            game.player1_chat_id,
            game.player1_message_id,
        )
    if game.player2_chat_id and game.player2_message_id and game.player2_id != -1:
        await _update_board_for_player(
            bot,
            game,
            game.player2_id,
            game.player2_chat_id,
            game.player2_message_id,
        )


async def _offer_new_game(context: ContextTypes.DEFAULT_TYPE, game) -> None:
    """Отправляет предложение сыграть еще раз после завершения игры."""
    await asyncio.sleep(1.0)  # Небольшая задержка, чтобы доска успела обновиться

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎮 Играть ещё раз", callback_data="show_games_menu")]]
    )
    text = "🏁 Игра завершена!\nХотите сыграть во что-нибудь ещё?"

    if getattr(game, "is_inline", False):
        return  # В инлайн-режиме не отправляем новое сообщение

    if game.player1_chat_id:
        try:
            await context.bot.send_message(
                chat_id=game.player1_chat_id, text=text, reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Failed to offer new game to p1: {e}")

    if game.player2_chat_id and game.player2_id != -1:
        try:
            await context.bot.send_message(
                chat_id=game.player2_chat_id, text=text, reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Failed to offer new game to p2: {e}")


# ═══════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome or deep link join."""
    user = update.effective_user
    user_name = user.first_name or user.username or f"Player {user.id}"

    # Check for deep link: /start join_GAMEID or /start pvp_GAMEID
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("join_"):
            game_id = arg[5:]
            await _handle_join_via_link(update, user, user_name, game_id)
            return
        elif arg.startswith("pvp_"):
            # Мультиплеер через Mini App — отправляем кнопку для открытия игры
            game_id = arg  # полный ID вида pvp_xxxxx
            join_url = f"https://Ersultan000.pythonanywhere.com/?start_param={game_id}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🎮 Присоединиться к игре!",
                    web_app=WebAppInfo(url=join_url)
                )]
            ])
            await update.message.reply_text(
                f"🎲 Вас пригласили сыграть в настольную игру!\n\n"
                f"Нажмите кнопку ниже, чтобы присоединиться:",
                reply_markup=keyboard
            )
            return

    welcome_text = (
        "🎲 *Добро пожаловать в Бота Настольных Игр!*\n\n"
        "Здесь вы можете сыграть в классические настольные игры: "
        "Уголки, Русские Шашки и Шахматы.\n\n"
        "📋 *Команды:*\n"
        "/play — Начать новую игру\n"
        "/rules — Правила игр\n"
        "/cancel — Отменить текущую игру\n\n"
        "Выберите действие ниже, чтобы начать! 🎯"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 Открыть Mini App", web_app=WebAppInfo(url="https://Ersultan000.pythonanywhere.com/"))],
            [InlineKeyboardButton("🎮 Классические Игры (Текст)", callback_data="show_games_menu")],
            [InlineKeyboardButton("📜 Правила", callback_data="rules_dummy")],
        ]
    )

    await update.message.reply_text(
        welcome_text, reply_markup=keyboard, parse_mode="Markdown"
    )


async def _handle_join_via_link(update, user, user_name, game_id) -> None:
    """Handle a player joining via invite deep link."""
    # Check if user already has an active game
    if (
        manager.has_active_game(user.id)
        or checkers_manager.has_active_game(user.id)
        or chess_manager.has_active_game(user.id)
    ):
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра!\n"
            "Используйте /cancel чтобы завершить текущую."
        )
        return

    # Try to join Ugolki
    game = manager.join_game(game_id, user.id, user_name)
    if game is None:
        # Try to join Checkers
        game = checkers_manager.join_game(game_id, user.id, user_name)
    if game is None:
        # Try to join Chess
        game = chess_manager.join_game(game_id, user.id, user_name)

    if game is None:
        await update.message.reply_text(
            "❌ Не удалось присоединиться.\n"
            "Возможно, игра не существует, уже началась, или вы её создатель."
        )
        return

    # Save player 2 chat info
    chat_id = update.effective_chat.id

    # Send board to player 2
    status = game.get_status_text(for_user_id=user.id)
    keyboard = game.board.to_inline_keyboard(
        timer_text=game.get_elapsed_time_str(), finish_reason=game.finish_reason
    )
    msg = await update.message.reply_text(status, reply_markup=keyboard)
    game.set_message_info(user.id, chat_id, msg.message_id)

    # Update player 1's board too (game started!)
    if game.player1_chat_id and game.player1_message_id:
        await _update_board_for_player(
            update.get_bot(),
            game,
            game.player1_id,
            game.player1_chat_id,
            game.player1_message_id,
        )

    # Also notify player 1 with a new message
    if game.player1_chat_id:
        try:
            bot = update.get_bot()
            notify_text = (
                f"🎮 {user_name} присоединился! Игра началась!\nВы ходите первым (⚪)."
            )
            await bot.send_message(chat_id=game.player1_chat_id, text=notify_text)

            # Send fresh board to P1
            status1 = game.get_status_text(for_user_id=game.player1_id)
            keyboard1 = game.board.to_inline_keyboard(
                timer_text=game.get_elapsed_time_str(), finish_reason=game.finish_reason
            )
            msg1 = await bot.send_message(
                chat_id=game.player1_chat_id,
                text=status1,
                reply_markup=keyboard1,
            )
            game.update_message_id(game.player1_id, msg1.message_id)
        except Exception as e:
            logger.warning(f"Failed to notify player 1: {e}")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rules command."""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏁 Уголки", callback_data="rules_ugolki")],
            [InlineKeyboardButton("🟤 Шашки", callback_data="rules_checkers")],
            [InlineKeyboardButton("♛ Шахматы", callback_data="rules_chess")],
        ]
    )
    await update.message.reply_text(
        "📜 *Правила игр*\n\nВыберите игру, чтобы узнать правила:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


RULES_UGOLKI = (
    "📜 *Правила игры «Уголки»*\n\n"
    "*Цель:* Первым переместить все свои шашки в «дом» противника "
    "(противоположный угол доски).\n\n"
    "*Начальная позиция:* У каждого игрока 14 шашек, "
    "расположенных треугольником в углу доски 8×8.\n\n"
    "*Ходы:*\n"
    "1️⃣ *Простой ход* — переместить шашку на 1 клетку "
    "по горизонтали, вертикали или диагонали.\n"
    "2️⃣ *Прыжок* — перепрыгнуть через соседнюю шашку (свою или чужую) "
    "на свободную клетку за ней.\n"
    "3️⃣ *Цепочка* — за один ход можно сделать несколько прыжков подряд.\n\n"
    "❗ Шашки НЕ «съедаются» — все остаются на доске!\n\n"
    "*Победа:*\n"
    "🏆 Побеждает тот, кто первым полностью занял угол противника.\n"
    "⏰ Лимит: 40 ходов на каждого игрока.\n\n"
    "*Управление:*\n"
    "1. Нажмите на свою шашку — она подсветится 🟡\n"
    "2. Нажмите на зелёную клетку 🟢 — сделать ход\n"
    "3. Нажмите на 🟡 ещё раз — отменить выбор"
)

RULES_CHECKERS = (
    "📜 *Правила игры «Русские Шашки»*\n\n"
    "*Цель:* Забрать все шашки противника или лишить их возможности хода.\n\n"
    "*Начальная позиция:* У каждого игрока 12 шашек "
    "на тёмных клетках доски 8×8.\n\n"
    "*Ходы:*\n"
    "1️⃣ *Простой ход* — двигать шашку по диагонали на 1 клетку вперёд.\n"
    "2️⃣ *Взятие (бой)* — обязательно! Перепрыгнуть через вражескую "
    "шашку по диагонали. Можно бить вперёд и назад.\n"
    "3️⃣ *Серия взятий* — если после боя можно побить ещё, "
    "вы обязаны продолжить цепочку.\n\n"
    "*Дамка:* 👑\n"
    "Если шашка дошла до последней горизонтали, она становится дамкой. "
    "Дамка ходит по диагонали на любое число клеток.\n\n"
    "*Победа:*\n"
    "🏆 Побеждает тот, кто забрал все шашки противника "
    "или заблокировал их.\n"
    "🤝 Ничья — если ни один из игроков не может выиграть."
)

RULES_CHESS = (
    "📜 *Правила игры «Шахматы»*\n\n"
    "*Цель:* Поставить мат королю противника (король под атакой и не может спастись).\n\n"
    "*Фигуры и их ходы:*\n"
    "♚ *Король* — 1 клетка в любом направлении.\n"
    "♛ *Ферзь* — любое количество клеток по горизонтали, "
    "вертикали или диагонали.\n"
    "♜ *Ладья* — по горизонтали или вертикали.\n"
    "♝ *Слон* — по диагонали.\n"
    "♞ *Конь* — буквой «Г» (2+1 клетка), перепрыгивает через фигуры.\n"
    "▲ *Пешка* — на 1 вперёд (или 2 с начальной позиции), "
    "бьёт по диагонали.\n\n"
    "*Особые ходы:*\n"
    "🏰 *Рокировка* — король + ладья меняются местами.\n"
    "👑 *Превращение* — пешка на последней горизонтали "
    "превращается в ферзя.\n"
    "⚔️ *Взятие на проходе* — особый бой пешки.\n\n"
    "*Победа:*\n"
    "🏆 Мат — вы победили!\n"
    "🤝 Ничья — пат, повторение позиции, правило 50 ходов.\n\n"
    "*Управление:*\n"
    "1. Нажмите на свою фигуру — она подсветится 🟡\n"
    "2. Зелёные клетки 🟢 — доступные ходы\n"
    "3. Красные клетки 🔴 — можно побить вражескую фигуру"
)


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /play — choose game mode."""
    user = update.effective_user

    if (
        manager.has_active_game(user.id)
        or checkers_manager.has_active_game(user.id)
        or chess_manager.has_active_game(user.id)
    ):
        await update.message.reply_text(
            "⚠️ У вас уже есть активная игра!\n"
            "Используйте /cancel чтобы завершить текущую."
        )
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🏁 Уголки", callback_data="select_game_ugolki")],
            [InlineKeyboardButton("🟤 Шашки", callback_data="select_game_checkers")],
            [InlineKeyboardButton("♛ Шахматы", callback_data="select_game_chess")],
            [InlineKeyboardButton("⚪ Го (в разработке)", callback_data="dev_dummy")],
        ]
    )
    await update.message.reply_text("Выберите игру:", reply_markup=keyboard)


async def show_ugolki_menu(query) -> None:
    """Show variations for Ugolki."""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Классика (3x4)", callback_data="ugolki_var_classic")],
            [InlineKeyboardButton("Квадрат (3x3)", callback_data="ugolki_var_square")],
            [InlineKeyboardButton("Треугольник", callback_data="ugolki_var_triangle")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="show_games_menu")],
        ]
    )
    await query.edit_message_text(
        "🎮 *Выберите вариацию игры в Уголки:*",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

async def show_ugolki_mode_menu(query, variant: str) -> None:
    """Show modes for a specific Ugolki variant."""
    from config import UGOLKI_VARIANTS
    var_name = UGOLKI_VARIANTS.get(variant, {}).get("name", "Уголки")
    
    # query_str e.g. "ugolki square" or "ugolki triangle" or empty for classic (or "ugolki classic")
    query_str = f"ugolki {variant}" if variant != "classic" else ""
    
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👊 Играть с другом ↗️", switch_inline_query=query_str),
            ],
            [
                InlineKeyboardButton(
                    "👥 Два игрока (По ссылке)", callback_data=f"ugolki_pvp_{variant}"
                ),
            ],
            [
                InlineKeyboardButton("🤖 Против бота (PvE)", callback_data=f"ugolki_pve_{variant}"),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="select_game_ugolki"),
            ],
        ]
    )
    await query.edit_message_text(
        f"🎮 *Уголки: {var_name}*\nВыберите режим игры:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def show_checkers_menu(query) -> None:
    """Show modes for Checkers."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👊 Играть с другом ↗️", switch_inline_query="checkers"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👥 Два игрока (По ссылке)", callback_data="checkers_mode_pvp"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🤖 Против бота (PvE)", callback_data="checkers_mode_pve"
                ),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="show_games_menu"),
            ],
        ]
    )
    await query.edit_message_text(
        "🟤 *Выберите режим игры в Шашки:*",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def show_chess_menu(query) -> None:
    """Show modes for Chess."""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👊 Играть с другом ↗️", switch_inline_query="chess"
                ),
            ],
            [
                InlineKeyboardButton(
                    "👥 Два игрока (По ссылке)", callback_data="chess_mode_pvp"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🤖 Против бота (PvE)", callback_data="chess_mode_pve"
                ),
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="show_games_menu"),
            ],
        ]
    )
    await query.edit_message_text(
        "♛ *Выберите режим игры в Шахматы:*",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel."""
    user = update.effective_user
    game = manager.get_game_by_user(user.id)
    active_mgr = manager
    if game is None:
        game = checkers_manager.get_game_by_user(user.id)
        active_mgr = checkers_manager
    if game is None:
        game = chess_manager.get_game_by_user(user.id)
        active_mgr = chess_manager

    if game is None:
        await update.message.reply_text("❌ Нет активной игры для отмены.")
        return

    game_id = game.game_id
    active_mgr.remove_game(game_id)
    await update.message.reply_text(
        "🚫 Игра отменена. Используйте /play для новой игры."
    )


# ═══════════════════════════════════════════════════════════════
#  INLINE QUERY HANDLER
# ═══════════════════════════════════════════════════════════════
from uuid import uuid4


async def handle_inline_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline queries to send the game to any chat."""
    query = update.inline_query.query.strip().lower()
    
    results = []
    
    from config import UGOLKI_VARIANTS
    
    # Determine which Ugolki variant to show
    variant_to_show = "classic"
    if query.startswith("ugolki "):
        requested_var = query.split(" ")[1]
        if requested_var in UGOLKI_VARIANTS:
            variant_to_show = requested_var
            
    var_name = UGOLKI_VARIANTS.get(variant_to_show, {}).get("name", "Классика")
    
    if not query or query.startswith("ugolki"):
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=f"🎮 Начать игру в Уголки ({var_name})",
                description="Отправить приглашение в этот чат",
                input_message_content=InputTextMessageContent(
                    f"🎮 **Игра Уголки: {var_name} (PvP)**\n"
                    "Ожидание игроков...\n"
                    "Нажмите кнопку ниже, чтобы присоединиться!",
                    parse_mode="Markdown",
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🎮 Присоединиться к игре",
                                callback_data=f"inline_join_ugolki_{variant_to_show}",
                            )
                        ]
                    ]
                ),
            )
        )
        
    if not query or query == "checkers":
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="🟤 Начать игру в Шашки",
                description="Отправить приглашение в этот чат",
                input_message_content=InputTextMessageContent(
                    "🟤 **Игра Русские Шашки (PvP)**\n"
                    "Ожидание игроков...\n"
                    "Нажмите кнопку ниже, чтобы присоединиться!",
                    parse_mode="Markdown",
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🟤 Присоединиться к игре",
                                callback_data="inline_join_checkers",
                            )
                        ]
                    ]
                ),
            )
        )
        
    if not query or query == "chess":
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="♛ Начать игру в Шахматы",
                description="Отправить приглашение в этот чат",
                input_message_content=InputTextMessageContent(
                    "♛ **Игра Шахматы (PvP)**\n"
                    "Ожидание игроков...\n"
                    "Нажмите кнопку ниже, чтобы присоединиться!",
                    parse_mode="Markdown",
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "♛ Присоединиться к игре",
                                callback_data="inline_join_chess",
                            )
                        ]
                    ]
                ),
            )
        )

    await update.inline_query.answer(results, cache_time=0)


# ═══════════════════════════════════════════════════════════════
#  CALLBACK HANDLERS
# ═══════════════════════════════════════════════════════════════


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all callback queries."""
    query = update.callback_query
    data = query.data
    if not data:
        await query.answer()
        return

    # ─── Game Selection ──────────────────────────────────────────
    if data == "show_games_menu":
        await query.answer()
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏁 Уголки", callback_data="select_game_ugolki")],
                [InlineKeyboardButton("🟤 Шашки", callback_data="select_game_checkers")],
                [InlineKeyboardButton("♛ Шахматы", callback_data="select_game_chess")],
                [InlineKeyboardButton("⚪ Го (в разработке)", callback_data="dev_dummy")],
            ]
        )
        await query.edit_message_text("Выберите игру:", reply_markup=keyboard)
        return

    if data == "select_game_ugolki":
        await query.answer()
        await show_ugolki_menu(query)
        return

    if data == "select_game_checkers":
        await query.answer()
        await show_checkers_menu(query)
        return

    if data == "select_game_chess":
        await query.answer()
        await show_chess_menu(query)
        return

    if data == "dev_dummy":
        await query.answer("Эта игра еще в разработке!", show_alert=True)
        return

    # ─── Inline Join ──────────────────────────────────────────────
    if (
        data.startswith("inline_join_")
    ) and query.inline_message_id:
        variant = "classic"
        if "checkers" in data:
            active_mgr = checkers_manager
            game_title = "Русские Шашки"
            join_cb = "inline_join_checkers"
            circle_emoji = "🟤"
        elif "chess" in data:
            active_mgr = chess_manager
            game_title = "Шахматы"
            join_cb = "inline_join_chess"
            circle_emoji = "♛"
        else:
            active_mgr = manager
            if data.startswith("inline_join_ugolki_"):
                variant = data.replace("inline_join_ugolki_", "")
            from config import UGOLKI_VARIANTS
            var_name = UGOLKI_VARIANTS.get(variant, {}).get("name", "Классика")
            game_title = f"Уголки ({var_name})"
            join_cb = f"inline_join_ugolki_{variant}"
            circle_emoji = "🎮"

        if active_mgr == manager:
            game = active_mgr.get_inline_game(query.inline_message_id, variant=variant)
        else:
            game = active_mgr.get_inline_game(query.inline_message_id)
        user = query.from_user

        if game.state.name == "FINISHED":
            await query.answer("Игра уже завершена!", show_alert=True)
            return

        if game.player1_id == user.id or game.player2_id == user.id:
            await query.answer("Вы уже в игре!", show_alert=True)
            return

        if game.player1_id == 0:
            game.player1_id = user.id
            game.player1_name = user.first_name or user.username or "Игрок 1"
            await query.answer("Вы играете за Белых (⚪)!")

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"{circle_emoji} Присоединиться (Игрок 2)",
                            callback_data=join_cb,
                        )
                    ]
                ]
            )
            await context.bot.edit_message_text(
                inline_message_id=query.inline_message_id,
                text=f"{circle_emoji} **Игра {game_title} (PvP)**\n⚪ Белые: {game.player1_name}\n⏳ Ожидание второго игрока...",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        elif game.player2_id is None:
            game.player2_id = user.id
            game.player2_name = user.first_name or user.username or "Игрок 2"
            game.state = game.state.__class__.PLAYING  # Duck-typed state assignment
            await query.answer("Вы играете за Черных (⚫)! Игра начинается.")
            await _update_both_boards(context.bot, game)
        else:
            await query.answer("Мест нет!", show_alert=True)
        return

    if data.startswith("ugolki_var_"):
        await query.answer()
        variant = data.replace("ugolki_var_", "")
        await show_ugolki_mode_menu(query, variant)
        return

    if data.startswith("ugolki_pvp_"):
        await query.answer()
        variant = data.replace("ugolki_pvp_", "")
        await _handle_mode_pvp(query, context, variant=variant)
        return

    if data.startswith("ugolki_pve_"):
        await query.answer()
        variant = data.replace("ugolki_pve_", "")
        await _handle_mode_pve(query, context, variant=variant)
        return

    if data == "checkers_mode_pvp":
        await query.answer()
        await _handle_checkers_mode_pvp(query, context)
        return

    if data == "checkers_mode_pve":
        await query.answer()
        await _handle_checkers_mode_pve(query, context)
        return

    if data == "chess_mode_pvp":
        await query.answer()
        await _handle_chess_mode_pvp(query, context)
        return

    if data == "chess_mode_pve":
        await query.answer()
        await _handle_chess_mode_pve(query, context)
        return

    if data == "rules_dummy":
        await query.answer()
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏁 Уголки", callback_data="rules_ugolki")],
                [InlineKeyboardButton("🟤 Шашки", callback_data="rules_checkers")],
                [InlineKeyboardButton("♛ Шахматы", callback_data="rules_chess")],
            ]
        )
        await query.edit_message_text(
            "📜 *Правила игр*\n\nВыберите игру, чтобы узнать правила:",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    if data in ("rules_ugolki", "rules_checkers", "rules_chess"):
        await query.answer()
        rules_map = {
            "rules_ugolki": RULES_UGOLKI,
            "rules_checkers": RULES_CHECKERS,
            "rules_chess": RULES_CHESS,
        }
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Назад к списку", callback_data="rules_dummy")]]
        )
        await query.edit_message_text(
            rules_map[data],
            reply_markup=back_btn,
            parse_mode="Markdown",
        )
        return

    # ─── Cell click ──────────────────────────────────────────────
    if data.startswith("cell_"):
        await _handle_cell_click(query, context)
        return

    # ─── Game controls ───────────────────────────────────────────
    if data == "surrender":
        user = query.from_user
        game = None
        if query.inline_message_id:
            if query.inline_message_id in checkers_manager.games:
                game = checkers_manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in manager.games:
                game = manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in chess_manager.games:
                game = chess_manager.get_inline_game(query.inline_message_id)
        else:
            game = manager.get_game_by_user(user.id)
            if game is None:
                game = checkers_manager.get_game_by_user(user.id)
            if game is None:
                game = chess_manager.get_game_by_user(user.id)

        if game and game.state.name == "PLAYING" and game.is_participant(user.id):
            game.surrender(user.id)
            await _update_both_boards(context.bot, game)
            await query.answer("Вы сдались!", show_alert=True)
            await _offer_new_game(context, game)
        else:
            await query.answer("Невозможно сдаться", show_alert=True)
        return

    if data == "draw":
        user = query.from_user
        game = None
        if query.inline_message_id:
            if query.inline_message_id in checkers_manager.games:
                game = checkers_manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in manager.games:
                game = manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in chess_manager.games:
                game = chess_manager.get_inline_game(query.inline_message_id)
        else:
            game = manager.get_game_by_user(user.id)
            if game is None:
                game = checkers_manager.get_game_by_user(user.id)
            if game is None:
                game = chess_manager.get_game_by_user(user.id)

        if game and game.state.name == "PLAYING" and game.is_participant(user.id):
            if game.mode.value == "pve":
                await query.answer("Бот не согласен на ничью!", show_alert=True)
            else:
                await query.answer("Ничья в PvP пока не реализована", show_alert=True)
        else:
            await query.answer("Невозможно предложить ничью", show_alert=True)
        return

    if data == "toggle_hints":
        user = query.from_user
        
        # Check inline games first
        game = None
        if query.inline_message_id:
            if query.inline_message_id in checkers_manager.games:
                game = checkers_manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in manager.games:
                game = manager.get_inline_game(query.inline_message_id)
            elif query.inline_message_id in chess_manager.games:
                game = chess_manager.get_inline_game(query.inline_message_id)
        else:
            game = manager.get_game_by_user(user.id)
            if game is None:
                game = checkers_manager.get_game_by_user(user.id)
            if game is None:
                game = chess_manager.get_game_by_user(user.id)

        if game and game.state.name == "PLAYING" and game.is_participant(user.id):
            game.show_hints = not getattr(game, "show_hints", True)
            await query.answer(f"Подсказки {'ВКЛЮЧЕНЫ' if game.show_hints else 'ВЫКЛЮЧЕНЫ'}")
            await _update_both_boards(context.bot, game)
        else:
            await query.answer("Вы не можете изменить эту настройку", show_alert=True)
        return

    if data in ("extend_40", "extend_inf"):
        user = query.from_user
        game = manager.get_game_by_user(user.id)
        if game is None:
            game = checkers_manager.get_game_by_user(user.id)

        if (
            game
            and game.state.name == "FINISHED"
            and game.finish_reason in ("move_limit_score", "move_limit_draw")
        ):
            extra = 40 if data == "extend_40" else 0
            if hasattr(game, "extend_game"):
                game.extend_game(extra)
                await _update_both_boards(context.bot, game)
                await query.answer("Игра продлена!", show_alert=True)
            else:
                await query.answer("Функция не поддерживается", show_alert=True)
        else:
            await query.answer("Продление недоступно", show_alert=True)
        return

    # ─── Noop (headers, etc.) ────────────────────────────────────
    if data.startswith("noop"):
        await query.answer()
        return

    await query.answer()


async def _handle_mode_pvp(query, context: ContextTypes.DEFAULT_TYPE, variant: str = "classic") -> None:
    """Create PvP game and generate invite link."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if manager.has_active_game(user.id) or checkers_manager.has_active_game(user.id):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = manager.create_game(user.id, user_name, GameMode.PVP, chat_id=chat_id, variant=variant)

    # Save player 1's chat info
    game.player1_chat_id = chat_id

    # Generate invite link
    bot_username = await _get_bot_username(context.bot)
    invite_link = f"https://t.me/{bot_username}?start=join_{game.game_id}"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📨 Отправить приглашение", url=invite_link)],
        ]
    )

    msg = await query.edit_message_text(
        f"👥 *Режим: два игрока (PvP)*\n\n"
        f"Вы: ⚪ {user_name}\n"
        f"⏳ Ожидание второго игрока...\n\n"
        f"📨 Отправьте эту ссылку другу:\n"
        f"`{invite_link}`\n\n"
        f"Или нажмите кнопку ниже!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    game.player1_message_id = msg.message_id


async def _handle_mode_pve(query, context: ContextTypes.DEFAULT_TYPE, variant: str = "classic") -> None:
    """Create PvE game and show board."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if manager.has_active_game(user.id) or checkers_manager.has_active_game(user.id):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = manager.create_game(user.id, user_name, GameMode.PVE, chat_id=chat_id, variant=variant)
    game.player1_chat_id = chat_id

    status = game.get_status_text(for_user_id=user.id)
    keyboard = game.board.to_inline_keyboard(
        timer_text=game.get_elapsed_time_str(), finish_reason=game.finish_reason
    )
    msg = await query.edit_message_text(status, reply_markup=keyboard)
    game.player1_message_id = msg.message_id


async def _handle_checkers_mode_pvp(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create checkers PvP game and generate invite link."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if checkers_manager.has_active_game(user.id) or manager.has_active_game(user.id):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = checkers_manager.create_game(
        user.id, user_name, CheckersMode.PVP, chat_id=chat_id
    )
    game.player1_chat_id = chat_id

    # Invite link
    bot_username = await _get_bot_username(context.bot)
    invite_link = f"https://t.me/{bot_username}?start=join_{game.game_id}"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📨 Отправить приглашение", url=invite_link)],
        ]
    )

    msg = await query.edit_message_text(
        f"👥 *Режим: два игрока в Шашки (PvP)*\n\n"
        f"Вы: ⚪ {user_name}\n"
        f"⏳ Ожидание второго игрока...\n\n"
        f"📨 Отправьте эту ссылку другу:\n"
        f"`{invite_link}`\n\n"
        f"Или нажмите кнопку ниже!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    game.player1_message_id = msg.message_id


async def _handle_checkers_mode_pve(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create checkers PvE game and show board."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if checkers_manager.has_active_game(user.id) or manager.has_active_game(user.id):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = checkers_manager.create_game(
        user.id, user_name, CheckersMode.PVE, chat_id=chat_id
    )
    game.player1_chat_id = chat_id

    status = game.get_status_text(for_user_id=user.id)
    keyboard = game.board.to_inline_keyboard(
        timer_text=game.get_elapsed_time_str(), finish_reason=game.finish_reason
    )
    msg = await query.edit_message_text(status, reply_markup=keyboard)
    game.player1_message_id = msg.message_id


async def _handle_chess_mode_pvp(
    query, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create chess PvP game and generate invite link."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if (
        chess_manager.has_active_game(user.id)
        or manager.has_active_game(user.id)
        or checkers_manager.has_active_game(user.id)
    ):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = chess_manager.create_game(
        user.id, user_name, ChessMode.PVP, chat_id=chat_id
    )
    game.player1_chat_id = chat_id

    bot_username = await _get_bot_username(context.bot)
    invite_link = f"https://t.me/{bot_username}?start=join_{game.game_id}"

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📨 Отправить приглашение", url=invite_link)],
        ]
    )

    msg = await query.edit_message_text(
        f"👥 *Режим: два игрока в Шахматы (PvP)*\n\n"
        f"Вы: ♔ {user_name}\n"
        f"⏳ Ожидание второго игрока...\n\n"
        f"📨 Отправьте эту ссылку другу:\n"
        f"`{invite_link}`\n\n"
        f"Или нажмите кнопку ниже!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    game.player1_message_id = msg.message_id


async def _handle_chess_mode_pve(
    query, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Create chess PvE game and show board."""
    user = query.from_user
    user_name = user.first_name or user.username or f"Player {user.id}"
    chat_id = query.message.chat_id

    if (
        chess_manager.has_active_game(user.id)
        or manager.has_active_game(user.id)
        or checkers_manager.has_active_game(user.id)
    ):
        await query.edit_message_text("⚠️ У вас уже есть активная игра!")
        return

    game = chess_manager.create_game(
        user.id, user_name, ChessMode.PVE, chat_id=chat_id
    )
    game.player1_chat_id = chat_id

    status = game.get_status_text(for_user_id=user.id)
    keyboard = game.board.to_inline_keyboard(
        timer_text=game.get_elapsed_time_str(),
        finish_reason=game.finish_reason,
        flip_board=(user.id == game.player2_id),
        show_hints=getattr(game, "show_hints", True),
    )
    msg = await query.edit_message_text(status, reply_markup=keyboard)
    game.player1_message_id = msg.message_id


async def _handle_cell_click(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a click on a board cell."""
    user = query.from_user
    data = query.data

    # Parse coordinates: cell_R_C
    parts = data.split("_")
    if len(parts) != 3:
        await query.answer()
        return

    try:
        row, col = int(parts[1]), int(parts[2])
    except ValueError:
        await query.answer()
        return

    # Find game for this user
    is_checkers = False
    if query.inline_message_id:
        if query.inline_message_id in checkers_manager.games:
            game = checkers_manager.get_inline_game(query.inline_message_id)
            is_checkers = True
        elif query.inline_message_id in chess_manager.games:
            game = chess_manager.get_inline_game(query.inline_message_id)
            is_checkers = False
        else:
            game = manager.get_inline_game(query.inline_message_id)

        if game.player1_id != user.id and game.player2_id != user.id:
            await query.answer("❌ Вы не участвуете в этой игре!", show_alert=True)
            return
    else:
        game = manager.get_game_by_user(user.id)
        if game is None:
            game = checkers_manager.get_game_by_user(user.id)
            is_checkers = True
        if game is None:
            game = chess_manager.get_game_by_user(user.id)
            is_checkers = False

    if game is None:
        await query.answer("❌ Игра не найдена!", show_alert=True)
        return

    if game.state.name != "PLAYING":
        await query.answer("⛔ Игра не активна!", show_alert=True)
        return

    # Check turn
    if not game.is_players_turn(user.id):
        await query.answer("⏳ Сейчас не ваш ход!", show_alert=True)
        return

    # Process click
    result = game.handle_click(user.id, row, col)

    # Answer callback based on result
    popup_messages = {
        "not_your_turn": "⏳ Сейчас не ваш ход!",
        "not_yours": "❌ Это не ваша шашка!",
        "empty": "❌ Выберите свою шашку",
        "no_moves": "🚫 Нет доступных ходов",
        "invalid": "❌ Недоступный ход",
        "error": "❌ Ошибка",
        "stop": "⛔ Игра не активна",
    }

    try:
        if result in popup_messages:
            await query.answer(popup_messages[result], show_alert=False)
        else:
            await query.answer()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to answer callback query: {e}")

    # Update boards
    if game.is_inline:
        await _update_both_boards(context.bot, game)
    elif game.mode.value == "pvp":
        # Update current player's message_id
        game.set_message_info(user.id, query.message.chat_id, query.message.message_id)

        # Update both boards
        await _update_both_boards(context.bot, game)
    else:
        # PvE: just update current player's board
        status = game.get_status_text(for_user_id=user.id)
        keyboard = game.board.to_inline_keyboard(
            selected=game.selected_piece,
            valid_moves=game.valid_moves,
            game_over=(game.state.name == "FINISHED"),
            timer_text=game.get_elapsed_time_str(),
            finish_reason=game.finish_reason,
            flip_board=(user.id == game.player2_id),
            show_hints=getattr(game, "show_hints", True),
        )
        try:
            await query.edit_message_text(text=status, reply_markup=keyboard)
        except Exception as e:
            logger.warning(f"Edit failed: {e}")

    # ─── AI move (PvE) ──────────────────────────────────────────
    ai_should_move = (
        game.mode.value == "pve"
        and game.state.name == "PLAYING"
        and not game.is_players_turn(user.id)
    )
    if ai_should_move:
        await asyncio.sleep(AI_MOVE_DELAY)

        # Запускаем сложные вычисления ИИ в отдельном потоке,
        # чтобы бот не "зависал" и мог отвечать на другие сообщения!
        ai_result = await asyncio.to_thread(game.make_ai_move)
        logger.info(f"AI move: {ai_result}")

        status = game.get_status_text(for_user_id=user.id)
        keyboard = game.board.to_inline_keyboard(
            game_over=(game.state.name == "FINISHED"),
            timer_text=game.get_elapsed_time_str(),
            finish_reason=game.finish_reason,
            flip_board=(user.id == game.player2_id),
            show_hints=getattr(game, "show_hints", True),
        )
        try:
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=status,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"AI board update failed: {e}")

    # ─── Предложить новую игру, если завершилась ────────────────
    if game.state.name == "FINISHED":
        await _offer_new_game(context, game)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════


async def post_init(application: Application) -> None:
    """Установка меню команд для бота."""
    await application.bot.set_my_commands(
        [
            BotCommand("play", "Начать новую игру"),
            BotCommand("rules", "Правила игры"),
            BotCommand("cancel", "Отменить текущую игру"),
            BotCommand("start", "Перезапустить бота"),
        ]
    )


def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("=" * 60)
        print("  Token not configured!")
        print("  Set BOT_TOKEN in config.py")
        print("=" * 60)
        return

    print("Starting Ugolki bot...")
    print(f"Token: {BOT_TOKEN[:8]}...{BOT_TOKEN[-4:]}")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .post_init(post_init)
        .build()
    )

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    app.add_handler(InlineQueryHandler(handle_inline_query))

    # Callback handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
