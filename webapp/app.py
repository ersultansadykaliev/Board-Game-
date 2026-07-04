import os
import sys
import uuid
import sqlite3
import pickle
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# Убеждаемся, что мы можем импортировать модули из родительской папки
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from games.chess.game import Game as ChessGame, ChessMode
from games.checkers.game import Game as CheckersGame, GameMode as CheckersMode
from games.ugolki.game import Game as UgolkiGame, GameMode as UgolkiMode

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS games (game_id TEXT PRIMARY KEY, data BLOB)")
init_db()

def save_game(game):
    with sqlite3.connect(DB_PATH) as conn:
        data = pickle.dumps(game)
        conn.execute("INSERT OR REPLACE INTO games (game_id, data) VALUES (?, ?)", (game.game_id, data))

def load_game(game_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT data FROM games WHERE game_id = ?", (game_id,))
        row = cur.fetchone()
        if row:
            return pickle.loads(row[0])
    return None

def _detect_game_type(game):
    """Определяет тип игры по модулю."""
    module = game.__module__
    if "chess" in module:
        return "chess"
    elif "checkers" in module:
        return "checkers"
    elif "ugolki" in module:
        return "ugolki"
    return "unknown"

@app.route("/")
@app.route("/game/<game_id>")
def index(game_id=None):
    return render_template("index.html")

@app.route("/api/my_games", methods=["GET"])
def my_games():
    """Найти активные (незавершённые) игры пользователя."""
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"status": "ok", "games": []})
    
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        user_id_int = None
    
    active_games = []
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT game_id, data FROM games")
        for row in cur.fetchall():
            try:
                game = pickle.loads(row[1])
                if game.state.name in ("PLAYING", "WAITING"):
                    p1 = getattr(game, 'player1_id', None)
                    p2 = getattr(game, 'player2_id', None)
                    if str(p1) == str(user_id) or p1 == user_id_int or str(p2) == str(user_id) or p2 == user_id_int:
                        game_type = _detect_game_type(game)
                        is_pvp = game.mode.name == "PVP"
                        opponent = ""
                        if is_pvp:
                            if str(p1) == str(user_id) or p1 == user_id_int:
                                opponent = getattr(game, 'player2_name', 'Оппонент') or 'Ожидание...'
                            else:
                                opponent = getattr(game, 'player1_name', 'Оппонент')
                        else:
                            opponent = "Бот ИИ"
                        
                        my_color = "WHITE"
                        if is_pvp and (str(p2) == str(user_id) or p2 == user_id_int):
                            my_color = "BLACK"
                        
                        active_games.append({
                            "game_id": game.game_id,
                            "game_type": game_type,
                            "mode": game.mode.name,
                            "state": game.state.name,
                            "opponent": opponent,
                            "my_color": my_color,
                            "board": _serialize_board(game)
                        })
            except Exception:
                continue
    
    return jsonify({"status": "ok", "games": active_games})

@app.route("/api/delete_game", methods=["POST"])
def delete_game():
    """Удалить игру из базы."""
    data = request.json
    game_id = data.get("game_id")
    if game_id:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
    return jsonify({"status": "ok"})

@app.route("/api/start_game", methods=["POST"])
def start_game():
    data = request.json
    user_id = data.get("user_id", "guest")
    user_name = data.get("user_name", "Игрок")
    game_type = data.get("game_type", "chess")
    
    if game_type == "chess":
        game = ChessGame(f"game_{user_id}", user_id, user_name, ChessMode.PVE)
    elif game_type == "checkers":
        game = CheckersGame(f"game_{user_id}", user_id, user_name, CheckersMode.PVE)
    elif game_type == "ugolki":
        game = UgolkiGame(f"game_{user_id}", user_id, user_name, UgolkiMode.PVE)
    else:
        return jsonify({"status": "error", "message": "Неизвестная игра"}), 400
        
    game.player1_id = user_id
    game.player1_name = user_name
    save_game(game)
    
    return jsonify({
        "status": "ok", 
        "game_id": game.game_id, 
        "board": _serialize_board(game)
    })

