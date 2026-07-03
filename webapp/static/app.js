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
    'MAN_WHITE': '⚪', 'KING_WHITE': '♔', 'MAN_BLACK': '⚫', 'KING_BLACK': '♚'
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

if (startParam && startParam.startsWith('pvp_')) {
    joinGame(startParam);
}

async function joinGame(gameId) {
    document.getElementById('game-menu').style.display = 'none';
    setStatus("Подключение к игре...");
    
    try {
        const response = await fetch('/api/join_pvp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user_id, game_id: gameId })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            currentGameId = gameId;
            currentGameType = data.game_type;
            gameMode = 'PVP';
            myColor = 'BLACK'; // Второй игрок
            
            boardState = data.board.grid;
            currentTurn = data.board.turn;
            
            document.getElementById('opponent-name').textContent = "Оппонент";
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

async function initGame(gameType = 'chess', mode = 'PVE') {
    currentGameType = gameType;
    gameMode = mode;
    myColor = 'WHITE';
    document.getElementById('game-menu').style.display = 'none';
    
    try {
        const endpoint = mode === 'PVE' ? '/api/start_game' : '/api/create_pvp';
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user_id, game_type: gameType })
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
    // Используем прямую ссылку на сайт, чтобы работало у всех без настройки t.me
    const link = `https://Ersultan000.pythonanywhere.com/?start_param=pvp_${gameId}`;
    document.getElementById('invite-link').innerText = link;
}

function copyInviteLink() {
    const link = document.getElementById('invite-link').innerText;
    navigator.clipboard.writeText(link).then(() => {
        tg.showAlert("Ссылка скопирована! Отправьте её другу в Telegram.");
    });
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
