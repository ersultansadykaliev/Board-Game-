let tg = window.Telegram.WebApp;
tg.expand();

// Настраиваем цвета под тему
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color);
document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color);
document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color);
document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color);

const user_id = tg.initDataUnsafe?.user?.id || Math.floor(Math.random() * 1000000);
const user_name = tg.initDataUnsafe?.user?.first_name || "Гость";
document.getElementById('user-name').textContent = user_name;

const PIECE_SYMBOLS = {
    'PAWN_WHITE': '♟\uFE0E', 'ROOK_WHITE': '♜\uFE0E', 'KNIGHT_WHITE': '♞\uFE0E', 'BISHOP_WHITE': '♝\uFE0E', 'QUEEN_WHITE': '♛\uFE0E', 'KING_WHITE': '♚\uFE0E',
    'PAWN_BLACK': '♟\uFE0E', 'ROOK_BLACK': '♜\uFE0E', 'KNIGHT_BLACK': '♞\uFE0E', 'BISHOP_BLACK': '♝\uFE0E', 'QUEEN_BLACK': '♛\uFE0E', 'KING_BLACK': '♚\uFE0E',
    'MAN_WHITE': '⚪', 'KING_WHITE_CHECKERS': '♔', 'MAN_BLACK': '⚫', 'KING_BLACK_CHECKERS': '♚',
    'UGOLKI_MAN_WHITE': '▲', 'UGOLKI_MAN_BLACK': '▼'
};

let boardState = null;
let currentTurn = 'WHITE';
let selectedPiece = null;
let validMoves = [];
let isWaitingForServer = false;
let currentGameType = 'chess';
let currentGameId = null;
let isMyTurn = true;
let pollInterval = null;
let gameMode = 'PVE';
let myColor = 'WHITE'; // В PVE мы всегда белые. В PVP создатель - белые, второй - черные

// Проверяем, не перешли ли мы по ссылке с инвайтом
let startParam = tg.initDataUnsafe?.start_param;
if (!startParam) {
    // Резервный вариант для локального тестирования в браузере
    const urlParams = new URLSearchParams(window.location.search);
    startParam = urlParams.get('start_param');
}
// Добавляем проверку пути на случай, если Telegram обрежет query-параметры
if (!startParam) {
    const match = window.location.pathname.match(/\/game\/(pvp_[a-zA-Z0-9]+)/);
    if (match) {
        startParam = match[1];
    }
}

if (startParam && startParam.startsWith('pvp_')) {
    joinGame(startParam); // startParam уже содержит полный game_id вида pvp_xxxxx
} else {
    // Проверяем незавершённые игры при обычном запуске
    checkActiveGames();
}

async function joinGame(gameId) {
    document.getElementById('game-menu').style.display = 'none';
    setStatus("Подключение к игре...");
    
    try {
        const response = await fetch('/api/join_pvp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user_id, user_name: user_name, game_id: gameId })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            currentGameId = gameId;
            currentGameType = data.game_type;
            gameMode = 'PVP';
            myColor = data.my_color || 'BLACK';
            
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            if (data.state === 'WAITING') {
                showInviteScreen(gameId);
                startPolling();
                return;
            }
            
            document.getElementById('opponent-name').textContent = data.opponent_name || "Оппонент";
            document.getElementById('opponent-avatar').textContent = "👤";
            document.getElementById('game-area').style.display = 'flex';
            
            renderBoard();
            updateTurnStatus();
            startPolling();
        } else {
            alert("Не удалось подключиться: " + data.message);
            document.getElementById('game-menu').style.display = 'flex';
        }
    } catch (e) {
        alert("Ошибка сети");
    }
}

async function checkActiveGames() {
    try {
        const response = await fetch(`/api/my_games?user_id=${user_id}`);
        const data = await response.json();
        
        const section = document.getElementById('my-games-section');
        
        if (data.status === 'ok' && data.games.length > 0) {
            section.style.display = 'block';
            section.innerHTML = '<h2 class="game-title" style="justify-content: center; margin-bottom: 15px;">🎮 Мои активные игры</h2>';
            
            const gameNames = { chess: 'Шахматы', checkers: 'Шашки', ugolki: 'Уголки' };
            
            data.games.forEach(game => {
                let gameName = gameNames[game.game_type] || game.game_type;
                if (game.game_type === 'ugolki' && game.variant) {
                    const variantNames = { classic: 'Классика (3x4)', square: 'Квадрат (3x3)', triangle: 'Треугольник' };
                    const varName = variantNames[game.variant] || game.variant;
                    gameName += ` (${varName})`;
                }
                const modeText = game.mode === 'PVP' ? `против ${game.opponent}` : 'против Бота ИИ';
                
                const card = document.createElement('div');
                card.className = 'game-card';
                card.style.marginBottom = '10px';
                card.innerHTML = `
                    <p style="opacity: 0.9; margin: 0 0 10px 0; color: #fff; font-size: 16px; font-weight: bold;">${gameName}</p>
                    <p style="opacity: 0.7; margin: 0 0 15px 0; color: #fff; font-size: 14px;">${modeText}</p>
                    <div class="game-actions" style="gap: 10px;">
                        <button class="btn-ai" style="flex: 1; padding: 10px; font-size: 14px;" onclick="resumeGame('${game.game_id}', '${game.game_type}', '${game.mode}', '${game.my_color}')">▶️ Продолжить</button>
                        <button class="btn-friend" style="padding: 10px; font-size: 14px; background: rgba(255,82,82,0.2); border: 1px solid #ff5252;" onclick="dismissResume('${game.game_id}')">🗑</button>
                    </div>
                `;
                section.appendChild(card);
            });
        } else {
            section.style.display = 'none';
            section.innerHTML = '';
        }
    } catch (e) {
        console.error('Ошибка проверки активных игр', e);
    }
}