@app.route("/api/create_pvp", methods=["POST"])
def create_pvp():
    data = request.json
    user_id = data.get("user_id", "guest")
    user_name = data.get("user_name", "Игрок")
    game_type = data.get("game_type", "chess")
    
    game_id = f"pvp_{uuid.uuid4().hex[:8]}"
    
    if game_type == "chess":
        game = ChessGame(game_id, user_id, "Player 1", ChessMode.PVP)
    elif game_type == "checkers":
        game = CheckersGame(game_id, user_id, "Player 1", CheckersMode.PVP)
    elif game_type == "ugolki":
        game = UgolkiGame(game_id, user_id, "Player 1", UgolkiMode.PVP)
    else:
        return jsonify({"status": "error", "message": "Неизвестная игра"}), 400
        
    game.player1_id = user_id
    game.player1_name = user_name
    game.player2_name = None
    save_game(game)
    
    return jsonify({
        "status": "ok", 
        "game_id": game_id,
        "board": _serialize_board(game)
    })

@app.route("/api/join_pvp", methods=["POST"])
def join_pvp():
    data = request.json
    user_id = data.get("user_id", "guest")
    user_name = data.get("user_name", "Игрок")
    game_id = data.get("game_id")
    
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    if game.state.name != "WAITING":
        if user_id in (game.player1_id, game.player2_id):
            return jsonify({
                "status": "ok",
                "game_type": "chess" if "chess" in game.__module__ else ("checkers" if "checkers" in game.__module__ else "ugolki"),
                "board": _serialize_board(game)
            })
        return jsonify({"status": "error", "message": "Игра уже началась"}), 400
        
    game.join(user_id, user_name)
    game.player2_name = user_name
    save_game(game)
    
    # Для второго игрока оппонент - это player1
    opponent_name = getattr(game, 'player1_name', 'Оппонент')
    
    return jsonify({
        "status": "ok",
        "game_type": "chess" if "chess" in game.__module__ else ("checkers" if "checkers" in game.__module__ else "ugolki"),
        "board": _serialize_board(game),
        "opponent_name": opponent_name
    })

@app.route("/api/state", methods=["GET"])
def get_state():
    game_id = request.args.get("game_id")
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    game_over = game.state.name == "FINISHED"
    reason = game.finish_reason if game_over else ""
    if game_over and game.winner == 0:
        reason = f"Ничья ({reason})"
    elif game_over:
        reason = f"Победитель: {'Белые' if game.winner == 1 else 'Черные'} ({reason})"
        
    # Определяем имя оппонента для запрашивающего
    opponent_name = getattr(game, 'player2_name', None) or getattr(game, 'player1_name', 'Оппонент')
        
    return jsonify({
        "status": "ok",
        "state": game.state.name,
        "board": _serialize_board(game),
        "game_over": game_over,
        "reason": reason,
        "opponent_name": opponent_name
    })

@app.route("/api/click", methods=["POST"])
def click():
    data = request.json
    user_id = data.get("user_id", "guest")
    game_id = data.get("game_id")
    r = data.get("r")
    c = data.get("c")
    
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    if game.state.name == "FINISHED":
        return jsonify({"status": "error", "message": "Игра уже завершена"}), 400

    if game.state.name == "WAITING":
        return jsonify({"status": "error", "message": "Ожидание второго игрока"}), 400

    # Обрабатываем клик пользователя
    result = game.handle_click(user_id, r, c)
    
    # Проверяем, завершилась ли игра
    game_over = game.state.name == "FINISHED"
    reason = game.finish_reason if game_over else ""
    if game_over and game.winner == 0:
        reason = f"Ничья ({reason})"
    elif game_over:
        reason = f"Победитель: {'Белые' if game.winner == 1 else 'Черные'} ({reason})"

    save_game(game)

    return jsonify({
        "status": "ok",
        "result": result,
        "board": _serialize_board(game),
        "selected_piece": game.selected_piece,
        "valid_moves": game.valid_moves,
        "game_over": game_over,
        "reason": reason
    })

