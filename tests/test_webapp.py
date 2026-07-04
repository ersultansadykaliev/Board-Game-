import unittest
import json
import os
import sys

# Добавляем корневую директорию в пути поиска модулей
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import webapp.app
# Переопределяем путь к БД для тестов, чтобы не влиять на продакшн базу
webapp.app.DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_games.db")

from webapp.app import app, init_db

class TestWebAppAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Инициализируем тестовую БД
        init_db()
        app.config['TESTING'] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        # Освобождаем все ссылки и удаляем тестовую БД
        import gc
        gc.collect()
        if os.path.exists(webapp.app.DB_PATH):
            try:
                os.remove(webapp.app.DB_PATH)
            except Exception as e:
                pass

    def test_index_route(self):
        """Проверяет работоспособность главной страницы."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_pve_chess_flow(self):
        """Тест полного цикла PVE игры в шахматы."""
        # 1. Создание игры
        res = self.client.post("/api/start_game", json={
            "user_id": "test_user_pve_chess",
            "user_name": "TestPveChess",
            "game_type": "chess"
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        game_id = data["game_id"]
        
        # 2. Клик на фигуру (выбор белой пешки e2 - row 6, col 4)
        res = self.client.post("/api/click", json={
            "user_id": "test_user_pve_chess",
            "game_id": game_id,
            "r": 6,
            "c": 4
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["result"], "selected")
        
        # 3. Клик для совершения хода (ход e2-e4 - row 4, col 4)
        res = self.client.post("/api/click", json={
            "user_id": "test_user_pve_chess",
            "game_id": game_id,
            "r": 4,
            "c": 4
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["result"], "move")
        
        # 4. Ход ИИ (черные делают ход)
        res = self.client.post("/api/ai_move", json={"game_id": game_id})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        
        # 5. Получение состояния
        res = self.client.get(f"/api/state?game_id={game_id}")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["state"], "PLAYING")
        
        # 6. Удаление игры
        res = self.client.post("/api/delete_game", json={"game_id": game_id})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")

    def test_pve_checkers_flow(self):
        """Тест создания и удаления игры PVE шашек."""
        res = self.client.post("/api/start_game", json={
            "user_id": "test_user_pve_checkers",
            "user_name": "TestPveCheckers",
            "game_type": "checkers"
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        game_id = data["game_id"]
        
        # Удаляем
        res = self.client.post("/api/delete_game", json={"game_id": game_id})
        self.assertEqual(res.status_code, 200)

    def test_pvp_game_flow(self):
        """Тест полного цикла PVP игры (создание, ожидание, джоин, переподключение, сдача)."""
        p1_id = "11111"
        p2_id = "22222"
        
        # 1. Создатель создает игру PVP
        res = self.client.post("/api/create_pvp", json={
            "user_id": p1_id,
            "user_name": "Player 1",
            "game_type": "chess"
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        game_id = data["game_id"]
        
        # 2. Проверяем список игр для Player 1
        res = self.client.get(f"/api/my_games?user_id={p1_id}")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(len(data["games"]), 1)
        self.assertEqual(data["games"][0]["opponent"], "Ожидание...")
        self.assertEqual(data["games"][0]["my_color"], "WHITE")
        self.assertEqual(data["games"][0]["state"], "WAITING")
        
        # 3. Создатель повторно открывает инвайт-ссылку (переподключается)
        res = self.client.post("/api/join_pvp", json={
            "user_id": p1_id,
            "user_name": "Player 1",
            "game_id": game_id
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["my_color"], "WHITE")
        self.assertEqual(data["state"], "WAITING")
        
        # 4. Второй игрок подключается
        res = self.client.post("/api/join_pvp", json={
            "user_id": p2_id,
            "user_name": "Player 2",
            "game_id": game_id
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["my_color"], "BLACK")
        self.assertEqual(data["state"], "PLAYING")
        self.assertEqual(data["opponent_name"], "Player 1")
        
        # 5. Проверяем список игр для Player 1 (должен видеть имя соперника)
        res = self.client.get(f"/api/my_games?user_id={p1_id}")
        data = json.loads(res.data)
        self.assertEqual(data["games"][0]["opponent"], "Player 2")
        self.assertEqual(data["games"][0]["state"], "PLAYING")
        
        # 6. Проверяем список игр для Player 2
        res = self.client.get(f"/api/my_games?user_id={p2_id}")
        data = json.loads(res.data)
        self.assertEqual(data["games"][0]["opponent"], "Player 1")
        self.assertEqual(data["games"][0]["my_color"], "BLACK")
        
        # 7. Player 1 сдается
        res = self.client.post("/api/surrender", json={
            "user_id": p1_id,
            "game_id": game_id
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "ok")
        
        # Проверяем состояние — должно быть завершено
        res = self.client.get(f"/api/state?game_id={game_id}")
        data = json.loads(res.data)
        self.assertEqual(data["state"], "FINISHED")
        self.assertTrue(data["game_over"])
        
        # 8. Чистим за собой
        res = self.client.post("/api/delete_game", json={"game_id": game_id})
        self.assertEqual(res.status_code, 200)

    def test_ugolki_variants(self):
        """Тест создания уголков с различными расстановками (вариантами)."""
        variants_to_test = {
            "classic": 12,  # 12 фишек у каждого
            "square": 9,    # Квадрат 3х3 = 9 фишек
            "triangle": 10  # Треугольник = 10 фишек
        }
        
        for variant, piece_count in variants_to_test.items():
            res = self.client.post("/api/start_game", json={
                "user_id": f"test_ugolki_{variant}",
                "user_name": "UgolkiTester",
                "game_type": "ugolki",
                "variant": variant
            })
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertEqual(data["status"], "ok")
            
            # Подсчитываем количество фишек на полученной доске
            grid = data["board"]["grid"]
            white_count = 0
            black_count = 0
            for row in grid:
                for cell in row:
                    if cell and cell["type"] == "UGOLKI_MAN":
                        if cell["color"] == "WHITE":
                            white_count += 1
                        elif cell["color"] == "BLACK":
                            black_count += 1
            
            self.assertEqual(white_count, piece_count, f"Неверное число фишек для белых в варианте {variant}")
            self.assertEqual(black_count, piece_count, f"Неверное число фишек для черных в варианте {variant}")
            
            # Удаляем игру
            self.client.post("/api/delete_game", json={"game_id": data["game_id"]})

if __name__ == "__main__":
    unittest.main()
