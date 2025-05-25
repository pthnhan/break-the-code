from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import random
import uuid
import json
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'break_the_code_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

class BreakTheCodeGame:
    def __init__(self):
        self.rooms = {}
        
    def create_game_room(self, room_id, max_players=4, num_question_cards=4):
        """Create a new game room"""
        self.rooms[room_id] = {
            'players': {},
            'game_state': 'waiting',  # waiting, playing, finished
            'max_players': max_players,
            'num_question_cards': num_question_cards, # Store the number of question cards
            'current_turn': None,
            'tiles': self.create_tiles(),
            'question_cards': self.create_question_cards(),
            'center_cards': [],
            'used_question_cards': [],
            'host': None,  # Track room host
            'ready_players': set()  # Track ready players
        }
        
    def create_tiles(self):
        """Create the number tiles for the game"""
        tiles = []
        # Numbers 0-9 with white and black colors, except 5
        for number in range(10):
            if number != 5:  # Skip 5 for white and black
                tiles.append({'number': number, 'color': 'white'})
                tiles.append({'number': number, 'color': 'black'})
        
        # Two green 5s
        tiles.append({'number': 5, 'color': 'green'})
        tiles.append({'number': 5, 'color': 'green'})
        
        return tiles
    
    def create_question_cards(self):
        """Create question cards for deduction"""
        cards = [
            "How many **odd** tiles you have?",
            "Which neighbouring tiles have **consecutive numbers**?",
            "How many of **your tiles have the same number**?",
            "What is the **sum of your 3 left-most tiles**?",
            "What is the **sum of your 3 right-most tiles**?",
            "Where are your **#8** or **#9** tiles? **You must choose one number before asking that question**.",
            "Where are your **#1** or **#2** tiles? **You must choose one number before asking that question**.",
            "Where are your **#3** or **#4** tiles? **You must choose one number before asking that question**.",
            "Where are your **#6** or **#7** tiles? **You must choose one number before asking that question**.",
            "Is your **C tile greater than 4**?",
            "How many of your tiles have **a black number**?",
            "How many of your tiles have **a white number**?",
            "What is the **sum of your central tiles (B, C and D)**?",
            "What is the **sum of your tiles**?",
            "Where are your **#5** tiles?",
            "Which **neighboring tiles have the same color**?",
            "How many **even** tiles you have?",
            "Where are your **#0** tiles?",
            "What is the **difference between your highest and lowest numbers**?"
        ]
        return cards
    
    def distribute_tiles(self, room_id):
        """Distribute tiles to players based on player count"""
        room = self.rooms[room_id]
        player_count = len(room['players'])
        
        if player_count == 2:
            tiles_per_player = 5
            # No center tiles for 2 players
            room['center_tiles_count'] = 0
        elif player_count == 3:
            tiles_per_player = 5
            # 5 tiles go to center
            room['center_tiles_count'] = 5
        elif player_count == 4:
            tiles_per_player = 4
            # 4 tiles go to center
            room['center_tiles_count'] = 4
        else:
            return False
            
        # Shuffle tiles
        tiles = room['tiles'].copy()
        random.shuffle(tiles)
        
        # Distribute to players
        tile_index = 0
        for player_id in room['players']:
            player_tiles = tiles[tile_index:tile_index + tiles_per_player]
            # Sort tiles: numerically ascending, black before white for same number
            player_tiles.sort(key=lambda x: (x['number'], x['color'] == 'white'))
            room['players'][player_id]['tiles'] = player_tiles
            tile_index += tiles_per_player
            
        # Handle center tiles for 3-4 players
        if player_count >= 3:
            center_count = room['center_tiles_count']
            center_tiles = tiles[tile_index:tile_index + center_count]
            center_tiles.sort(key=lambda x: (x['number'], x['color'] == 'white'))
            room['center_tiles'] = center_tiles
            
        # Draw question cards for the center based on host's selection
        question_cards = room['question_cards'].copy()
        random.shuffle(question_cards)
        num_to_draw = room.get('num_question_cards', 4)  # Use stored value or default to 4
        room['available_questions'] = question_cards[:num_to_draw]
        room['used_question_cards'] = []  # Track used cards
        
        return True
    
    def join_room(self, room_id, player_id, player_name):
        """Add a player to a game room"""
        if room_id not in self.rooms:
            return False, "Room not found"
            
        room = self.rooms[room_id]
        if len(room['players']) >= room['max_players']:
            return False, "Room is full"
            
        if room['game_state'] != 'waiting':
            return False, "Game already started"
            
        room['players'][player_id] = {
            'name': player_name,
            'tiles': [],
            'guesses': [],
            'score': 0,  # Add scoring system
            'ready': False
        }
        
        return True, "Joined successfully"
    
    def set_player_ready(self, room_id, player_id, ready_status):
        """Set a player's ready status"""
        if room_id not in self.rooms:
            return False, "Room not found"
            
        room = self.rooms[room_id]
        if player_id not in room['players']:
            return False, "Player not in room"
            
        room['players'][player_id]['ready'] = ready_status
        if ready_status:
            room['ready_players'].add(player_id)
        else:
            room['ready_players'].discard(player_id)
            
        return True, "Ready status updated"
    
    def all_players_ready(self, room_id):
        """Check if all players are ready"""
        if room_id not in self.rooms:
            return False
            
        room = self.rooms[room_id]
        # At least 2 players and all are ready
        return len(room['players']) >= 2 and len(room['ready_players']) == len(room['players'])
    
    def start_game(self, room_id):
        """Start the game in a room"""
        room = self.rooms[room_id]
        if len(room['players']) < 2:
            return False, "Need at least 2 players"
            
        if self.distribute_tiles(room_id):
            room['game_state'] = 'playing'
            # Set first player's turn
            room['current_turn'] = list(room['players'].keys())[0]
            return True, "Game started"
        return False, "Failed to start game"

