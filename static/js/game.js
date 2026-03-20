const socket = io();
const bootstrapData = window.BREAK_THE_CODE_BOOTSTRAP || {};
const roomId = bootstrapData.roomId;
let gameState = {
    playerData: null,
    availableQuestions: [],
    otherPlayers: [],
    currentTurn: null,
    playerCount: 0,
    selectedQuestionIndex: null,
    yourPlayerId: null,
    allPlayers: [],
    isHost: false,
    isReady: false,
    finalRound: false,
    finalRoundPlayer: null
};

// Reorder functionality variables
let reorderMode = false;
let originalPlayerOrder = [];
let currentPlayerOrder = [];

// Timer functionality variables
let timerInterval = null;
let currentTimeLimit = null;
let turnStartTime = null;
let statusTimeout = null;

function setWaitingPanel(panelName) {
    document.querySelectorAll('[data-waiting-panel-target]').forEach(button => {
        button.classList.toggle('is-active', button.dataset.waitingPanelTarget === panelName);
    });

    document.querySelectorAll('[data-waiting-panel]').forEach(panel => {
        panel.classList.toggle('is-active', panel.dataset.waitingPanel === panelName);
    });
}

function setGamePanel(panelName) {
    document.querySelectorAll('[data-game-panel-target]').forEach(button => {
        button.classList.toggle('is-active', button.dataset.gamePanelTarget === panelName);
    });

    document.querySelectorAll('[data-game-panel]').forEach(panel => {
        panel.classList.toggle('is-active', panel.dataset.gamePanel === panelName);
    });
}

function openJoinSheet(message = 'Pick a player name to enter the room.', suggestedName = '') {
    const joinSheet = document.getElementById('roomJoinSheet');
    const messageElement = document.getElementById('joinSheetMessage');
    const input = document.getElementById('directJoinName');

    if (!joinSheet || !messageElement || !input) {
        return;
    }

    messageElement.textContent = message;
    input.value = suggestedName || input.value || '';
    joinSheet.style.display = 'flex';

    window.setTimeout(() => {
        input.focus();
        input.select();
    }, 30);
}

function hideJoinSheet() {
    const joinSheet = document.getElementById('roomJoinSheet');
    if (joinSheet) {
        joinSheet.style.display = 'none';
    }
}

function submitDirectJoin() {
    const input = document.getElementById('directJoinName');
    if (!input) {
        return;
    }

    const playerName = input.value.trim();
    if (!playerName) {
        showStatus('Enter a player name before joining.', 'error');
        input.focus();
        return;
    }

    socket.emit('join_room', {
        room_id: roomId,
        player_name: playerName
    });
}

function createPlayerBadge(label, className) {
    return `<span class="player-pill ${className}">${label}</span>`;
}

function canHostRemovePlayer(player) {
    const waitingRoomVisible = document.getElementById('waitingRoom').style.display !== 'none';
    return (
        waitingRoomVisible &&
        gameState.isHost &&
        !reorderMode &&
        player &&
        player.id &&
        player.id !== gameState.yourPlayerId
    );
}

function requestPlayerRemoval(playerId, playerName) {
    if (!gameState.isHost || !playerId) {
        return;
    }

    const confirmed = window.confirm(`Remove ${playerName} from this room?`);
    if (!confirmed) {
        return;
    }

    socket.emit('remove_player', { target_player_id: playerId });
}

function createPlayerItem(player) {
    const playerDiv = document.createElement('div');
    playerDiv.className = 'player-item';
    playerDiv.dataset.playerId = player.id;
    playerDiv.dataset.playerName = player.name;
    playerDiv.dataset.playerReady = player.ready ? 'true' : 'false';
    playerDiv.dataset.playerConnected = player.connected === false ? 'false' : 'true';
    playerDiv.dataset.playerScore = String(player.score || 0);

    if (player.ready) {
        playerDiv.classList.add('is-ready');
    }

    if (player.connected === false) {
        playerDiv.classList.add('is-disconnected');
    }

    const badges = [
        createPlayerBadge(`${player.score || 0} pts`, 'score'),
        createPlayerBadge(player.ready ? 'Ready' : 'Waiting', player.ready ? 'ready' : 'pending'),
        createPlayerBadge(player.connected === false ? 'Offline' : 'Connected', player.connected === false ? 'offline' : 'online')
    ];

    playerDiv.innerHTML = `
        <div class="player-item-main">
            <span class="player-name">${player.name}</span>
            <div class="player-pills">${badges.join('')}</div>
        </div>
    `;

    if (canHostRemovePlayer(player)) {
        const actionStrip = document.createElement('div');
        actionStrip.className = 'player-action-strip';

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'player-remove-btn';
        removeButton.textContent = 'Remove';
        removeButton.setAttribute('aria-label', `Remove ${player.name} from the room`);
        removeButton.addEventListener('click', event => {
            event.stopPropagation();
            requestPlayerRemoval(player.id, player.name);
        });

        actionStrip.appendChild(removeButton);
        playerDiv.appendChild(actionStrip);
    }

    return playerDiv;
}

function getStoredPlayerData() {
    const rawData = localStorage.getItem(`playerData_${roomId}`);
    if (!rawData) {
        return null;
    }

    try {
        return JSON.parse(rawData);
    } catch (error) {
        console.log('Error parsing stored player data:', error);
        localStorage.removeItem(`playerData_${roomId}`);
        return null;
    }
}

function getKnownPlayerId() {
    if (gameState.yourPlayerId) {
        return gameState.yourPlayerId;
    }

    const storedData = getStoredPlayerData();
    if (storedData && storedData.player_id) {
        return storedData.player_id;
    }

    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('player_id');
}

function getAllPlayersReady(players, count = 0) {
    if (!Array.isArray(players) || count < 2) {
        return false;
    }

    return players.every(player => Boolean(player.ready));
}

function syncLocalPlayerState(players) {
    if (!Array.isArray(players)) {
        return;
    }

    const localPlayerId = getKnownPlayerId();
    if (!localPlayerId) {
        return;
    }

    const localPlayer = players.find(player => player.id === localPlayerId);
    if (!localPlayer) {
        return;
    }

    gameState.yourPlayerId = localPlayer.id;
    gameState.isReady = Boolean(localPlayer.ready);
}

// Socket event handlers
socket.on('player_joined', function (data) {
    console.log('Player joined event received:', data);
    const allReady = getAllPlayersReady(data.players, data.player_count);
    updatePlayersList(data.players, data.player_count, allReady);
    updateScoreboard(data.players);
    gameState.playerCount = data.player_count;
    syncLocalPlayerState(data.players);
    updateWaitingRoomButtons();

    // Update game settings and score history
    if (data.game_settings) {
        updateGameSettings(data.game_settings);
    }
    if (data.score_history) {
        updateScoreHistory(data.score_history);
    }
});

socket.on('player_reconnected', function (data) {
    console.log('Player reconnected:', data);
    showStatus(`${data.player_name} has reconnected`, 'info');

    // If this is the current player and they're a host, emit ready status
    const storedData = localStorage.getItem(`playerData_${roomId}`);
    if (storedData) {
        try {
            const playerData = JSON.parse(storedData);
            if (playerData.player_id === data.player_id && playerData.is_host) {
                gameState.isHost = true;
                gameState.isReady = true;
                setTimeout(() => {
                    socket.emit('player_ready', { ready: true });
                }, 100);
            }
        } catch (e) {
            console.log('Error parsing stored player data:', e);
        }
    }
});

socket.on('player_disconnected', function (data) {
    console.log('Player disconnected:', data);
    showStatus(`${data.player_name} has disconnected`, 'warning');
});

socket.on('player_removed', function (data) {
    console.log('Player removed from room:', data);
    localStorage.removeItem(`playerData_${roomId}`);
    showStatus(data.message || 'You were removed from the room.', 'warning');
    window.setTimeout(() => {
        window.location.href = '/';
    }, 1200);
});

socket.on('player_removed_notice', function (data) {
    console.log('Player removed notice:', data);
    showStatus(data.message || `${data.player_name} was removed from the room.`, 'info');
});