@app.route("/api/ai_move", methods=["POST"])
def ai_move():
    data = request.json
    game_id = data.get("game_id")
    
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    if game.state.name == "FINISHED" or game.mode.name != "PVE":
        return jsonify({"status": "error"}), 400

    ai_turn_value = -1 if "chess" in game.__module__ else 2
    if game.current_turn != ai_turn_value:
        return jsonify({"status": "error", "message": "Не ход ИИ"}), 400

    ai_result = game.make_ai_move()
    
    game_over = game.state.name == "FINISHED"
    reason = game.finish_reason if game_over else ""
    if game_over and game.winner == 0:
        reason = f"Ничья ({reason})"
    elif game_over:
        reason = f"Победитель: {'Белые' if game.winner == 1 else 'Черные'} ({reason})"

    save_game(game)

    return jsonify({
        "status": "ok",
        "result": ai_result,
        "board": _serialize_board(game),
        "game_over": game_over,
        "reason": reason
    })

@app.route("/api/surrender", methods=["POST"])
def surrender_api():
    data = request.json
    user_id = data.get("user_id", "guest")
    game_id = data.get("game_id")
    
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    # PythonAnywhere uses python 3.10, so we can use duck typing
    if hasattr(game, "surrender"):
        # For simplicity, pass user_id (surrender expects int typically, but let's try to pass the raw string if needed, or convert)
        try:
            uid = int(user_id)
        except:
            uid = user_id
        game.surrender(uid)
        save_game(game)
        
    return jsonify({"status": "ok"})

@app.route("/api/draw", methods=["POST"])
def draw_api():
    data = request.json
    game_id = data.get("game_id")
    
    game = load_game(game_id)
    if not game:
        return jsonify({"status": "error", "message": "Игра не найдена"}), 404
        
    if "chess" in game.__module__:
        from games.chess.game import GameState
        game.state = GameState.FINISHED
    elif "checkers" in game.__module__:
        from games.checkers.game import GameState
        game.state = GameState.FINISHED
    elif "ugolki" in game.__module__:
        from games.ugolki.game import GameState
        game.state = GameState.FINISHED
        
    game.winner = 0
    game.finish_reason = "Ничья по согласию"
    save_game(game)
    
    return jsonify({"status": "ok"})

def _serialize_board(game):
    board_state = []
    game_module = game.__module__
    
    for r in range(8):
        row = []
        for c in range(8):
            piece = game.board.get_piece(r, c)
            if piece != 0:
                type_name = ""
                color = ""
                if "chess" in game_module:
                    color = "WHITE" if piece > 0 else "BLACK"
                    pt = abs(piece)
                    if pt == 1: type_name = "PAWN"
                    elif pt == 2: type_name = "ROOK"
                    elif pt == 3: type_name = "KNIGHT"
                    elif pt == 4: type_name = "BISHOP"
                    elif pt == 5: type_name = "QUEEN"
                    elif pt == 6: type_name = "KING"
                elif "checkers" in game_module:
                    if piece == 1: color, type_name = "WHITE", "MAN"
                    elif piece == 2: color, type_name = "BLACK", "MAN"
                    elif piece == 3: color, type_name = "WHITE", "KING"
                    elif piece == 4: color, type_name = "BLACK", "KING"
                elif "ugolki" in game_module:
                    if piece == 1: color, type_name = "WHITE", "UGOLKI_MAN"
                    elif piece == 2: color, type_name = "BLACK", "UGOLKI_MAN"
                
                row.append({
                    "type": type_name,
                    "color": color
                })
            else:
                row.append(None)
        board_state.append(row)
        
    return {
        "grid": board_state,
        "turn": "WHITE" if game.current_turn == 1 else "BLACK"
    }

if __name__ == "__main__":
    app.run(debug=True, port=5000)