# Global game instance
game_manager = BreakTheCodeGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game/<room_id>')
def game_room(room_id):
    return render_template('game.html', room_id=room_id)

@socketio.on('create_room')
def handle_create_room(data):
    room_id = str(uuid.uuid4())[:8]
    player_name = data.get('player_name', 'Anonymous')
    max_players = data.get('max_players', 4)
    num_question_cards = data.get('num_question_cards', 4)  # Get from client
    
    game_manager.create_game_room(room_id, max_players, num_question_cards) # Pass to game creation
    
    player_id = str(uuid.uuid4())
    success, message = game_manager.join_room(room_id, player_id, player_name)
    
    if success:
        # Set this player as the host
        game_manager.rooms[room_id]['host'] = player_id
        
        # Automatically mark the host as ready
        game_manager.set_player_ready(room_id, player_id, True)
        
        join_room(room_id)
        session['player_id'] = player_id
        session['room_id'] = room_id
        
        emit('room_created', {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': player_name,
            'is_host': True,
            'message': 'Room created successfully'
        })
        
        # Send initial player state to the room
        emit('player_joined', {
            'players': list(game_manager.rooms[room_id]['players'].values()),
            'player_count': len(game_manager.rooms[room_id]['players']),
            'host_id': player_id
        }, room=room_id)
    else:
        emit('error', {'message': message})

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')
    player_name = data.get('player_name', 'Anonymous')
    
    print(f"Join room request: room_id={room_id}, player_name={player_name}")
    
    if room_id not in game_manager.rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    # Check if this player is already in the room (by session)
    existing_player_id = session.get('player_id')
    room = game_manager.rooms[room_id]
    
    print(f"Room {room_id} current players: {len(room['players'])}, max: {room['max_players']}")
    print(f"Existing player_id in session: {existing_player_id}")
    
    if existing_player_id and existing_player_id in room['players']:
        # Player already in room, just rejoin socket room
        print(f"Player {existing_player_id} rejoining room")
        join_room(room_id)
        session['room_id'] = room_id
        
        emit('room_joined', {
            'room_id': room_id,
            'player_id': existing_player_id,
            'player_name': room['players'][existing_player_id]['name'],
            'message': 'Rejoined successfully'
        })
        
        emit('player_joined', {
            'players': list(room['players'].values()),
            'player_count': len(room['players'])
        }, room=room_id)
        return
    
    # New player joining
    player_id = str(uuid.uuid4())
    print(f"Creating new player {player_id} with name {player_name}")
    success, message = game_manager.join_room(room_id, player_id, player_name)
    
    print(f"Join result: success={success}, message={message}")
    
    if success:
        join_room(room_id)
        session['player_id'] = player_id
        session['room_id'] = room_id
        
        print(f"Player {player_id} successfully joined. Room now has {len(game_manager.rooms[room_id]['players'])} players")
        
        emit('room_joined', {
            'room_id': room_id,
            'player_id': player_id,
            'player_name': player_name,
            'message': message
        })
        
        emit('player_joined', {
            'players': list(game_manager.rooms[room_id]['players'].values()),
            'player_count': len(game_manager.rooms[room_id]['players'])
        }, room=room_id)
    else:
        print(f"Failed to join room: {message}")
        emit('error', {'message': message})