socket.on('game_reconnected', function (data) {
    console.log('Game reconnected, restoring state:', data);

    // Restore game state
    gameState.playerData = data;
    gameState.availableQuestions = data.available_questions;
    gameState.currentTurn = data.current_turn;
    gameState.playerCount = data.player_count;
    gameState.yourPlayerId = data.your_player_id;
    gameState.allPlayers = data.all_players;
    gameState.timeLimit = data.time_limit;
    gameState.penaltyMode = data.penalty_mode;
    gameState.finalRound = Boolean(data.final_round);
    gameState.finalRoundPlayer = data.final_round_player || null;

    // Show game interface
    document.getElementById('waitingRoom').style.display = 'none';
    document.getElementById('gameInterface').style.display = 'block';
    hideJoinSheet();
    setGamePanel('table');

    // Restore UI
    displayYourTiles(data.tiles);
    displayAvailableQuestions(data.available_questions);
    updateTurnIndicator(data.current_turn);

    if (data.center_tiles_count) {
        setupCenterTiles(data.center_tiles_count);
    }

    setupOtherPlayers();
    updateGuessDisplay();
    ensureTimerUpdatesActive();

    showStatus('Game state restored successfully!', 'success');
});

socket.on('room_joined', function (data) {
    console.log('Successfully joined room:', data);
    showStatus(data.message, 'success');
    hideJoinSheet();

    // Store player information securely
    localStorage.setItem(`playerData_${roomId}`, JSON.stringify({
        player_id: data.player_id,
        player_name: data.player_name,
        session_key: data.session_key,
        is_host: data.is_host
    }));

    // Update URL to include player info for future reconnections
    const newUrl = `${window.location.pathname}?player_id=${data.player_id}`;
    window.history.replaceState({}, '', newUrl);

    // Set local game state
    gameState.yourPlayerId = data.player_id;
    gameState.isHost = data.is_host || false;
    gameState.isReady = data.is_host || false; // Host is auto-ready

    // Update waiting room buttons for all players
    updateWaitingRoomButtons();
    setWaitingPanel('lobby');

    // If this is a host, automatically emit ready status
    if (data.is_host) {
        setTimeout(() => {
            socket.emit('player_ready', { ready: true });
        }, 100);
    }
});

socket.on('game_started', function (data) {
    console.log('Game started event received:', data);
    showStatus('Game has started!', 'success');
    hideJoinSheet();

    // Update basic game state
    gameState.availableQuestions = data.available_questions;
    gameState.currentTurn = data.current_turn;
    gameState.playerCount = data.player_count;
    gameState.timeLimit = data.time_limit;
    gameState.penaltyMode = data.penalty_mode;
    gameState.finalRound = false;
    gameState.finalRoundPlayer = null;

    // Start timer updates for all players
    startTimerUpdates();

    console.log('Waiting for personalized game data...');
});

socket.on('time_violation', function (data) {
    console.log('Time violation:', data);

    let message = `⏰ ${data.player_name}: ${data.message}`;
    let statusType = 'warning';

    if (data.penalty_type === 'score_penalty') {
        statusType = 'warning';
        message = `📉 ${data.player_name} received a score penalty for exceeding time!`;
    }

    showStatus(message, statusType);
    addToGameLog(`⏰ Time violation: ${data.message}`, 'answer');
});

socket.on('player_game_data', function (data) {
    console.log('Player game data received:', data);

    gameState.playerData = data;
    gameState.availableQuestions = data.available_questions;
    gameState.currentTurn = data.current_turn;
    gameState.playerCount = data.player_count;
    gameState.yourPlayerId = data.your_player_id;
    gameState.allPlayers = data.all_players;
    gameState.timeLimit = data.time_limit;
    gameState.penaltyMode = data.penalty_mode;
    gameState.finalRound = Boolean(data.final_round);
    gameState.finalRoundPlayer = data.final_round_player || null;

    console.log('Hiding waiting room, showing game interface');

    // Hide waiting room, show game interface
    document.getElementById('waitingRoom').style.display = 'none';
    document.getElementById('gameInterface').style.display = 'block';
    hideJoinSheet();
    setGamePanel('table');

    // Re-enable guess buttons for new game
    const submitBtn = document.getElementById('submitGuess');
    const clearBtn = document.getElementById('clearGuess');
    if (submitBtn) submitBtn.disabled = false;
    if (clearBtn) clearBtn.disabled = false;

    // Re-enable tile buttons
    document.querySelectorAll('#availableTiles .tile-button').forEach(btn => {
        btn.disabled = false;
    });

    // Clear any previous guess
    currentGuess = [];

    // Setup game interface
    displayYourTiles(data.tiles);
    displayAvailableQuestions(data.available_questions);
    updateTurnIndicator(data.current_turn);

    // Start timer if it's my turn and there's a time limit
    if (data.current_turn === data.your_player_id && data.time_limit) {
        startTimer(data.time_limit);
    } else {
        stopTimer();
    }

    if (data.center_tiles_count) {
        setupCenterTiles(data.center_tiles_count);
    }

    setupOtherPlayers();

    // Update guess display to show empty state
    updateGuessDisplay();
    ensureTimerUpdatesActive();

    console.log('Game interface setup complete');
});

socket.on('question_asked', function (data) {
    // Format the question with ** ** highlighting
    const formattedQuestion = data.question.replace(/\*\*(.*?)\*\*/g, '<span class="question-highlight">$1</span>');

    // Add question to log with special styling
    const questionMessage = `<span class="question-icon">❓</span> <span class="player-name-question">${data.asking_player}</span> asked: "${formattedQuestion}"`;
    addToGameLog(questionMessage, 'question');

    // Display all answers with special styling
    for (const playerId in data.answers) {
        const playerInfo = data.answers[playerId];
        const answerMessage = `<span class="answer-icon">💬</span> <span class="player-name-answer">${playerInfo.name}</span>: <strong>${playerInfo.answer}</strong>`;
        addToGameLog(answerMessage, 'answer');
    }
});

socket.on('questions_updated', function (data) {
    console.log('Questions updated:', data.available_questions);
    gameState.availableQuestions = data.available_questions;
    displayAvailableQuestions(data.available_questions);

    // Show appropriate status message
    if (data.new_question_added) {
        showStatus('Question cards refreshed! New card added.', 'info');
    } else {
        if (data.total_questions_remaining === 0) {
            showStatus('No more questions available! Only guessing allowed now.', 'warning');
        } else {
            showStatus(`Questions updated - ${data.total_questions_remaining} question(s) remaining.`, 'info');
        }
    }

    // Hide question interface if it's open
    hideQuestionInterface();
});

socket.on('turn_changed', function (data) {
    gameState.currentTurn = data.current_turn;
    gameState.finalRound = Boolean(data.final_round);
    gameState.finalRoundPlayer = data.final_round_player || null;
    updateTurnIndicator(data.current_turn);

    // Ensure timer updates are running during active game
    if (document.getElementById('gameInterface').style.display !== 'none' && !timerUpdateInterval) {
        console.log('Starting timer updates on turn change');
        startTimerUpdates();
    }

    // Start timer for the new player's turn
    if (data.current_turn === gameState.yourPlayerId && gameState.timeLimit) {
        startTimer(gameState.timeLimit);
    } else {
        stopTimer();
    }

    if (data.current_turn === gameState.yourPlayerId) {
        playSound('turnChangeSound');
    }
});

socket.on('error', function (data) {
    console.log('Error received:', data);
    if (data.message.includes('name already exists')) {
        showStatus(`${data.message}. Choose a different name.`, 'error');
        openJoinSheet('That name is already taken in this room. Choose a different one.');
    } else {
        showStatus(data.message, 'error');

        // If connection failed, clear stored data and redirect
        if (data.message.includes('Reconnection failed') || data.message.includes('Invalid session key')) {
            localStorage.removeItem(`playerData_${roomId}`);
            openJoinSheet('Your saved session is no longer valid. Enter a name to join again.');
        }
    }
});

socket.on('connect', function () {
    console.log('Connected to server');

    // Check if we have stored player data for this room
    const storedData = getStoredPlayerData();
    const urlParams = new URLSearchParams(window.location.search);
    const urlPlayerId = urlParams.get('player_id');

    if (storedData && storedData.player_id && storedData.session_key) {
        if (!urlPlayerId || storedData.player_id === urlPlayerId) {
            console.log('Attempting to reconnect with stored credentials');
            socket.emit('join_room', {
                room_id: roomId,
                reconnect: {
                    player_id: storedData.player_id,
                    session_key: storedData.session_key
                }
            });

            gameState.yourPlayerId = storedData.player_id;
            gameState.isHost = storedData.is_host || false;
            gameState.isReady = storedData.is_host || false;
            return;
        }

        console.log('Stored player data does not match URL player_id, skipping auto-reconnect');
    }

    console.log('New player joining');
    openJoinSheet(`Choose a player name to join room ${roomId}.`);
});

