"""
Интеграционные юнит-тесты для Telegram-бота.
Используют unittest.mock для симуляции Telegram-объектов.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from telegram import Update, Message, Chat, User, CallbackQuery, InlineQuery
from telegram.ext import ContextTypes

# We need to set the dummy token to avoid the bot exiting on import
import config
config.BOT_TOKEN = "TEST_TOKEN"

import bot

class TestBotHandlers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=111, first_name="TestUser", is_bot=False)
        self.chat = Chat(id=999, type="private")
        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        self.context.bot = MagicMock()
        self.context.bot.edit_message_text = AsyncMock()
        self.context.bot.send_message = AsyncMock()

    def create_mock_update(self, text=""):
        update = MagicMock(spec=Update)
        update.effective_chat = self.chat
        update.effective_user = self.user
        update.message = MagicMock(spec=Message)
        update.message.text = text
        update.message.chat_id = self.chat.id
        update.message.message_id = 1000
        update.message.reply_text = AsyncMock()
        return update

    async def test_cmd_start(self):
        update = self.create_mock_update(text="/start")
        await bot.cmd_start(update, self.context)
        
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Добро пожаловать", args[0])

    async def test_cmd_play(self):
        update = self.create_mock_update(text="/play")
        await bot.cmd_play(update, self.context)
        
        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        self.assertIn("Выберите игру", args[0])

    async def test_toggle_hints_callback(self):
        # 1. Create a game for user 111
        bot.manager.user_games.clear()
        game = bot.manager.create_game(111, "TestUser", bot.GameMode.PVP, chat_id=999)
        game.join(222, "Player2") # Starts the game
        
        # 2. Simulate toggle_hints callback
        update = MagicMock(spec=Update)
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = "toggle_hints"
        update.callback_query.from_user = self.user
        update.callback_query.answer = AsyncMock()
        update.callback_query.message = MagicMock(spec=Message)
        update.callback_query.message.chat_id = 999
        update.callback_query.message.message_id = 1000
        update.callback_query.inline_message_id = None
        
        self.assertTrue(game.show_hints)
        
        await bot.callback_handler(update, self.context)
        
        # Hint should be toggled
        self.assertFalse(game.show_hints)
        
        # Callback should be answered
        update.callback_query.answer.assert_called_once()
        args, kwargs = update.callback_query.answer.call_args
        self.assertIn("ВЫКЛЮЧЕНЫ", args[0])

    async def test_surrender_callback(self):
        bot.manager.user_games.clear()
        game = bot.manager.create_game(111, "TestUser", bot.GameMode.PVP, chat_id=999)
        game.join(222, "Player2")
        
        update = MagicMock(spec=Update)
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = "surrender"
        update.callback_query.from_user = self.user
        update.callback_query.answer = AsyncMock()
        
        await bot.callback_handler(update, self.context)
        
        self.assertEqual(game.state.name, "FINISHED")
        self.assertEqual(game.finish_reason, "surrender")

if __name__ == '__main__':
    unittest.main()