@socketio.on('player_ready')
def handle_player_ready(data):
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    ready_status = data.get('ready', False)
    
    if not room_id or room_id not in game_manager.rooms:
        emit('error', {'message': 'Invalid room'})
        return
    
    success, message = game_manager.set_player_ready(room_id, player_id, ready_status)
    
    if success:
        room = game_manager.rooms[room_id]
        
        # Broadcast updated player states
        emit('player_ready_update', {
            'player_id': player_id,
            'player_name': room['players'][player_id]['name'],
            'ready': ready_status,
            'all_ready': game_manager.all_players_ready(room_id),
            'players': [{
                'id': pid,
                'name': room['players'][pid]['name'],
                'ready': room['players'][pid]['ready'],
                'score': room['players'][pid]['score']
            } for pid in room['players']]
        }, room=room_id)
    else:
        emit('error', {'message': message})

@socketio.on('start_game')
def handle_start_game():
    print(f"Start game request received from session: {dict(session)}")
    
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    
    print(f"Start game: room_id={room_id}, player_id={player_id}")
    
    if not room_id or room_id not in game_manager.rooms:
        print(f"Invalid room: room_id={room_id}, rooms available: {list(game_manager.rooms.keys())}")
        emit('error', {'message': 'Invalid room'})
        return
    
    room = game_manager.rooms[room_id]
    
    # Check if player is the host
    if room['host'] != player_id:
        emit('error', {'message': 'Only the host can start the game'})
        return
    
    # Check if all players are ready
    if not game_manager.all_players_ready(room_id):
        emit('error', {'message': 'All players must be ready before starting the game'})
        return
    
    print(f"Room {room_id} has {len(room['players'])} players: {[p['name'] for p in room['players'].values()]}")
    
    success, message = game_manager.start_game(room_id)
    print(f"Start game result: success={success}, message={message}")
    
    if success:
        room = game_manager.rooms[room_id]
        
        print(f"Game started successfully, sending game data to {len(room['players'])} players")
        
        # Send personalized game state to each player
        for player_id in room['players']:
            player_data = {
                'tiles': room['players'][player_id]['tiles'],
                'available_questions': room['available_questions'],
                'player_count': len(room['players']),
                'current_turn': room['current_turn'],
                'game_state': 'playing',
                'your_player_id': player_id,
                'all_players': {pid: {'name': room['players'][pid]['name']} for pid in room['players'] if pid != player_id}
            }
            
            if len(room['players']) >= 3 and 'center_tiles_count' in room:
                player_data['center_tiles_count'] = room['center_tiles_count']
            
            print(f"Sending game_started to player {player_id} ({room['players'][player_id]['name']})")
            
        # Send game_started event to the entire room, but each client will only see their own data
        # We'll send a generic event first, then personalized data
        emit('game_started', {
            'message': 'Game has started!',
            'player_count': len(room['players']),
            'available_questions': room['available_questions'],
            'current_turn': room['current_turn'],
            'game_state': 'playing'
        }, room=room_id)
        
        # Now send personalized data to each player individually using their session
        # We need to get the session ID for each player and emit to them specifically
        # For now, let's emit to the room with the assumption that each client will filter their own data
        for player_id in room['players']:
            player_data = {
                'tiles': room['players'][player_id]['tiles'],
                'available_questions': room['available_questions'],
                'player_count': len(room['players']),
                'current_turn': room['current_turn'],
                'game_state': 'playing',
                'your_player_id': player_id,
                'all_players': {pid: {'name': room['players'][pid]['name']} for pid in room['players'] if pid != player_id}
            }
            
            if len(room['players']) >= 3 and 'center_tiles_count' in room:
                player_data['center_tiles_count'] = room['center_tiles_count']
            
            # Emit personalized data with player_id so client can check if it's for them
            emit('player_game_data', player_data, room=room_id)
    else:
        print(f"Failed to start game: {message}")
        emit('error', {'message': message})