// Event listeners for reorder functionality
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('reorderPlayersBtn').addEventListener('click', function () {
        enterReorderMode();
    });

    document.getElementById('saveOrderBtn').addEventListener('click', function () {
        savePlayerOrder();
    });

    document.getElementById('cancelOrderBtn').addEventListener('click', function () {
        exitReorderMode();
    });

    document.getElementById('directJoinForm').addEventListener('submit', function (event) {
        event.preventDefault();
        submitDirectJoin();
    });

    document.getElementById('joinSheetBack').addEventListener('click', function () {
        window.location.href = '/';
    });

    document.querySelectorAll('[data-waiting-panel-target]').forEach(button => {
        button.addEventListener('click', function () {
            setWaitingPanel(button.dataset.waitingPanelTarget);
        });
    });

    document.querySelectorAll('[data-game-panel-target]').forEach(button => {
        button.addEventListener('click', function () {
            setGamePanel(button.dataset.gamePanelTarget);
        });
    });

    setWaitingPanel('lobby');
    setGamePanel('table');
});

socket.on('guess_made', function (data) {
    let message = `<span class="guess-icon">🎯</span> <strong>${data.player}</strong> guessed <em>${data.target}</em>`;
    if (data.correct) {
        message += ` - <span class="correct-result">🎉 CORRECT! ✅</span>`;
        // if (data.actual_tiles) {
        //     const tilesHTML = data.actual_tiles.map(tile =>
        //         `<span class="actual-tile ${tile.color}">${tile.number}</span>`
        //     ).join('');
        //     message += ` <span class="guessed-tiles-display">[${tilesHTML}]</span>`;
        // }

        // Trigger celebration effects for correct guesses
        showCelebration();
        playSound('correctAnswerSound');

        // Ensure timer updates continue if game is still active
        // Only restart if we're still in game interface and don't have timer updates running
        setTimeout(() => {
            if (document.getElementById('gameInterface').style.display !== 'none' && !timerUpdateInterval) {
                console.log('Restarting timer updates after correct guess');
                startTimerUpdates();
            }
        }, 500); // Small delay to allow server to process game state
    } else {
        message += ` - <span class="wrong-result">❌ WRONG</span>`;
        if (data.player_count === 2) {
            const tilesHTML = data.guess.map(tile =>
                `<span class="actual-tile ${tile.color}">${tile.number}</span>`
            ).join('');
            message += `<br><span class="reveal-label">🔍 Guessed tiles:</span> <span class="guessed-tiles-display">${tilesHTML}</span>`;
        }
        playSound('wrongAnswerSound');
    }
    addToGameLog(message);
});

socket.on('final_round_started', function (data) {
    console.log('Final round started:', data);
    gameState.finalRound = true;
    gameState.finalRoundPlayer = data.final_player;
    addToGameLog(data.message);
    showStatus(data.message, 'info');
    updateTurnIndicator(gameState.currentTurn);

    // Ensure timer updates continue during final round
    ensureTimerUpdatesActive();

    // Disable question asking for everyone in final round
    const questionCards = document.querySelectorAll('.question-card');
    questionCards.forEach(card => {
        card.style.opacity = '0.5';
        card.style.pointerEvents = 'none';
    });
});

socket.on('game_ended', function (data) {
    addToGameLog(`Game Over! Winners: ${data.winners.join(', ')}`);
    // The message from server now includes actual points awarded after penalties
    showStatus(data.message, data.is_draw ? 'info' : 'success');

    // Stop and reset timer
    stopTimer();
    stopTimerUpdates(); // Stop all player timer updates
    currentTimeLimit = null;
    turnStartTime = null;

    // Disable further interactions
    const submitBtn = document.getElementById('submitGuess');
    const clearBtn = document.getElementById('clearGuess');
    if (submitBtn) submitBtn.disabled = true;
    if (clearBtn) clearBtn.disabled = true;

    // Disable tile buttons
    document.querySelectorAll('#availableTiles .tile-button').forEach(btn => {
        btn.disabled = true;
    });

    // Redirect to waiting room if specified
    if (data.redirect_to_waiting) {
        setTimeout(() => {
            // Hide game interface, show waiting room
            document.getElementById('gameInterface').style.display = 'none';
            document.getElementById('waitingRoom').style.display = 'block';
            setWaitingPanel('lobby');

            // Reset game state
            gameState.finalRound = false;
            gameState.finalRoundPlayer = null;
            gameState.currentTurn = null;
            gameState.isReady = gameState.isHost; // Host auto-ready

            // Reset timer state
            gameState.timeLimit = null;
            gameState.penaltyMode = null;

            // Update waiting room buttons
            updateWaitingRoomButtons();

            // Emit ready status if host
            if (gameState.isHost) {
                socket.emit('player_ready', { ready: true });
            }

            showStatus('Game finished! Ready for next game?', 'info');
        }, 3000);
    }
});

socket.on('player_ready_update', function (data) {
    console.log('Player ready update:', data);
    updatePlayersList(data.players, data.players.length, data.all_ready);
    syncLocalPlayerState(data.players);
    updateWaitingRoomButtons();

    // Update scoreboard with proper player data
    const playersForScoreboard = data.players.map(player => ({
        name: player.name,
        score: player.score || 0
    }));
    updateScoreboard(playersForScoreboard);
});

// Event listeners
document.getElementById('startGameBtn').addEventListener('click', function () {
    console.log('Start game button clicked!');
    console.log('Button disabled state:', this.disabled);
    console.log('Player count:', gameState.playerCount);

    if (this.disabled) {
        console.log('Button is disabled, cannot start game');
        return;
    }

    console.log('Emitting start_game event...');
    socket.emit('start_game');
});

document.getElementById('backToLobby').addEventListener('click', function () {
    window.location.href = '/';
});

document.getElementById('copyRoomId').addEventListener('click', function () {
    navigator.clipboard.writeText(roomId);
    showStatus('Room ID copied to clipboard!', 'success');
});

document.getElementById('confirmQuestion').addEventListener('click', function () {
    const data = {
        question_index: gameState.selectedQuestionIndex
    };

    // Include chosen number if one was selected
    if (gameState.chosenNumber !== null) {
        data.chosen_number = gameState.chosenNumber;
    }

    socket.emit('ask_question', data);

    hideQuestionInterface();
});

document.getElementById('cancelQuestion').addEventListener('click', function () {
    hideQuestionInterface();
});

document.getElementById('readyBtn').addEventListener('click', function () {
    gameState.isReady = true;
    socket.emit('player_ready', { ready: true });
    updateWaitingRoomButtons();
});

document.getElementById('notReadyBtn').addEventListener('click', function () {
    gameState.isReady = false;
    socket.emit('player_ready', { ready: false });
    updateWaitingRoomButtons();
});

// Helper functions
function updateWaitingRoomButtons() {
    const startBtn = document.getElementById('startGameBtn');
    const readyBtn = document.getElementById('readyBtn');
    const notReadyBtn = document.getElementById('notReadyBtn');

    if (gameState.isHost) {
        // Host sees start button
        startBtn.style.display = 'inline-block';
        readyBtn.style.display = 'none';
        notReadyBtn.style.display = 'none';
    } else {
        // Regular players see ready/not ready buttons
        startBtn.style.display = 'none';
        if (gameState.isReady) {
            readyBtn.style.display = 'none';
            notReadyBtn.style.display = 'inline-block';
        } else {
            readyBtn.style.display = 'inline-block';
            notReadyBtn.style.display = 'none';
        }
    }
}

function updatePlayersList(players, count, allReady = null) {
    const listElement = document.getElementById('playersList');
    listElement.innerHTML = '';

    if (allReady === null && Array.isArray(players)) {
        allReady = getAllPlayersReady(players, count);
    }

    if (Array.isArray(players)) {
        // Handle array format (with ready status, scores, and connection status)
        players.forEach(player => {
            listElement.appendChild(createPlayerItem({
                id: player.id,
                name: player.name,
                ready: Boolean(player.ready),
                connected: player.connected !== false,
                score: player.score || 0
            }));
        });
    } else {
        // Handle old format (just player objects)
        players.forEach((player, index) => {
            listElement.appendChild(createPlayerItem({
                id: player.id || `player_${index}`,
                name: player.name,
                ready: Boolean(player.ready),
                connected: player.connected !== false,
                score: player.score || 0
            }));
        });
    }

    const countDiv = document.createElement('div');
    countDiv.className = 'player-count';
    countDiv.textContent = `${count} player(s) joined`;
    listElement.appendChild(countDiv);

    // Show host controls if user is host and not in reorder mode
    const hostControls = document.getElementById('hostControls');
    if (gameState.isHost && !reorderMode) {
        hostControls.style.display = 'block';
    } else {
        hostControls.style.display = 'none';
    }

    // Update start button for host
    if (gameState.isHost) {
        const startBtn = document.getElementById('startGameBtn');
        if (allReady && count >= 2) {
            startBtn.disabled = false;
        } else {
            startBtn.disabled = true;
        }
    }
}