async function resumeGame(gameId, gameType, mode, color) {
    document.getElementById('game-menu').style.display = 'none';
    
    currentGameId = gameId;
    currentGameType = gameType;
    gameMode = mode;
    myColor = color;
    
    try {
        const response = await fetch(`/api/state?game_id=${gameId}`);
        const data = await response.json();
        if (data.status === 'ok') {
            if (data.state === 'WAITING') {
                showInviteScreen(gameId);
                if (mode === 'PVP') {
                    startPolling();
                }
                return;
            }
            
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            const opponentName = data.opponent_name || 'Оппонент';
            document.getElementById('opponent-name').textContent = mode === 'PVE' ? 'Бот ИИ' : opponentName;
            document.getElementById('opponent-avatar').textContent = mode === 'PVE' ? '🤖' : '👤';
            document.getElementById('game-area').style.display = 'flex';
            
            renderBoard();
            updateTurnStatus();
            
            if (mode === 'PVP') {
                startPolling();
            }
        }
    } catch (e) {
        alert('Ошибка загрузки игры');
    }
}

async function dismissResume(gameId) {
    if (!confirm("Вы уверены, что хотите удалить эту игру?")) return;
    try {
        await fetch('/api/delete_game', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: gameId })
        });
        checkActiveGames(); // Перерисовываем список
    } catch (e) {
        console.error(e);
    }
}

async function initGame(gameType = 'chess', mode = 'PVE', variant = 'classic') {
    currentGameType = gameType;
    gameMode = mode;
    myColor = 'WHITE';
    document.getElementById('game-menu').style.display = 'none';
    
    try {
        const endpoint = mode === 'PVE' ? '/api/start_game' : '/api/create_pvp';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user_id, user_name: user_name, game_type: gameType, variant: variant })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            currentGameId = data.game_id;
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            if (mode === 'PVP') {
                document.getElementById('opponent-name').textContent = "Оппонент";
                document.getElementById('opponent-avatar').textContent = "👤";
                showInviteScreen(currentGameId);
                startPolling(); // Начинаем проверять, не подключился ли второй
            } else {
                document.getElementById('opponent-name').textContent = "Бот ИИ";
                document.getElementById('opponent-avatar').textContent = "🤖";
                document.getElementById('game-area').style.display = 'flex';
                renderBoard();
                updateTurnStatus();
            }
        }
    } catch (e) {
        alert("Ошибка сети");
    }
}

function showInviteScreen(gameId) {
    document.getElementById('waiting-screen').style.display = 'block';
    // Используем deep link через бота — так Mini App откроется ВНУТРИ Telegram
    const link = `https://t.me/Boardgames_1bot?start=${gameId}`;
    document.getElementById('invite-link').innerText = link;
}

function copyInviteLink() {
    const link = document.getElementById('invite-link').innerText;
    navigator.clipboard.writeText(link).then(() => {
        tg.showAlert("Ссылка скопирована! Отправьте её другу в Telegram.");
    });
}