@socketio.on('ask_question')
def handle_ask_question(data):
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    question_index = data.get('question_index')
    chosen_number = data.get('chosen_number')  # Optional parameter for questions requiring number choice
    
    if not room_id or room_id not in game_manager.rooms:
        emit('error', {'message': 'Invalid room'})
        return
    
    room = game_manager.rooms[room_id]
    
    # Check if it's the player's turn
    if room.get('current_turn') != player_id:
        emit('error', {'message': "It's not your turn!"})
        return
    
    # Check if game is in final round
    if room.get('final_round'):
        emit('error', {'message': 'Questions cannot be asked during final round!'})
        return
    
    if question_index < 0 or question_index >= len(room['available_questions']):
        emit('error', {'message': 'Invalid question'})
        return
    
    question = room['available_questions'][question_index]
    
    # Check if this question requires a number choice
    if "You must choose one number before asking that question" in question and chosen_number is None:
        emit('error', {'message': 'This question requires you to choose a number first!'})
        return
    
    # Calculate answers for ALL other players
    all_answers = {}
    asking_player_name = room['players'][player_id]['name']
    
    for target_player_id in room['players']:
        if target_player_id != player_id:  # Don't ask the question to yourself
            target_tiles = room['players'][target_player_id]['tiles']
            answer = calculate_answer(question, target_tiles, chosen_number)
            all_answers[target_player_id] = {
                'name': room['players'][target_player_id]['name'],
                'answer': answer
            }
    
    # Broadcast question and all answers to all players
    question_display = question
    if chosen_number is not None:
        question_display = f"{question} (Chosen number: {chosen_number})"
    
    emit('question_asked', {
        'question': question_display,
        'answers': all_answers,
        'asking_player': asking_player_name
    }, room=room_id)
    
    # Remove used question and add to used pile
    used_question = room['available_questions'].pop(question_index)
    room['used_question_cards'].append(used_question)
    
    # Try to replace with a new question from the remaining deck
    remaining_questions = [q for q in room['question_cards'] if q not in room['used_question_cards'] and q not in room['available_questions']]
    
    new_question_added = False
    if remaining_questions:
        # Add a new random question from the remaining deck
        new_question = random.choice(remaining_questions)
        room['available_questions'].append(new_question)
        new_question_added = True
    
    # Always broadcast updated questions to all players (even if no new question was added)
    emit('questions_updated', {
        'available_questions': room['available_questions'],
        'new_question_added': new_question_added,
        'total_questions_remaining': len(room['available_questions'])
    }, room=room_id)
    
    # Move to next player's turn
    players = list(room['players'].keys())
    current_index = players.index(player_id)
    next_index = (current_index + 1) % len(players)
    room['current_turn'] = players[next_index]
    
    emit('turn_changed', {
        'current_turn': room['current_turn'],
        'current_player_name': room['players'][room['current_turn']]['name']
    }, room=room_id)