function updateScoreboard(players) {
    const scoreboard = document.getElementById('gameScoreboard');
    if (!scoreboard) return;

    scoreboard.innerHTML = '';

    // Convert players object to array if needed and sort by score
    let playerList = [];
    if (Array.isArray(players)) {
        playerList = players;
    } else if (typeof players === 'object') {
        playerList = Object.values(players);
    }

    // Sort by score (highest first)
    playerList.sort((a, b) => (b.score || 0) - (a.score || 0));

    playerList.forEach((player, index) => {
        const scoreItem = document.createElement('div');
        scoreItem.className = 'score-item';
        const position = index + 1;
        const medal = position === 1 ? '🥇' : position === 2 ? '🥈' : position === 3 ? '🥉' : '';

        // Create score item content with medal animation if applicable
        let content = '';
        if (medal) {
            content += `<span class="score-medal">${medal}</span>`;
        }
        content += `
            <span class="score-rank">#${position}</span>
            <span class="score-name">${player.name}</span>
            <span class="score-points">${player.score || 0} pts</span>
        `;

        scoreItem.innerHTML = content;
        scoreboard.appendChild(scoreItem);
    });
}

function displayYourTiles(tiles) {
    const container = document.getElementById('yourTiles');
    container.innerHTML = '';

    tiles.forEach(tile => {
        const tileElement = document.createElement('button');
        tileElement.type = 'button';
        tileElement.tabIndex = -1;
        tileElement.className = `tile-button table-tile ${tile.color}`;
        tileElement.textContent = tile.number;
        container.appendChild(tileElement);
    });
}

function displayAvailableQuestions(questions) {
    const container = document.getElementById('availableQuestions');
    container.innerHTML = '';

    questions.forEach((question, index) => {
        const questionElement = document.createElement('button');
        questionElement.type = 'button';
        questionElement.className = 'question-card';

        const questionLabel = getQuestionCardLabel(question);
        const requiresNumber = question.includes("You must choose one number before asking that question");
        const footerText = requiresNumber
            ? 'Pick one number first, then open the ask sheet.'
            : 'Tap to open the ask sheet and send this clue.';

        if (requiresNumber) {
            questionElement.classList.add('requires-choice');
        }

        // Format text between ** ** as bold and green
        const formattedText = question.replace(/\*\*(.*?)\*\*/g, '<span class="question-highlight">$1</span>');
        questionElement.innerHTML = `
            <span class="question-card-index">${index + 1}</span>
            <span class="question-card-body">
                <span class="question-card-topline">
                    <span class="question-card-label">${questionLabel}</span>
                    <span class="question-card-badge">${requiresNumber ? 'Pick a number' : 'Ready to ask'}</span>
                </span>
                <span class="question-card-text">${formattedText}</span>
                <span class="question-card-footer">${footerText}</span>
            </span>
        `;

        questionElement.addEventListener('click', () => {
            container.querySelectorAll('.question-card').forEach(card => card.classList.remove('selected'));
            if (selectQuestion(index, question)) {
                questionElement.classList.add('selected');
            }
        });
        container.appendChild(questionElement);
    });
}

function getQuestionCardLabel(question) {
    const normalizedQuestion = question.toLowerCase();

    if (normalizedQuestion.includes('how many')) {
        return 'Count clue';
    }

    if (normalizedQuestion.includes('where are')) {
        return 'Locate clue';
    }

    if (normalizedQuestion.includes('sum')) {
        return 'Sum clue';
    }

    if (normalizedQuestion.includes('difference') || normalizedQuestion.includes('greater than')) {
        return 'Compare clue';
    }

    if (
        normalizedQuestion.includes('neighbour') ||
        normalizedQuestion.includes('same color') ||
        normalizedQuestion.includes('same number') ||
        normalizedQuestion.includes('consecutive')
    ) {
        return 'Pattern clue';
    }

    return 'Deduction clue';
}

function selectQuestion(index, question) {
    // Check if it's player's turn
    if (gameState.currentTurn !== gameState.yourPlayerId) {
        showStatus("It's not your turn!", 'error');
        return false;
    }

    // Check if in final round
    if (gameState.finalRound) {
        if (gameState.finalRoundPlayer === gameState.yourPlayerId) {
            showStatus("Final round - you must make a guess, not ask questions!", 'error');
        } else {
            showStatus("Final round in progress - you cannot ask questions!", 'error');
        }
        return false;
    }

    gameState.selectedQuestionIndex = index;
    gameState.selectedQuestion = question;
    gameState.chosenNumber = null; // Reset chosen number

    // Format the selected question with the same highlighting
    const formattedText = question.replace(/\*\*(.*?)\*\*/g, '<span class="question-highlight">$1</span>');
    document.getElementById('selectedQuestion').innerHTML = formattedText;

    // Check if this question requires number selection
    if (question.includes("You must choose one number before asking that question")) {
        setupNumberSelection(question);
    } else {
        hideNumberSelection();
    }

    showQuestionInterface();
    return true;
}

function setupNumberSelection(question) {
    const numberSection = document.getElementById('numberSelectionSection');
    const numberButtons = document.getElementById('numberButtons');
    const selectedDisplay = document.getElementById('selectedNumberDisplay');

    // Clear previous buttons
    numberButtons.innerHTML = '';
    selectedDisplay.textContent = '';

    // Determine which numbers are valid for this question
    let validNumbers = [];
    if (question.includes('#8** or **#9')) {
        validNumbers = [8, 9];
    } else if (question.includes('#1** or **#2')) {
        validNumbers = [1, 2];
    } else if (question.includes('#3** or **#4')) {
        validNumbers = [3, 4];
    } else if (question.includes('#6** or **#7')) {
        validNumbers = [6, 7];
    }

    // Create number buttons
    validNumbers.forEach(number => {
        const button = document.createElement('button');
        button.className = 'number-button';
        button.textContent = number;
        button.dataset.number = number;
        button.addEventListener('click', () => selectNumber(number));
        numberButtons.appendChild(button);
    });

    // Show the number selection section
    numberSection.style.display = 'block';

    // Update confirm button state
    updateConfirmButtonState();
}

function hideNumberSelection() {
    const numberSection = document.getElementById('numberSelectionSection');
    numberSection.style.display = 'none';
    gameState.chosenNumber = null;
    updateConfirmButtonState();
}

function selectNumber(number) {
    gameState.chosenNumber = number;

    // Update button states
    document.querySelectorAll('.number-button').forEach(btn => {
        btn.classList.remove('selected');
        if (parseInt(btn.dataset.number) === number) {
            btn.classList.add('selected');
        }
    });

    // Update display
    const selectedDisplay = document.getElementById('selectedNumberDisplay');
    selectedDisplay.textContent = `Selected number: ${number}`;

    // Update confirm button state
    updateConfirmButtonState();
}

