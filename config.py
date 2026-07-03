"""
Конфигурация бота «Уголки»
"""

import os

# Загружаем переменные из .env файла (если он есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("UGOLKI_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("ВНИМАНИЕ: Токен бота не найден! Убедитесь, что переменная UGOLKI_BOT_TOKEN задана.")

# ─── Настройки игры ─────────────────────────────────────────────
BOARD_SIZE = 8
MAX_MOVES_PER_PLAYER = 40  # Лимит ходов на каждого игрока (всего 80)

# ─── Вариации расстановки ───────────────────────────────────────
UGOLKI_VARIANTS = {
    "classic": {
        "name": "Классика (3x4)",
        "start1": [
            (0, 0), (0, 1), (0, 2), (0, 3),
            (1, 0), (1, 1), (1, 2), (1, 3),
            (2, 0), (2, 1), (2, 2), (2, 3),
        ],
        "start2": [
            (7, 7), (7, 6), (7, 5), (7, 4),
            (6, 7), (6, 6), (6, 5), (6, 4),
            (5, 7), (5, 6), (5, 5), (5, 4),
        ],
    },
    "square": {
        "name": "Квадрат 3x3",
        "start1": [(r, c) for r in range(3) for c in range(3)],
        "start2": [(r, c) for r in range(5, 8) for c in range(5, 8)],
    },
    "triangle": {
        "name": "Треугольник",
        "start1": [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (3, 0)],
        "start2": [(7, 7), (7, 6), (7, 5), (7, 4), (6, 7), (6, 6), (6, 5), (5, 7), (5, 6), (4, 7)],
    }
}

for var in UGOLKI_VARIANTS.values():
    var["home1"] = var["start2"]
    var["home2"] = var["start1"]

# Для обратной совместимости некоторых частей, оставляем классику по умолчанию
PLAYER1_START = UGOLKI_VARIANTS["classic"]["start1"]
PLAYER2_START = UGOLKI_VARIANTS["classic"]["start2"]
PLAYER1_HOME = UGOLKI_VARIANTS["classic"]["home1"]
PLAYER2_HOME = UGOLKI_VARIANTS["classic"]["home2"].copy()  # Игрок 2 должен занять позиции игрока 1

# ─── Эмодзи ─────────────────────────────────────────────────────
EMOJI_PLAYER1 = "⚪"  # Шашка игрока 1
EMOJI_PLAYER2 = "⚫"  # Шашка игрока 2
EMOJI_SELECTED = "🟡"  # Выбранная шашка
EMOJI_VALID_MOVE = "🟢"  # Доступный ход
EMOJI_EMPTY_LIGHT = "·"  # Пустая клетка (светлая)
EMOJI_EMPTY_DARK = "·"  # Пустая клетка (тёмная)
EMOJI_HOME1_EMPTY = "◎"  # Пустая клетка в доме игрока 1 (цель белых)
EMOJI_HOME2_EMPTY = "◉"  # Пустая клетка в доме игрока 2 (цель черных)

# ─── Направления ходов (4 направления — классика) ─────────────────
DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

# ─── Лимит вывода шашек из дома ──────────────────────────────────
HOME_CLEAR_LIMIT = 40  # К этому ходу все фишки должны покинуть свой дом

# ─── Запрет зеркальной стратегии ─────────────────────────────────
MIRROR_MAX_COPIES = 10  # Максимум зеркальных ходов чёрных
MIRROR_CHECK_MOVES = 12  # Из первых N ходов белых

# ─── Стартовые позиции как frozenset (для быстрой проверки) ───────
PLAYER1_START_SET = frozenset(PLAYER1_START)
PLAYER2_START_SET = frozenset(PLAYER2_START)

# ─── Задержка хода ИИ (секунды) ─────────────────────────────────
AI_MOVE_DELAY = 0.8