def calculate_answer(question, tiles, chosen_number=None):
    """Calculate the answer to a question based on tiles"""
    
    # Handle questions that require a chosen number
    if "You must choose one number before asking that question" in question:
        if chosen_number is None:
            return "Error: Number not chosen"
            
        # Extract the target numbers from the question
        if "#8** or **#9" in question and chosen_number in [8, 9]:
            target_positions = []
            for i, tile in enumerate(tiles):
                if tile['number'] == chosen_number:
                    position = chr(65 + i)  # Convert to A, B, C, D, E
                    target_positions.append(position)
            return f"Position(s): {', '.join(target_positions)}" if target_positions else "Not found"
            
        elif "#1** or **#2" in question and chosen_number in [1, 2]:
            target_positions = []
            for i, tile in enumerate(tiles):
                if tile['number'] == chosen_number:
                    position = chr(65 + i)  # Convert to A, B, C, D, E
                    target_positions.append(position)
            return f"Position(s): {', '.join(target_positions)}" if target_positions else "Not found"
            
        elif "#3** or **#4" in question and chosen_number in [3, 4]:
            target_positions = []
            for i, tile in enumerate(tiles):
                if tile['number'] == chosen_number:
                    position = chr(65 + i)  # Convert to A, B, C, D, E
                    target_positions.append(position)
            return f"Position(s): {', '.join(target_positions)}" if target_positions else "Not found"
            
        elif "#6** or **#7" in question and chosen_number in [6, 7]:
            target_positions = []
            for i, tile in enumerate(tiles):
                if tile['number'] == chosen_number:
                    position = chr(65 + i)  # Convert to A, B, C, D, E
                    target_positions.append(position)
            return f"Position(s): {', '.join(target_positions)}" if target_positions else "Not found"
        else:
            return "Error: Invalid number choice"
    
    # Handle simple counting questions
    if "How many **odd** tiles you have" in question:
        return len([t for t in tiles if t['number'] % 2 == 1])
    elif "How many **even** tiles you have" in question:
        return len([t for t in tiles if t['number'] % 2 == 0])
    elif "How many of **your tiles have the same number**" in question:
        from collections import Counter
        numbers = [t['number'] for t in tiles]
        counts = Counter(numbers)
        return sum(count - 1 for count in counts.values() if count > 1)
    elif "How many of your tiles have **a black number**" in question:
        return len([t for t in tiles if t['color'] == 'black'])
    elif "How many of your tiles have **a white number**" in question:
        return len([t for t in tiles if t['color'] == 'white'])
    
    # Handle position-based questions
    elif "Which neighbouring tiles have **consecutive numbers**" in question:
        consecutive_pairs = []
        for i in range(len(tiles) - 1):
            current_num = tiles[i]['number']
            next_num = tiles[i + 1]['number']
            if abs(current_num - next_num) == 1:
                pos1 = chr(65 + i)
                pos2 = chr(65 + i + 1)
                consecutive_pairs.append(f"{pos1}-{pos2}")
        return ", ".join(consecutive_pairs) if consecutive_pairs else "None"
    
    elif "Which **neighboring tiles have the same color**" in question:
        same_color_pairs = []
        for i in range(len(tiles) - 1):
            current_color = tiles[i]['color']
            next_color = tiles[i + 1]['color']
            if current_color == next_color:
                pos1 = chr(65 + i)
                pos2 = chr(65 + i + 1)
                same_color_pairs.append(f"{pos1}-{pos2}")
        return ", ".join(same_color_pairs) if same_color_pairs else "None"
    
    # Handle sum questions
    elif "What is the **sum of your 3 left-most tiles**" in question:
        left_tiles = tiles[:3] if len(tiles) >= 3 else tiles
        return sum(t['number'] for t in left_tiles)
    elif "What is the **sum of your 3 right-most tiles**" in question:
        right_tiles = tiles[-3:] if len(tiles) >= 3 else tiles
        return sum(t['number'] for t in right_tiles)
    elif "What is the **sum of your central tiles (B, C and D)**" in question:
        if len(tiles) >= 5:
            central_tiles = tiles[1:4]  # Positions B, C, D (indices 1, 2, 3)
            return sum(t['number'] for t in central_tiles)
        elif len(tiles) >= 3:
            # For 4-player mode with 4 tiles, central would be B and C
            central_tiles = tiles[1:3]
            return sum(t['number'] for t in central_tiles)
        else:
            return "Not applicable"
    elif "What is the **sum of your tiles**" in question:
        return sum(t['number'] for t in tiles)
    
    # Handle specific position questions
    elif "Where are your **#5** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile['number'] == 5:
                position = chr(65 + i)  # Convert to A, B, C, D, E
                positions.append(position)
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"
    
    elif "Where are your **#0** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile['number'] == 0:
                position = chr(65 + i)  # Convert to A, B, C, D, E
                positions.append(position)
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"
    
    elif "Is your **C tile greater than 4**" in question:
        if len(tiles) >= 3:
            c_tile = tiles[2]  # Position C is index 2
            return "Yes" if c_tile['number'] > 4 else "No"
        else:
            return "Not applicable"
    
    # Handle mathematical questions
    elif "What is the **difference between your highest and lowest numbers**" in question:
        numbers = [t['number'] for t in tiles]
        return max(numbers) - min(numbers) if numbers else 0
    
    # Fallback for unrecognized questions
    return "Unknown question"