function updateConfirmButtonState() {
    const confirmBtn = document.getElementById('confirmQuestion');
    const requiresNumber = gameState.selectedQuestion &&
        gameState.selectedQuestion.includes("You must choose one number before asking that question");

    if (requiresNumber && gameState.chosenNumber === null) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Choose a number first';
    } else {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Ask Question';
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showQuestionInterface() {
    setGamePanel('questions');
    document.getElementById('askQuestionInterface').style.display = 'block';
}

function hideQuestionInterface() {
    document.getElementById('askQuestionInterface').style.display = 'none';
    document.querySelectorAll('.question-card.selected').forEach(card => {
        card.classList.remove('selected');
    });
    hideNumberSelection();
    gameState.selectedQuestionIndex = null;
    gameState.selectedQuestion = null;
}

function updateTurnIndicator(currentTurn) {
    const indicator = document.getElementById('currentTurnText');
    const turnIndicator = document.getElementById('turnIndicator');
    const submitBtn = document.getElementById('submitGuess');
    const clearBtn = document.getElementById('clearGuess');
    const tileButtons = document.querySelectorAll('#availableTiles .tile-button');

    // Remove all existing turn classes
    turnIndicator.classList.remove('your-turn', 'waiting-turn', 'final-round');

    if (currentTurn === gameState.yourPlayerId) {
        if (gameState.finalRound && gameState.finalRoundPlayer === gameState.yourPlayerId) {
            // In final round and you are the final player - can only guess
            turnIndicator.classList.add('final-round');
            indicator.innerHTML = '<span class="turn-icon">⚡</span>Final Round - Make your guess!';
            setGamePanel('guess');

            // Enable guess interface
            if (submitBtn) submitBtn.disabled = false;
            if (clearBtn) clearBtn.disabled = false;

            // Enable all tile buttons for selection
            tileButtons.forEach(btn => {
                btn.disabled = false;
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
        } else if (gameState.finalRound) {
            // In final round but not the final player - cannot act
            turnIndicator.classList.add('waiting-turn');
            indicator.innerHTML = '<span class="turn-icon">⏳</span>Final round in progress - Waiting...';

            // Disable guess interface
            if (submitBtn) submitBtn.disabled = true;
            if (clearBtn) clearBtn.disabled = true;
            tileButtons.forEach(btn => {
                btn.disabled = true;
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.5';
            });
        } else {
            // Normal turn - can ask questions or guess
            turnIndicator.classList.add('your-turn');
            indicator.innerHTML = '<span class="turn-icon">🎯</span>Your Turn - Ask a question or make a guess!';

            // Enable guess interface
            if (submitBtn) submitBtn.disabled = false;
            if (clearBtn) clearBtn.disabled = false;

            // Enable all tile buttons for selection
            tileButtons.forEach(btn => {
                btn.disabled = false;
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
        }
    } else {
        // Not your turn
        turnIndicator.classList.add('waiting-turn');
        if (currentTurn && gameState.allPlayers && gameState.allPlayers[currentTurn]) {
            indicator.innerHTML = `<span class="turn-icon">⏱️</span>${gameState.allPlayers[currentTurn].name}'s Turn`;
        } else {
            indicator.innerHTML = '<span class="turn-icon">⏱️</span>Waiting for turn...';
        }

        // Disable guess interface when not your turn
        if (submitBtn) submitBtn.disabled = true;
        if (clearBtn) clearBtn.disabled = true;
        tileButtons.forEach(btn => {
            btn.disabled = true;
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.5';
        });
    }
}

function setupCenterTiles(count) {
    const section = document.getElementById('centerTilesSection');
    section.style.display = 'block';
    const title = section.querySelector('h3');
    if (title) {
        title.textContent = 'Center code';
    }

    const container = document.getElementById('centerTiles');
    container.innerHTML = '';

    for (let i = 0; i < count; i++) {
        const tileElement = document.createElement('button');
        tileElement.type = 'button';
        tileElement.tabIndex = -1;
        tileElement.className = 'tile-button table-tile tile-hidden';
        tileElement.textContent = '?';
        container.appendChild(tileElement);
    }
}

function setupOtherPlayers() {
    // Setup other players display based on game mode
    const container = document.getElementById('otherPlayers');
    const sectionTitle = document.querySelector('#otherPlayersSection h3');
    const rivals = Object.entries(gameState.allPlayers || {}).filter(([playerId]) => playerId !== gameState.yourPlayerId);

    if (gameState.playerCount === 2) {
        if (sectionTitle) {
            sectionTitle.textContent = "Opponent's code";
        }

        container.innerHTML = '';
        const grid = document.createElement('div');
        grid.className = 'opponent-code-grid';

        rivals.forEach(([playerId, player]) => {
            const playerDiv = document.createElement('div');
            playerDiv.className = 'opponent-code-card';
            playerDiv.innerHTML = `
                <div class="opponent-code-head">
                    <div>
                        <strong>${escapeHtml(player.name)}</strong>
                        <span class="opponent-meta">Hidden code · 5 tiles</span>
                    </div>
                    <span class="opponent-code-label">Target</span>
                </div>
                <div class="tiles-container opponent-code-rack"></div>
                <p class="opponent-code-note">Read the clues, track the hidden order, then commit to the full code break.</p>
            `;

            const rack = playerDiv.querySelector('.opponent-code-rack');
            for (let i = 0; i < 5; i++) {
                const tileElement = document.createElement('button');
                tileElement.type = 'button';
                tileElement.tabIndex = -1;
                tileElement.className = 'tile-button table-tile tile-hidden';
                tileElement.textContent = '?';
                rack.appendChild(tileElement);
            }

            grid.appendChild(playerDiv);
        });

        container.appendChild(grid);
    } else {
        if (sectionTitle) {
            sectionTitle.textContent = 'Opponents';
        }

        container.innerHTML = '';
        const grid = document.createElement('div');
        grid.className = 'other-players-grid';

        rivals.forEach(([, player]) => {
            const playerDiv = document.createElement('div');
            playerDiv.className = 'other-player-item';
            playerDiv.innerHTML = `
                <strong>${escapeHtml(player.name)}</strong>
                <span class="opponent-meta">Racing with you to solve the center code</span>
            `;
            grid.appendChild(playerDiv);
        });

        container.appendChild(grid);
    }

    // Setup guess interface when game starts
    setupGuessInterface();
}

function setupGuessInterface() {
    console.log('setupGuessInterface called - player count:', gameState.playerCount);

    // Update guess interface title based on game mode
    const guessSection = document.querySelector('.guess-section h3');
    if (gameState.playerCount === 2) {
        guessSection.textContent = 'Break Another Player\'s Code';
    } else {
        guessSection.textContent = 'Break the Center Code';
    }

    // Update instructions
    const instructions = document.querySelector('.guess-instructions p');
    if (gameState.playerCount === 2) {
        instructions.textContent = 'Click tiles to select/deselect them for your guess:';
    } else {
        instructions.textContent = 'Click tiles to select/deselect them for your guess:';
    }

    const availableTilesContainer = document.getElementById('availableTiles');
    console.log('Available tiles container found:', !!availableTilesContainer);

    if (!availableTilesContainer) {
        console.error('availableTiles container not found!');
        return;
    }

    availableTilesContainer.innerHTML = '';

    // Add tiles 0-9 in sequential order with spacing
    for (let number = 0; number <= 9; number++) {
        console.log('Creating tiles for number:', number);
        if (number === 5) {
            // For number 5, add green tiles instead of black/white
            const greenTile1 = { number: 5, color: 'green' };
            const greenTile2 = { number: 5, color: 'green' };

            // Calculate index for green tiles
            const index1 = number * 2;
            const index2 = number * 2 + 1;

            const button1 = document.createElement('button');
            button1.className = `tile-button ${greenTile1.color}`;
            button1.textContent = greenTile1.number;
            button1.dataset.tileIndex = index1;
            button1.dataset.number = greenTile1.number;
            button1.dataset.color = greenTile1.color;
            button1.dataset.selected = 'false';
            button1.addEventListener('click', () => toggleTileSelection(button1, greenTile1, index1));
            availableTilesContainer.appendChild(button1);

            const button2 = document.createElement('button');
            button2.className = `tile-button ${greenTile2.color}`;
            button2.textContent = greenTile2.number;
            button2.dataset.tileIndex = index2;
            button2.dataset.number = greenTile2.number;
            button2.dataset.color = greenTile2.color;
            button2.dataset.selected = 'false';
            button2.addEventListener('click', () => toggleTileSelection(button2, greenTile2, index2));
            availableTilesContainer.appendChild(button2);
        } else {
            // For all other numbers, add black first, then white
            const blackTile = { number: number, color: 'black' };
            const whiteTile = { number: number, color: 'white' };

            // Calculate index
            const blackIndex = number * 2;
            const whiteIndex = number * 2 + 1;

            const blackButton = document.createElement('button');
            blackButton.className = `tile-button ${blackTile.color}`;
            blackButton.textContent = blackTile.number;
            blackButton.dataset.tileIndex = blackIndex;
            blackButton.dataset.number = blackTile.number;
            blackButton.dataset.color = blackTile.color;
            blackButton.dataset.selected = 'false';
            blackButton.addEventListener('click', () => toggleTileSelection(blackButton, blackTile, blackIndex));
            availableTilesContainer.appendChild(blackButton);

            const whiteButton = document.createElement('button');
            whiteButton.className = `tile-button ${whiteTile.color}`;
            whiteButton.textContent = whiteTile.number;
            whiteButton.dataset.tileIndex = whiteIndex;
            whiteButton.dataset.number = whiteTile.number;
            whiteButton.dataset.color = whiteTile.color;
            whiteButton.dataset.selected = 'false';
            whiteButton.addEventListener('click', () => toggleTileSelection(whiteButton, whiteTile, whiteIndex));
            availableTilesContainer.appendChild(whiteButton);
        }

        // Add spacing element after each number (except the last one)
        if (number < 9) {
            const spacer = document.createElement('div');
            spacer.className = 'tile-spacer';
            availableTilesContainer.appendChild(spacer);
        }
    }

    console.log('Total elements created:', availableTilesContainer.children.length);
    console.log('Available tiles container children:', availableTilesContainer.children);

    // Setup clear and submit buttons
    const clearButton = document.getElementById('clearGuess');
    const submitButton = document.getElementById('submitGuess');

    // Remove existing event listeners to prevent duplicates
    clearButton.removeEventListener('click', clearGuess);
    submitButton.removeEventListener('click', submitGuess);

    // Add fresh event listeners
    clearButton.addEventListener('click', clearGuess);
    submitButton.addEventListener('click', submitGuess);

    // Initialize empty selection
    currentGuess = [];
    updateGuessDisplay();
}

let currentGuess = [];

function toggleTileSelection(button, tile, index) {
    const isSelected = button.dataset.selected === 'true';
    const maxTiles = gameState.playerCount === 2 ? 5 :
        gameState.playerCount === 3 ? 5 :
            gameState.playerCount === 4 ? 4 : 5;

    if (!isSelected) {
        // Trying to select a tile
        if (currentGuess.length >= maxTiles) {
            showStatus(`You can only select ${maxTiles} tiles for your guess`, 'error');
            return;
        }
        // Select the tile
        button.dataset.selected = 'true';
        currentGuess.push({ ...tile, buttonIndex: index });
    } else {
        // Deselecting a tile
        button.dataset.selected = 'false';
        // Remove from currentGuess
        currentGuess = currentGuess.filter(guessedTile =>
            !(guessedTile.buttonIndex === index &&
                guessedTile.number === tile.number &&
                guessedTile.color === tile.color)
        );
    }

    updateGuessDisplay();
}

function updateGuessDisplay() {
    const guessBuilder = document.getElementById('guessBuilder');
    guessBuilder.innerHTML = '';
    guessBuilder.classList.toggle('empty', currentGuess.length === 0);

    if (currentGuess.length === 0) {
        guessBuilder.innerHTML = '<p class="guess-placeholder">Select tiles above to build your guess.</p>';
        return;
    }

    // Sort the guess by the button index to maintain grid order
    const sortedGuess = [...currentGuess].sort((a, b) => a.buttonIndex - b.buttonIndex);

    sortedGuess.forEach((tile, index) => {
        const tileElement = document.createElement('button');
        tileElement.type = 'button';
        tileElement.tabIndex = -1;
        tileElement.className = `tile-button guess-display-tile ${tile.color}`;
        tileElement.textContent = tile.number;
        guessBuilder.appendChild(tileElement);
    });

    // Show count
    const maxTiles = gameState.playerCount === 2 ? 5 :
        gameState.playerCount === 3 ? 5 :
            gameState.playerCount === 4 ? 4 : 5;
    const countElement = document.createElement('p');
    countElement.className = 'guess-count';
    countElement.textContent = `Selected: ${currentGuess.length}/${maxTiles} tiles`;
    guessBuilder.appendChild(countElement);
}

function removeTileFromGuess(guessIndex) {
    // This function is no longer needed with toggle system
    // Keep for compatibility but it won't be called
}

function clearGuess() {
    // Reset all button states
    document.querySelectorAll('#availableTiles .tile-button').forEach(button => {
        button.dataset.selected = 'false';
    });

    currentGuess = [];
    updateGuessDisplay();
}

function submitGuess() {
    // Check if it's your turn
    if (gameState.currentTurn !== gameState.yourPlayerId) {
        showStatus("It's not your turn!", 'error');
        return;
    }

    // Check final round restrictions
    if (gameState.finalRound && gameState.finalRoundPlayer !== gameState.yourPlayerId) {
        showStatus("Only the final round player can make guesses now!", 'error');
        return;
    }

    // Updated tile counts for new game modes
    const maxTiles = gameState.playerCount === 2 ? 5 :
        gameState.playerCount === 3 ? 5 :
            gameState.playerCount === 4 ? 4 : 5;

    if (currentGuess.length !== maxTiles) {
        showStatus(`Please select exactly ${maxTiles} tiles for your guess`, 'error');
        return;
    }

    const guessData = currentGuess.map(tile => ({
        number: tile.number,
        color: tile.color
    }));

    let guessType = 'center';

    // For 2-player games, automatically target the other player
    if (gameState.playerCount === 2) {
        // Find the other player (not yourself)
        for (const playerId in gameState.allPlayers) {
            if (playerId !== gameState.yourPlayerId) {
                guessType = playerId;
                break;
            }
        }

        if (guessType === 'center') {
            showStatus('Unable to find target player for guess', 'error');
            return;
        }
    }
    // For 3-4 player games, guessType remains 'center'

    console.log('Submitting guess:', guessData, 'Type:', guessType);

    socket.emit('make_guess', {
        guess: guessData,
        guess_type: guessType
    });

    showStatus('Guess submitted!', 'success');

    // Clear the guess after submission
    clearGuess();
}

function addToGameLog(message, type = 'default') {
    const logContainer = document.getElementById('gameLog');
    const logEntry = document.createElement('div');

    // Set appropriate CSS classes based on type
    if (type === 'question') {
        logEntry.className = 'log-entry question-log-entry';
    } else if (type === 'answer') {
        logEntry.className = 'log-entry answer-log-entry';
    } else {
        logEntry.className = 'log-entry';
    }

    // Add timestamp and message content
    const timestamp = new Date().toLocaleTimeString();
    if (type === 'answer') {
        // For answers, don't add timestamp as they're grouped with questions
        logEntry.innerHTML = message;
    } else {
        logEntry.innerHTML = `<span style="color: #718096; font-size: 11px;">${timestamp}</span> ${message}`;
    }

    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;

    clearTimeout(statusTimeout);
    statusTimeout = setTimeout(() => {
        statusDiv.textContent = '';
        statusDiv.className = 'status-message';
    }, 5000);
}

// Celebration functions
function showCelebration() {
    // Create celebration overlay
    const overlay = document.createElement('div');
    overlay.className = 'celebration-overlay';
    document.body.appendChild(overlay);

    // Show celebration message
    const message = document.createElement('div');
    message.className = 'celebration-message';
    message.textContent = '🎉 CORRECT! 🎉';
    document.body.appendChild(message);

    // Create fireworks
    createFireworks(overlay);

    // Create falling flowers
    createFlowers(overlay);

    // Create stars
    createStars(overlay);

    // Remove elements after animation
    setTimeout(() => {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        if (message.parentNode) message.parentNode.removeChild(message);
    }, 3000);
}

function createFireworks(container) {
    const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ffa500'];

    for (let i = 0; i < 20; i++) {
        setTimeout(() => {
            const firework = document.createElement('div');
            firework.className = 'firework';
            firework.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            firework.style.left = Math.random() * 100 + '%';
            firework.style.top = Math.random() * 100 + '%';
            container.appendChild(firework);

            setTimeout(() => {
                if (firework.parentNode) firework.parentNode.removeChild(firework);
            }, 1500);
        }, i * 100);
    }
}

function createFlowers(container) {
    const flowers = ['🌸', '🌺', '🌻', '🌹', '🌼', '🌷', '🌿', '🍀'];

    for (let i = 0; i < 15; i++) {
        setTimeout(() => {
            const flower = document.createElement('div');
            flower.className = 'flower';
            flower.textContent = flowers[Math.floor(Math.random() * flowers.length)];
            flower.style.left = Math.random() * 100 + '%';
            flower.style.animationDelay = Math.random() * 0.5 + 's';
            container.appendChild(flower);

            setTimeout(() => {
                if (flower.parentNode) flower.parentNode.removeChild(flower);
            }, 2000);
        }, i * 150);
    }
}

function createStars(container) {
    const stars = ['⭐', '✨', '🌟', '💫'];

    for (let i = 0; i < 10; i++) {
        setTimeout(() => {
            const star = document.createElement('div');
            star.className = 'star';
            star.textContent = stars[Math.floor(Math.random() * stars.length)];
            star.style.left = Math.random() * 100 + '%';
            star.style.top = Math.random() * 100 + '%';
            star.style.animationDelay = Math.random() * 0.3 + 's';
            container.appendChild(star);

            setTimeout(() => {
                if (star.parentNode) star.parentNode.removeChild(star);
            }, 2000);
        }, i * 200);
    }
}

function playSound(soundId) {
    const sound = document.getElementById(soundId);
    if (sound && typeof sound.play === 'function') {
        sound.currentTime = 0;
        sound.play().catch(e => { });
    }
}

// Timer management functions
function startTimer(timeLimit) {
    if (timeLimit === null || timeLimit === undefined) {
        hidePopupClock();
        return;
    }

    currentTimeLimit = timeLimit;
    turnStartTime = Date.now();

    // Ensure global timer updates are running when starting individual timer
    ensureTimerUpdatesActive();

    // No need to show timer here - it's handled by updateSimpleTimer

    // Clear any existing timer
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    // Update timer every second
    timerInterval = setInterval(updateTimerDisplay, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    // Timer hiding is handled by updateSimpleTimer when there's no active timer
}

function showTimer() {
    // Legacy function - timer display is now handled by showPopupClock
}

function hideTimer() {
    // Legacy function - timer hiding is now handled by hidePopupClock
}

function updateTimerDisplay() {
    // Legacy function - timer updates are now handled by the all_timers_update socket event
    // and updateSimpleTimer function
}

function formatTimeLimit(seconds) {
    if (!seconds) return 'Unlimited';

    if (seconds < 60) {
        return `${seconds} seconds`;
    } else {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        if (remainingSeconds === 0) {
            return `${minutes} minute${minutes > 1 ? 's' : ''}`;
        } else {
            return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
        }
    }
}

socket.on('disconnect', function () {
    console.log('Disconnected from server');
    showStatus('Connection lost. Attempting to reconnect...', 'warning');
});

// Socket event for player reordering
socket.on('players_reordered', function (data) {
    console.log('Players reordered:', data);
    const allReady = getAllPlayersReady(data.players, data.players.length);
    updatePlayersList(data.players, data.players.length, allReady);
    syncLocalPlayerState(data.players);
    updateWaitingRoomButtons();
    exitReorderMode();
    showStatus(data.message, 'success');
});

// Reorder functionality
function enterReorderMode() {
    if (!gameState.isHost) {
        showStatus('Only the host can reorder players', 'error');
        return;
    }

    reorderMode = true;

    // Store original order and current player data
    const playersList = document.getElementById('playersList');
    const playerItems = Array.from(playersList.querySelectorAll('.player-item:not(.player-count)'));
    originalPlayerOrder = playerItems.map(item => item.dataset.playerId);
    currentPlayerOrder = [...originalPlayerOrder];

    // Store current player data for rebuilding
    gameState.currentPlayerData = playerItems.map(item => ({
        id: item.dataset.playerId,
        name: item.dataset.playerName || '',
        ready: item.dataset.playerReady === 'true',
        connected: item.dataset.playerConnected !== 'false',
        score: parseInt(item.dataset.playerScore || '0', 10),
        element: item
    }));

    // Show reorder controls
    document.getElementById('reorderControls').style.display = 'block';
    document.getElementById('hostControls').style.display = 'none';

    // Add reorder mode class and setup arrow buttons
    playersList.classList.add('reorder-mode');
    setupArrowButtons();

    // Add order numbers
    updateOrderNumbers();
}

function exitReorderMode() {
    reorderMode = false;

    // Hide reorder controls
    document.getElementById('reorderControls').style.display = 'none';
    if (gameState.isHost) {
        document.getElementById('hostControls').style.display = 'block';
    }

    // Remove reorder mode class
    document.getElementById('playersList').classList.remove('reorder-mode');

    // Remove drag and drop
    removeDragAndDrop();

    // Remove order numbers
    document.querySelectorAll('.player-order-number').forEach(el => el.remove());
}

function setupArrowButtons() {
    const playerItems = document.querySelectorAll('.player-item:not(.player-count)');

    playerItems.forEach((item, index) => {
        // Store the player ID
        item.dataset.playerId = currentPlayerOrder[index];

        // Create arrow buttons container
        const arrowsContainer = document.createElement('div');
        arrowsContainer.className = 'reorder-arrows';

        // Create up arrow button
        const upBtn = document.createElement('button');
        upBtn.className = 'arrow-btn up';
        upBtn.textContent = '↑';
        upBtn.setAttribute('aria-label', 'Move player up');
        upBtn.disabled = index === 0; // Disable if first item
        upBtn.addEventListener('click', () => movePlayerUp(index));

        // Create down arrow button
        const downBtn = document.createElement('button');
        downBtn.className = 'arrow-btn down';
        downBtn.textContent = '↓';
        downBtn.setAttribute('aria-label', 'Move player down');
        downBtn.disabled = index === playerItems.length - 1; // Disable if last item
        downBtn.addEventListener('click', () => movePlayerDown(index));

        arrowsContainer.appendChild(upBtn);
        arrowsContainer.appendChild(downBtn);
        item.appendChild(arrowsContainer);
    });
}

function removeArrowButtons() {
    document.querySelectorAll('.reorder-arrows').forEach(container => {
        container.remove();
    });
}

function movePlayerUp(currentIndex) {
    if (currentIndex === 0) return; // Already at top

    // Swap in the order array
    [currentPlayerOrder[currentIndex], currentPlayerOrder[currentIndex - 1]] =
        [currentPlayerOrder[currentIndex - 1], currentPlayerOrder[currentIndex]];

    // Update the UI
    updatePlayerListOrder();
}

function movePlayerDown(currentIndex) {
    if (currentIndex === currentPlayerOrder.length - 1) return; // Already at bottom

    // Swap in the order array
    [currentPlayerOrder[currentIndex], currentPlayerOrder[currentIndex + 1]] =
        [currentPlayerOrder[currentIndex + 1], currentPlayerOrder[currentIndex]];

    // Update the UI
    updatePlayerListOrder();
}

function updatePlayerListOrder() {
    const playersList = document.getElementById('playersList');
    const playerCountElement = playersList.querySelector('.player-count');

    // Remove all existing player items (but keep player-count)
    const existingPlayers = playersList.querySelectorAll('.player-item:not(.player-count)');
    existingPlayers.forEach(item => item.remove());

    // Rebuild the player list in the new order using stored data
    currentPlayerOrder.forEach((playerId, index) => {
        // Find player data from stored data
        const playerData = gameState.currentPlayerData.find(p => p.id === playerId);

        if (playerData) {
            const playerDiv = createPlayerItem(playerData);

            // Insert before player-count element
            if (playerCountElement) {
                playersList.insertBefore(playerDiv, playerCountElement);
            } else {
                playersList.appendChild(playerDiv);
            }
        }
    });

    // Re-setup arrow buttons and order numbers
    setupArrowButtons();
    updateOrderNumbers();
}

// Replace the old drag and drop functions
function setupDragAndDrop() {
    // This function is replaced by setupArrowButtons
    setupArrowButtons();
}

function removeDragAndDrop() {
    // This function is replaced by removeArrowButtons
    removeArrowButtons();
}

// Remove all the old drag and drop event handlers (keep as empty functions for compatibility)
function handleDragStart(e) { }
function handleDragEnd(e) { }
function handleDropZoneDragOver(e) { }
function handleDropZoneDragLeave(e) { }
function handleDropZoneDrop(e) { }
function handleDragOver(e) { }
function handleDrop(e) { }
function getDragAfterElement(container, y) { }

function updateOrderNumbers() {
    const playerItems = document.querySelectorAll('.player-item:not(.player-count)');

    // Remove existing order numbers
    document.querySelectorAll('.player-order-number').forEach(el => el.remove());

    // Add new order numbers
    playerItems.forEach((item, index) => {
        const orderNumber = document.createElement('div');
        orderNumber.className = 'player-order-number';
        orderNumber.textContent = index + 1;
        item.appendChild(orderNumber);

        // Update the dataset for consistency
        item.dataset.originalIndex = index;
    });
}

function savePlayerOrder() {
    if (!gameState.isHost) {
        showStatus('Only the host can reorder players', 'error');
        return;
    }

    if (JSON.stringify(currentPlayerOrder) === JSON.stringify(originalPlayerOrder)) {
        showStatus('No changes to save', 'info');
        exitReorderMode();
        return;
    }

    // Send new order to server
    socket.emit('reorder_players', {
        new_order: currentPlayerOrder
    });
}

// Game Settings Display Functions
function updateGameSettings(settings) {
    const gameSettingsDisplay = document.getElementById('gameSettingsDisplay');

    if (!settings) {
        gameSettingsDisplay.innerHTML = '<p>Game settings not available</p>';
        return;
    }

    // Format time limit display
    let timeLimitText = 'Unlimited';
    if (settings.time_limit) {
        if (settings.time_limit_display === 'custom') {
            timeLimitText = `${settings.custom_time} minutes (custom)`;
        } else if (settings.time_limit < 60) {
            timeLimitText = `${settings.time_limit} seconds`;
        } else {
            timeLimitText = `${Math.floor(settings.time_limit / 60)} minutes`;
        }
    }

    // Format penalty mode display
    let penaltyModeText = settings.penalty_mode === 'for_fun' ? 'For Fun (Alerts only)' : 'Competitive (Score penalty)';

    gameSettingsDisplay.innerHTML = `
        <div class="setting-item">
            <span class="setting-label">Max Players:</span>
            <span class="setting-value">${settings.max_players}</span>
        </div>
        <div class="setting-item">
            <span class="setting-label">Question Cards:</span>
            <span class="setting-value">${settings.num_question_cards}</span>
        </div>
        <div class="setting-item">
            <span class="setting-label">Time Limit:</span>
            <span class="setting-value">${timeLimitText}</span>
        </div>
        <div class="setting-item">
            <span class="setting-label">Penalty Mode:</span>
            <span class="setting-value">${penaltyModeText}</span>
        </div>
    `;
}

// Score History Display Functions
function updateScoreHistory(scoreHistory) {
    const scoreHistoryDisplay = document.getElementById('scoreHistoryDisplay');

    if (!scoreHistory || scoreHistory.length === 0) {
        scoreHistoryDisplay.innerHTML = '<p class="no-history">No games completed yet. Start playing to see score history!</p>';
        return;
    }

    // Display rounds in reverse order (most recent first)
    const historyHTML = scoreHistory.slice().reverse().map(round => {
        const roundTypeClass = round.is_draw ? 'draw' : 'win';

        // Handle both old format (winners) and new format (players)
        const playersData = round.players || round.winners || [];

        const playersHTML = playersData.map(player => {
            const resultClass = player.result ? player.result.toLowerCase() : (player.points_awarded > 0 ? 'win' : 'loss');
            const resultText = player.result || (player.points_awarded > 0 ? 'Win' : 'Loss');

            return `
                <div class="player-result-item ${resultClass}">
                    <span class="player-name">${player.player_name}</span>
                    <span class="player-result ${resultClass}">${resultText}</span>
                    ${player.points_awarded > 0 ? `<span class="player-points">+${player.points_awarded} pts</span>` : ''}
                    ${player.penalties > 0 ? `<span class="player-penalties">(-${player.penalties} penalty)</span>` : ''}
                </div>
            `;
        }).join('');

        return `
            <div class="round-history">
                <div class="round-header">
                    <span class="round-title">Round ${round.round}</span>
                </div>
                <div class="players-results-list">
                    ${playersHTML}
                </div>
            </div>
        `;
    }).join('');

    scoreHistoryDisplay.innerHTML = historyHTML;
}

// Timer Display Functions
function updateSimpleTimer(timerData) {
    if (!timerData || !timerData.timers) {
        console.log('updateSimpleTimer: No timer data, hiding clock');
        hidePopupClock();
        return;
    }

    // Show the timer during game
    if (document.getElementById('gameInterface').style.display !== 'none') {
        // Find the current turn player
        const currentTurnTimer = Object.entries(timerData.timers).find(([playerId, timer]) => timer.is_current_turn);

        if (currentTurnTimer) {
            const [playerId, timer] = currentTurnTimer;
            console.log(`updateSimpleTimer: Showing timer for player ${timer.player_name} (Final round: ${gameState.finalRound})`);
            showPopupClock(timer);
        } else {
            console.log('updateSimpleTimer: No current turn player found, hiding clock');
            hidePopupClock();
        }
    } else {
        console.log('updateSimpleTimer: Game interface not visible, hiding clock');
        hidePopupClock();
    }
}

function showPopupClock(timerData) {
    const popup = document.getElementById('timerClockPopup');
    const playerName = document.getElementById('clockPlayerName');
    const timerDisplay = document.getElementById('clockTimerDisplay');
    const progressCircle = document.getElementById('progressCircle');
    const progressPercentage = document.getElementById('progressPercentage');

    // Show popup
    popup.style.display = 'block';

    // Update player name
    playerName.textContent = timerData.player_name;

    // Update timer display
    const hasTimeLimit = timerData.time_limit !== null;
    let timerDisplayClass = '';
    let progressValue = 100;

    if (hasTimeLimit && timerData.remaining_time !== null) {
        const remainingSeconds = Math.max(0, timerData.remaining_time);
        const minutes = Math.floor(remainingSeconds / 60);
        const seconds = Math.floor(remainingSeconds % 60);
        timerDisplay.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

        // Calculate progress percentage
        progressValue = (remainingSeconds / timerData.time_limit) * 100;

        if (remainingSeconds <= 10) {
            timerDisplayClass = 'critical';
        } else if (remainingSeconds <= 30) {
            timerDisplayClass = 'warning';
        }
    } else {
        timerDisplay.textContent = '∞';
    }

    // Update display classes
    timerDisplay.className = `time-display ${timerDisplayClass}`;

    // Update progress ring
    updateProgressRing(progressValue, timerDisplayClass);
    progressPercentage.textContent = `${Math.round(progressValue)}%`;
}

function hidePopupClock() {
    const popup = document.getElementById('timerClockPopup');
    popup.style.display = 'none';
}

function updateProgressRing(percentage, statusClass = '') {
    const progressCircle = document.getElementById('progressCircle');
    const circumference = 2 * Math.PI * 20; // radius = 20 for the smaller ring
    const offset = circumference - (percentage / 100) * circumference;

    progressCircle.style.strokeDashoffset = offset;

    // Update color based on status
    progressCircle.className = `ring-progress ${statusClass}`;
}

function updateClockHands() {
    const now = new Date();
    const hours = now.getHours() % 12;
    const minutes = now.getMinutes();
    const seconds = now.getSeconds();

    // Calculate angles (360 degrees = 12 hours, 60 minutes, 60 seconds)
    const hourAngle = (hours * 30) + (minutes * 0.5); // 30 degrees per hour + minute adjustment
    const minuteAngle = minutes * 6; // 6 degrees per minute
    const secondAngle = seconds * 6; // 6 degrees per second

    // Apply rotations
    const hourHand = document.getElementById('hourHand');
    const minuteHand = document.getElementById('minuteHand');
    const secondHand = document.getElementById('secondHand');

    if (hourHand) hourHand.style.transform = `rotate(${hourAngle}deg)`;
    if (minuteHand) minuteHand.style.transform = `rotate(${minuteAngle}deg)`;
    if (secondHand) secondHand.style.transform = `rotate(${secondAngle}deg)`;
}

// Add event listener for close button
document.addEventListener('DOMContentLoaded', function () {
    const closeBtn = document.getElementById('closeTimerBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            hidePopupClock();
        });
    }
});

// Socket event handlers for new features
socket.on('game_reset_to_waiting', function (data) {
    console.log('Game reset to waiting:', data);

    // Switch to waiting room
    document.getElementById('gameInterface').style.display = 'none';
    document.getElementById('waitingRoom').style.display = 'block';
    setWaitingPanel('lobby');

    // Update player list and game info
    const allReady = getAllPlayersReady(data.players, data.players.length);
    updatePlayersList(data.players, data.players.length, allReady);
    syncLocalPlayerState(data.players);
    updateWaitingRoomButtons();
    updateGameSettings(data.game_settings);
    updateScoreHistory(data.score_history);

    // Clear timers
    clearInterval(timerInterval);
    timerInterval = null;
    stopTimerUpdates();
    hidePopupClock();

    showStatus('Game completed! Ready for next round.', 'success');
});

socket.on('all_timers_update', function (data) {
    updateSimpleTimer(data);
    // Ensure timer updates stay active during game
    ensureTimerUpdatesActive();
});

socket.on('game_info_update', function (data) {
    if (data.game_settings) {
        updateGameSettings(data.game_settings);
    }
    if (data.score_history) {
        updateScoreHistory(data.score_history);
    }
});

// Request game info when page loads
socket.emit('get_game_info');

// Request timer updates periodically during game
let timerUpdateInterval = null;

function startTimerUpdates() {
    if (timerUpdateInterval) {
        clearInterval(timerUpdateInterval);
    }
    timerUpdateInterval = setInterval(() => {
        if (document.getElementById('gameInterface').style.display !== 'none') {
            socket.emit('get_all_timers');
        }
    }, 1000);
    console.log('Timer updates started');
}

function stopTimerUpdates() {
    if (timerUpdateInterval) {
        clearInterval(timerUpdateInterval);
        timerUpdateInterval = null;
    }
    hidePopupClock();
    console.log('Timer updates stopped');
}

// Ensure timer updates are running during active game
function ensureTimerUpdatesActive() {
    if (document.getElementById('gameInterface').style.display !== 'none' && !timerUpdateInterval) {
        console.log('Timer updates were inactive during game, restarting...');
        startTimerUpdates();
    }
}
