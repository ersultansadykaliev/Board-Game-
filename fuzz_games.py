import random
import traceback
import sys
from games.ugolki.game import Game as UgolkiGame, GameMode as UgolkiMode
from games.checkers.game import Game as CheckersGame, GameMode as CheckersMode
from games.chess.game import Game as ChessGame, ChessMode

def fuzz_game(game_class, game_mode, num_actions=10000):
    game = game_class(game_id="test", player1_id=1, player1_name="Player 1", mode=game_mode.PVP)
    game.join(player2_id=2, player2_name="Player 2")
    
    actions = ["click", "surrender", "hints"]
    users = [1, 2, 3] # 3 - "левый" пользователь (зритель)
    
    print(f"--- Fuzzing {game_class.__name__} ({num_actions} случайных действий) ---")
    
    success_actions = 0
    
    for i in range(num_actions):
        if game.state.name == "FINISHED":
            # Перезапускаем игру, если кто-то выиграл или сдался
            game = game_class(game_id="test", player1_id=1, player1_name="Player 1", mode=game_mode.PVP)
            game.join(player2_id=2, player2_name="Player 2")
            
        action = random.choices(actions, weights=[90, 5, 5])[0]
        user_id = random.choice(users)
        
        try:
            if action == "click":
                r = random.randint(-2, 10)  # Специально генерируем индексы вне доски (ошибки границ)
                c = random.randint(-2, 10)
                if game.is_participant(user_id) and game.is_players_turn(user_id):
                    game.handle_click(user_id, r, c)
            elif action == "surrender":
                if game.is_participant(user_id):
                    game.surrender(user_id)
            elif action == "hints":
                pass # В будущем можно добавить
                
            success_actions += 1
        except Exception as e:
            print(f"\n[CRASH] Ошибка в {game_class.__name__} на действии {action} от пользователя {user_id}:")
            print(f"Координаты: r={r}, c={c}" if action == "click" else "")
            traceback.print_exc()
            sys.exit(1)
            
    print(f"Успешно обработано: {success_actions}/{num_actions} действий. Сбоев нет!\n")


if __name__ == "__main__":
    print("Начинаем хаотичный стресс-тест всех игр (Fuzzing)...\n")
    
    fuzz_game(UgolkiGame, UgolkiMode, 20000)
    fuzz_game(CheckersGame, CheckersMode, 20000)
    fuzz_game(ChessGame, ChessMode, 20000)
    
    print("🎉 Все игры выдержали стресс-тест! Ни один неверный клик не сломал бота.")