@socketio.on('make_guess')
def handle_make_guess(data):
    room_id = session.get('room_id')
    player_id = session.get('player_id')
    guess = data.get('guess')
    guess_type = data.get('guess_type', 'center')
    
    print(f"Guess received from {game_manager.rooms[room_id]['players'][player_id]['name']}: {guess}, type: {guess_type}")
    
    if not room_id or room_id not in game_manager.rooms:
        emit('error', {'message': 'Invalid room'})
        return
    
    room = game_manager.rooms[room_id]
    
    # Check turn validation
    if room.get('final_round'):
        # In final round, only the final round player can guess
        if room.get('final_round_player') != player_id:
            emit('error', {'message': 'Only the final round player can make guesses now!'})
            return
    else:
        # Normal round, check if it's the player's turn
        if room.get('current_turn') != player_id:
            emit('error', {'message': "It's not your turn!"})
            return
    
    player_count = len(room['players'])
    
    # Validate guess length based on game mode
    expected_length = get_expected_guess_length(player_count, guess_type)
    if len(guess) != expected_length:
        emit('error', {'message': f'Guess must have exactly {expected_length} tiles'})
        return
    
    # Check guess correctness based on game mode
    is_correct = False
    target_tiles = []
    
    if player_count == 2:
        # 2-player mode: guess another player's tiles
        if guess_type in room['players'] and guess_type != player_id:
            target_tiles = room['players'][guess_type]['tiles']
            is_correct = check_guess_correctness(guess, target_tiles)
            target_name = room['players'][guess_type]['name']
        else:
            emit('error', {'message': 'Invalid target player for guess'})
            return
    else:
        # 3-4 player mode: guess center tiles
        if guess_type == 'center':
            target_tiles = room['center_tiles']
            is_correct = check_guess_correctness(guess, target_tiles)
            target_name = "center tiles"
        else:
            emit('error', {'message': 'Invalid guess type for this game mode'})
            return
    
    # Store the guess result with timestamp for ordering
    timestamp = time.time()
    room['players'][player_id]['guesses'].append({
        'guess': guess,
        'target': guess_type,
        'correct': is_correct,
        'timestamp': timestamp
    })
    
    # Track first successful guess for win condition logic
    if is_correct and not room.get('first_successful_guess'):
        room['first_successful_guess'] = {
            'player_id': player_id,
            'timestamp': timestamp,
            'player_name': room['players'][player_id]['name']
        }
    
    # Broadcast the guess to all players
    emit('guess_made', {
        'player': room['players'][player_id]['name'],
        'guess': guess,
        'target': target_name,
        'correct': is_correct,
        'actual_tiles': target_tiles if is_correct else None
    }, room=room_id)
    
    # Check for game ending conditions with new logic
    if player_count == 2:
        check_two_player_win_condition_new(room_id, player_id, is_correct)
    else:
        check_center_guess_win_condition_new(room_id, player_id, is_correct)

def get_expected_guess_length(player_count, guess_type):
    """Get expected number of tiles in a guess"""
    if player_count == 2:
        return 5  # Each player has 5 tiles
    elif player_count == 3:
        return 5  # Center has 5 tiles
    elif player_count == 4:
        return 4  # Center has 4 tiles
    return 0