function shareInviteLink() {
    const link = document.getElementById('invite-link').innerText;
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent('Давай сыграем партию в настольные игры!')}`;
    tg.openTelegramLink(shareUrl);
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchState, 1500);
}

async function fetchState() {
    if (isWaitingForServer) return; // Не спамим, если уже ждем клик
    try {
        const response = await fetch(`/api/state?game_id=${currentGameId}`);
        const data = await response.json();
        if (data.status === 'ok') {
            if (data.state === 'PLAYING' && document.getElementById('waiting-screen').style.display === 'block') {
                // Второй игрок подключился
                document.getElementById('waiting-screen').style.display = 'none';
                document.getElementById('game-area').style.display = 'flex';
                if (data.opponent_name) {
                    document.getElementById('opponent-name').textContent = data.opponent_name;
                }
                tg.HapticFeedback.notificationOccurred('success');
            }
            
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            if (document.getElementById('game-area').style.display === 'flex') {
                renderBoard();
                updateTurnStatus();
                
                if (data.game_over) {
                    clearInterval(pollInterval);
                    setStatus(`Игра окончена! ${data.reason}`);
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function updateTurnStatus() {
    isMyTurn = (currentTurn === myColor);
    if (isMyTurn) {
        setStatus("Ваш ход!");
    } else {
        setStatus("Ожидание хода противника...");
    }
}

function renderBoard() {
    if (!boardState) return;
    const boardDiv = document.getElementById('board');
    boardDiv.innerHTML = '';
    
    // Если мы играем за черных, переворачиваем доску визуально
    const isFlipped = myColor === 'BLACK';
    
    for (let i = 0; i < 8; i++) {
        let r = isFlipped ? 7 - i : i;
        for (let j = 0; j < 8; j++) {
            let c = isFlipped ? 7 - j : j;
            
            const cellDiv = document.createElement('div');
            const isLight = (r + c) % 2 === 0;
            cellDiv.className = `cell ${isLight ? 'light' : 'dark'}`;
            
            if (selectedPiece && selectedPiece[0] === r && selectedPiece[1] === c) {
                cellDiv.classList.add('selected');
            }
            
            if (validMoves.some(m => m[0] === r && m[1] === c)) {
                cellDiv.classList.add('highlight');
            }
            
            cellDiv.onclick = () => handleCellClick(r, c);
            
            const piece = boardState[r][c];
            if (piece) {
                const pieceDiv = document.createElement('div');
                pieceDiv.className = 'piece';
                pieceDiv.dataset.color = piece.color;
                
                const symbolKey = `${piece.type}_${piece.color}`;
                pieceDiv.innerText = PIECE_SYMBOLS[symbolKey] || '';
                
                cellDiv.appendChild(pieceDiv);
            }
            
            boardDiv.appendChild(cellDiv);
        }
    }
}

async function handleCellClick(r, c) {
    if (isWaitingForServer) return;
    if (gameMode === 'PVP' && !isMyTurn) {
        tg.HapticFeedback.notificationOccurred('error');
        return; // Игнорируем клики не в свой ход
    }
    
    isWaitingForServer = true;
    
    try {
        const response = await fetch('/api/click', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user_id, game_id: currentGameId, r: r, c: c })
        });
        const data = await response.json();
        
        if (data.status === 'ok') {
            selectedPiece = data.selected_piece;
            validMoves = data.valid_moves;
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            if (data.result === 'selected') {
                tg.HapticFeedback.selectionChanged();
            } else if (data.result === 'moved' || data.result === 'capture') {
                tg.HapticFeedback.impactOccurred('light');
            }
            
            renderBoard();
            updateTurnStatus();
            
            if (data.game_over) {
                if (pollInterval) clearInterval(pollInterval);
                setStatus(`Игра окончена! ${data.reason}`);
                tg.HapticFeedback.notificationOccurred('success');
            } else if (gameMode === 'PVE' && !isMyTurn) {
                // Если сейчас ход ИИ, запрашиваем его ход с задержкой для анимации
                setTimeout(makeAiMove, 600);
            }
        } else {
            tg.HapticFeedback.notificationOccurred('error');
            setStatus("Ошибка: " + data.message);
        }
    } catch (e) {
        setStatus("Ошибка сети");
    } finally {
        isWaitingForServer = false;
    }
}

async function makeAiMove() {
    isWaitingForServer = true;
    try {
        const response = await fetch('/api/ai_move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: currentGameId })
        });
        const data = await response.json();
        
        if (data.status === 'ok') {
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            tg.HapticFeedback.impactOccurred('medium');
            
            renderBoard();
            updateTurnStatus();
            
            if (data.game_over) {
                if (pollInterval) clearInterval(pollInterval);
                setStatus(`Игра окончена! ${data.reason}`);
                tg.HapticFeedback.notificationOccurred('success');
            }
        }
    } catch (e) {
        console.error("Ошибка при ходе ИИ", e);
    } finally {
        isWaitingForServer = false;
    }
}

function setStatus(text) {
    document.getElementById('status-message').textContent = text;
}

async function surrenderGame() {
    if (!confirm("Вы уверены, что хотите сдаться?")) return;
    
    try {
        const response = await fetch('/api/surrender', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: currentGameId, user_id: user_id })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            setStatus("Вы сдались.");
            // State poll will pick up the game_over flag automatically
        }
    } catch (e) {
        alert("Ошибка сети");
    }
}

async function offerDraw() {
    if (!confirm("Предложить ничью (пока завершает игру мгновенно)?")) return;
    
    try {
        const response = await fetch('/api/draw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: currentGameId })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            setStatus("Ничья.");
        }
    } catch (e) {
        alert("Ошибка сети");
    }
}

function exitToMenu() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    document.getElementById('game-area').style.display = 'none';
    document.getElementById('game-menu').style.display = 'flex';
    // Проверим активные игры снова, чтобы показать баннер
    checkActiveGames();
}