def check_guess_correctness(guess, target_tiles):
    """Check if a guess matches the target tiles exactly"""
    if len(guess) != len(target_tiles):
        return False
    
    # Convert both to comparable format and sort
    guess_tiles = [{'number': tile['number'], 'color': tile['color']} for tile in guess]
    target_tiles_copy = [{'number': tile['number'], 'color': tile['color']} for tile in target_tiles]
    
    # Sort both lists the same way for comparison
    guess_tiles.sort(key=lambda x: (x['number'], x['color']))
    target_tiles_copy.sort(key=lambda x: (x['number'], x['color']))
    
    return guess_tiles == target_tiles_copy

def update_player_scores(room_id, winners, is_draw):
    """Update player scores based on game results"""
    room = game_manager.rooms[room_id]
    
    if not is_draw:
        # Winners get +1 point
        for winner_id in winners:
            if winner_id in room['players']:
                room['players'][winner_id]['score'] += 1
    # For draws, no points are awarded

def reset_game_for_next_round(room_id):
    """Reset game state for next round while preserving scores and players"""
    room = game_manager.rooms[room_id]
    
    # Reset game state
    room['game_state'] = 'waiting'
    room['current_turn'] = None
    room['final_round'] = False
    room['final_round_player'] = None
    room['first_successful_guess'] = None
    room['winners'] = None
    room['center_tiles'] = []
    room['center_tiles_count'] = 0
    room['used_question_cards'] = []
    
    # Reset player game data but keep scores and names
    for player_id in room['players']:
        player = room['players'][player_id]
        player['tiles'] = []
        player['guesses'] = []
        player['ready'] = False
        player.pop('correct_guess', None)
        player.pop('guess_timestamp', None)
        player.pop('center_guess_correct', None)
    
    # Reset ready players
    room['ready_players'] = set()
    
    # Auto-mark host as ready if exists
    if room.get('host') and room['host'] in room['players']:
        room['players'][room['host']]['ready'] = True
        room['ready_players'].add(room['host'])

def check_two_player_win_condition_new(room_id, guessing_player_id, is_correct):
    """Check win condition for 2-player game with new logic"""
    room = game_manager.rooms[room_id]
    players = list(room['players'].keys())
    
    # Determine player order: first joined is player 1, second is player 2
    player_1 = players[0]
    player_2 = players[1]
    
    # Check if we're already in final round
    if room.get('final_round'):
        # We're in final round, this must be player 2's final guess
        if guessing_player_id == player_2:
            room['game_state'] = 'finished'
            if is_correct:
                # Both players guessed correctly - it's a draw
                room['winners'] = [player_1, player_2]
                update_player_scores(room_id, [player_1, player_2], is_draw=True)
                emit('game_ended', {
                    'winners': [room['players'][pid]['name'] for pid in [player_1, player_2]],
                    'message': 'Both players guessed correctly! It\'s a draw!',
                    'is_draw': True,
                    'redirect_to_waiting': True
                }, room=room_id)
            else:
                # Only player 1 guessed correctly - player 1 wins
                room['winners'] = [player_1]
                update_player_scores(room_id, [player_1], is_draw=False)
                emit('game_ended', {
                    'winners': [room['players'][player_1]['name']],
                    'message': f"{room['players'][player_1]['name']} wins!",
                    'is_draw': False,
                    'redirect_to_waiting': True
                }, room=room_id)
            # Reset game for next round
            reset_game_for_next_round(room_id)
        return
    
    # Not in final round yet - only process correct guesses
    if is_correct:
        # Someone guessed correctly, mark them as having a correct guess
        room['players'][guessing_player_id]['correct_guess'] = True
        room['players'][guessing_player_id]['guess_timestamp'] = time.time()
        
        if guessing_player_id == player_2:
            # Player 2 guessed correctly first - immediate win, game ends
            room['game_state'] = 'finished'
            room['winners'] = [player_2]
            update_player_scores(room_id, [player_2], is_draw=False)
            
            emit('game_ended', {
                'winners': [room['players'][player_2]['name']],
                'message': f"{room['players'][player_2]['name']} wins! Game over.",
                'is_draw': False,
                'redirect_to_waiting': True
            }, room=room_id)
            # Reset game for next round
            reset_game_for_next_round(room_id)
            return
            
        elif guessing_player_id == player_1:
            # Player 1 guessed correctly first - give player 2 a final chance
            room['final_round'] = True
            room['final_round_player'] = player_2  # Only player 2 can guess now
            room['current_turn'] = player_2  # Set turn to final round player
            
            emit('final_round_started', {
                'message': f"{room['players'][player_1]['name']} guessed correctly! {room['players'][player_2]['name']} has one final chance to guess.",
                'first_winner': room['players'][player_1]['name'],
                'final_player': player_2,
                'final_player_name': room['players'][player_2]['name']
            }, room=room_id)
            
            # Also emit turn changed event to update the UI
            emit('turn_changed', {
                'current_turn': room['current_turn'],
                'current_player_name': room['players'][room['current_turn']]['name'],
                'final_round': True,
                'final_round_player': player_2
            }, room=room_id)
            return

def check_center_guess_win_condition_new(room_id, guessing_player_id, is_correct):
    """Check win condition for 3-4 player game with center guessing"""
    room = game_manager.rooms[room_id]
    
    if is_correct:
        # Someone guessed center correctly, mark them as having a correct guess
        room['players'][guessing_player_id]['center_guess_correct'] = True
        
        # Check if this is the first correct center guess
        first_correct = True
        for player_id in room['players']:
            if player_id != guessing_player_id and room['players'][player_id].get('center_guess_correct'):
                first_correct = False
                break
        
        if first_correct:
            # First correct guess - give others a chance to guess
            room['final_round'] = True
            emit('final_round_started', {
                'message': f"{room['players'][guessing_player_id]['name']} guessed the center correctly! Other players can still make their final guess.",
                'first_winner': room['players'][guessing_player_id]['name']
            }, room=room_id)
            return
    
    # Check if we're in final round and all players have guessed
    if room.get('final_round'):
        all_guessed = True
        for player_id in room['players']:
            player_data = room['players'][player_id]
            if not player_data.get('center_guess_correct') and not any(g.get('target') == 'center' for g in player_data['guesses']):
                all_guessed = False
                break
        
        if all_guessed:
            # Final round complete - determine winners
            winners = [pid for pid in room['players'] if room['players'][pid].get('center_guess_correct')]
            
            room['game_state'] = 'finished'
            room['winners'] = winners
            
            # Update scores
            is_draw = len(winners) > 1
            update_player_scores(room_id, winners, is_draw)
            
            emit('game_ended', {
                'winners': [room['players'][pid]['name'] for pid in winners],
                'message': f"Game ended! Winners: {', '.join([room['players'][pid]['name'] for pid in winners])}",
                'is_draw': is_draw,
                'redirect_to_waiting': True
            }, room=room_id)
            # Reset game for next round
            reset_game_for_next_round(room_id)

@socketio.on('get_room_state')
def handle_get_room_state(data):
    room_id = data.get('room_id')
    player_id = data.get('player_id')
    
    print(f"Get room state request: room_id={room_id}, player_id={player_id}")
    
    if not room_id or room_id not in game_manager.rooms:
        emit('error', {'message': 'Room not found'})
        return
    
    room = game_manager.rooms[room_id]
    print(f"Room {room_id} has {len(room['players'])} players: {[p['name'] for p in room['players'].values()]}")
    
    # Check if player_id exists and is in room
    if player_id and player_id in room['players']:
        # Existing player (room creator) reconnecting
        print(f"Player {player_id} ({room['players'][player_id]['name']}) reconnecting to room")
        join_room(room_id)
        session['player_id'] = player_id
        session['room_id'] = room_id
        
        emit('room_joined', {
            'room_id': room_id,
            'player_id': player_id,
            'message': 'Connected to room successfully'
        })
        
        emit('player_joined', {
            'players': list(room['players'].values()),
            'player_count': len(room['players'])
        }, room=room_id)
    else:
        # Player not found in session or room
        print(f"Player {player_id} not found in room {room_id}")
        emit('error', {'message': 'Player not found in room'})
        return

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 