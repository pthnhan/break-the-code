import os
import json
import random
import time
import uuid

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "break_the_code_secret_key_2024")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")


class BreakTheCodeGame:
    def __init__(self):
        self.rooms = {}

    def create_game_room(
        self,
        room_id,
        max_players=4,
        num_question_cards=4,
        time_limit="unlimited",
        custom_time=None,
        penalty_mode="for_fun",
    ):
        """Create a new game room"""
        # Calculate actual time limit in seconds
        if time_limit == "unlimited":
            actual_time_limit = None
        elif time_limit == "custom":
            actual_time_limit = int(custom_time) * 60 if custom_time else None
        else:
            actual_time_limit = int(time_limit)

        self.rooms[room_id] = {
            "players": {},
            "player_order": [],  # Track custom player order
            "game_state": "waiting",  # waiting, playing, finished
            "max_players": max_players,
            "num_question_cards": num_question_cards,  # Store the number of question cards
            "current_turn": None,
            "tiles": self.create_tiles(),
            "question_cards": [],
            "center_cards": [],
            "used_question_cards": [],
            "host": None,  # Track room host
            "ready_players": set(),  # Track ready players
            "time_limit": actual_time_limit,  # Time limit in seconds or None for unlimited
            "penalty_mode": penalty_mode,  # 'for_fun', 'manual'
            "turn_start_time": None,  # Track when current turn started
            "turn_timers": {},  # Track individual player turn times (for display purposes)
            "player_penalties": {},  # Track accumulated penalties per player
            "player_turn_start_times": {},  # Track individual player turn start times
            "score_history": [],  # Track score changes through rounds
            "round_number": 0,  # Track current round number
            "game_settings": {  # Store game settings for display
                "max_players": max_players,
                "num_question_cards": num_question_cards,
                "time_limit": actual_time_limit,
                "penalty_mode": penalty_mode,
                "time_limit_display": time_limit,
                "custom_time": custom_time,
            },
        }

    def create_tiles(self):
        """Create the number tiles for the game"""
        tiles = []
        # Numbers 0-9 with white and black colors, except 5
        for number in range(10):
            if number != 5:  # Skip 5 for white and black
                tiles.append({"number": number, "color": "white"})
                tiles.append({"number": number, "color": "black"})

        # Two green 5s
        tiles.append({"number": 5, "color": "green"})
        tiles.append({"number": 5, "color": "green"})

        return tiles

    def create_question_cards(self, player_count):
        """Create question cards for deduction"""
        if player_count >= 4:
            left_sum_question = "What is the **sum of your two left-most tiles (A, B)**?"
            right_sum_question = "What is the **sum of your two right-most tiles (C, D)**?"
            central_sum_question = "What is the **sum of your central tiles (B, C)**?"
        else:
            left_sum_question = "What is the **sum of your three left-most tiles (A, B, C)**?"
            right_sum_question = "What is the **sum of your three right-most tiles (C, D, E)**?"
            central_sum_question = "What is the **sum of your central tiles (B, C, D)**?"

        cards = [
            "How many **odd** tiles you have?",
            "Which neighbouring tiles have **consecutive numbers**?",
            "How many of **your tiles have the same number**?",
            left_sum_question,
            right_sum_question,
            "Where are your **#8** or **#9** tiles? **You must choose one number before asking that question**.",
            "Where are your **#1** or **#2** tiles? **You must choose one number before asking that question**.",
            "Where are your **#3** or **#4** tiles? **You must choose one number before asking that question**.",
            "Where are your **#6** or **#7** tiles? **You must choose one number before asking that question**.",
            "Is your **C tile greater than 4**?",
            "How many of your tiles have **a black number**?",
            "How many of your tiles have **a white number**?",
            central_sum_question,
            "What is the **sum of your tiles**?",
            "Where are your **#5** tiles?",
            "Which **neighboring tiles have the same color**?",
            "How many **even** tiles you have?",
            "Where are your **#0** tiles?",
            "What is the **difference between your highest and lowest numbers**?",
        ]
        return cards

    def distribute_tiles(self, room_id):
        """Distribute tiles to players based on player count"""
        room = self.rooms[room_id]
        player_count = len(room["players"])

        if player_count == 2:
            tiles_per_player = 5
            # No center tiles for 2 players
            room["center_tiles_count"] = 0
        elif player_count == 3:
            tiles_per_player = 5
            # 5 tiles go to center
            room["center_tiles_count"] = 5
        elif player_count == 4:
            tiles_per_player = 4
            # 4 tiles go to center
            room["center_tiles_count"] = 4
        else:
            return False

        # Shuffle tiles
        tiles = room["tiles"].copy()
        random.shuffle(tiles)

        # Distribute to players
        tile_index = 0
        for player_id in room["players"]:
            player_tiles = tiles[tile_index : tile_index + tiles_per_player]
            # Sort tiles: numerically ascending, black before white for same number
            player_tiles.sort(key=lambda x: (x["number"], x["color"] == "white"))
            room["players"][player_id]["tiles"] = player_tiles
            tile_index += tiles_per_player

        # Handle center tiles for 3-4 players
        if player_count >= 3:
            center_count = room["center_tiles_count"]
            center_tiles = tiles[tile_index : tile_index + center_count]
            center_tiles.sort(key=lambda x: (x["number"], x["color"] == "white"))
            room["center_tiles"] = center_tiles

        # Draw question cards for the center based on host's selection
        room["question_cards"] = self.create_question_cards(player_count)
        question_cards = room["question_cards"].copy()
        random.shuffle(question_cards)
        num_to_draw = room.get(
            "num_question_cards", 4
        )  # Use stored value or default to 4
        room["available_questions"] = question_cards[:num_to_draw]
        room["used_question_cards"] = []  # Track used cards

        return True

    def join_room(self, room_id, player_id, player_name):
        """Add a player to a game room"""
        if room_id not in self.rooms:
            return False, "Room not found"

        room = self.rooms[room_id]
        if len(room["players"]) >= room["max_players"]:
            return False, "Room is full"

        if room["game_state"] != "waiting":
            return False, "Game already started"

        # Check for duplicate names
        existing_names = [
            player["name"].lower().strip() for player in room["players"].values()
        ]
        if player_name.lower().strip() in existing_names:
            return False, "A player with this name already exists in the room"

        room["players"][player_id] = {
            "name": player_name,
            "tiles": [],
            "guesses": [],
            "score": 0,  # Add scoring system
            "ready": False,
            "connected": True,  # Track connection status
            "session_key": str(uuid.uuid4()),  # Unique session key for security
            "socket_sid": None,  # Track the latest active socket for this player
        }

        # Add player to the order list
        room["player_order"].append(player_id)

        return True, "Joined successfully"

    def reconnect_player(self, room_id, player_id, session_key, socket_sid=None):
        """Reconnect a player using their session key"""
        if room_id not in self.rooms:
            return False, "Room not found"

        room = self.rooms[room_id]
        if player_id not in room["players"]:
            return False, "Player not found in room"

        player = room["players"][player_id]
        if player.get("session_key") != session_key:
            return False, "Invalid session key"

        # Mark player as connected
        player["connected"] = True
        if socket_sid is not None:
            player["socket_sid"] = socket_sid
        return True, "Reconnected successfully"

    def set_player_socket(self, room_id, player_id, socket_sid):
        """Associate the current active socket with a player"""
        if room_id not in self.rooms:
            return False

        room = self.rooms[room_id]
        if player_id not in room["players"]:
            return False

        player = room["players"][player_id]
        player["connected"] = True
        player["socket_sid"] = socket_sid
        return True

    def disconnect_player(self, room_id, player_id, socket_sid=None):
        """Mark a player as disconnected"""
        if room_id not in self.rooms:
            return False

        room = self.rooms[room_id]
        if player_id in room["players"]:
            player = room["players"][player_id]
            active_sid = player.get("socket_sid")

            # Ignore disconnects from stale sockets. This happens during fast
            # reconnects or page transitions where an old socket closes after a
            # new one is already active for the same player.
            if (
                socket_sid is not None
                and active_sid is not None
                and active_sid != socket_sid
            ):
                return False

            player["connected"] = False
            if socket_sid is None or active_sid == socket_sid:
                player["socket_sid"] = None
            return True
        return False

    def reorder_players(self, room_id, new_order, requesting_player_id):
        """Reorder players in the room (only host can do this)"""
        if room_id not in self.rooms:
            return False, "Room not found"

        room = self.rooms[room_id]

        # Check if requesting player is the host
        if room["host"] != requesting_player_id:
            return False, "Only the host can reorder players"

        # Check if game is not already started
        if room["game_state"] != "waiting":
            return False, "Cannot reorder players after game has started"

        # Validate that new_order contains all current players
        current_players = set(room["player_order"])
        new_order_set = set(new_order)

        if current_players != new_order_set:
            return False, "Invalid player order - must include all current players"

        # Update the player order
        room["player_order"] = new_order
        return True, "Player order updated successfully"

    def remove_player(self, room_id, requesting_player_id, target_player_id):
        """Remove a player from a waiting room (host only)."""
        if room_id not in self.rooms:
            return False, "Room not found", None

        room = self.rooms[room_id]

        if room["host"] != requesting_player_id:
            return False, "Only the host can remove players", None

        if room["game_state"] != "waiting":
            return False, "Players can only be removed before the game starts", None

        if target_player_id not in room["players"]:
            return False, "Player not found", None

        if target_player_id == requesting_player_id:
            return False, "The host cannot remove themselves", None

        removed_player = room["players"].pop(target_player_id)
        room["player_order"] = [
            player_id for player_id in room["player_order"] if player_id != target_player_id
        ]
        room["ready_players"].discard(target_player_id)
        room["player_penalties"].pop(target_player_id, None)
        room["player_turn_start_times"].pop(target_player_id, None)
        room["turn_timers"].pop(target_player_id, None)

        return True, "Player removed successfully", removed_player

    def set_player_ready(self, room_id, player_id, ready_status):
        """Set a player's ready status"""
        if room_id not in self.rooms:
            return False, "Room not found"

        room = self.rooms[room_id]
        if player_id not in room["players"]:
            return False, "Player not in room"

        room["players"][player_id]["ready"] = ready_status
        if ready_status:
            room["ready_players"].add(player_id)
        else:
            room["ready_players"].discard(player_id)

        return True, "Ready status updated"

    def all_players_ready(self, room_id):
        """Check if all players are ready"""
        if room_id not in self.rooms:
            return False

        room = self.rooms[room_id]
        # At least 2 players and all are ready
        return len(room["players"]) >= 2 and len(room["ready_players"]) == len(
            room["players"]
        )

    def start_game(self, room_id):
        """Start the game in a room"""
        room = self.rooms[room_id]
        if room["game_state"] != "waiting":
            return False, "Game is already in progress"

        if len(room["players"]) < 2:
            return False, "Need at least 2 players"

        if self.distribute_tiles(room_id):
            room["game_state"] = "playing"
            # Set first player's turn using the custom order
            room["current_turn"] = room["player_order"][0]
            # Start timer for the first player
            self.start_turn_timer(room_id, room["current_turn"])
            return True, "Game started"
        return False, "Failed to start game"

    def start_turn_timer(self, room_id, player_id):
        """Start timer for a player's turn"""
        room = self.rooms[room_id]
        if room["time_limit"] is not None:
            # Store individual player turn start time
            if "player_turn_start_times" not in room:
                room["player_turn_start_times"] = {}

            current_time = time.time()
            room["player_turn_start_times"][player_id] = current_time
            print(
                f"DEBUG: Started timer for {room['players'][player_id]['name']} (ID: {player_id}) at {current_time}"
            )

            # Also store in turn_timers for compatibility
            if player_id not in room["turn_timers"]:
                room["turn_timers"][player_id] = 0

    def get_remaining_time(self, room_id, player_id):
        """Get remaining time for current turn"""
        room = self.rooms[room_id]
        if room["time_limit"] is None:
            return None  # Unlimited time

        if (
            "player_turn_start_times" not in room
            or player_id not in room["player_turn_start_times"]
        ):
            return room["time_limit"]

        elapsed = time.time() - room["player_turn_start_times"][player_id]
        remaining = room["time_limit"] - elapsed
        return max(0, remaining)

    def check_time_violation(self, room_id, player_id):
        """Check if player exceeded time limit and apply penalty"""
        room = self.rooms[room_id]
        if room["time_limit"] is None:
            return False, "unlimited"

        if (
            "player_turn_start_times" not in room
            or player_id not in room["player_turn_start_times"]
        ):
            return False, "no_timer"

        elapsed = time.time() - room["player_turn_start_times"][player_id]
        exceed_time = elapsed - room["time_limit"]

        current_turn = room.get("current_turn", "unknown")
        current_turn_name = (
            room["players"][current_turn]["name"]
            if current_turn in room["players"]
            else "unknown"
        )

        print(
            f"DEBUG: Timer check for {room['players'][player_id]['name']} (ID: {player_id})"
        )
        print(f"DEBUG: Current turn is: {current_turn_name} (ID: {current_turn})")
        print(
            f"DEBUG: Timer details - elapsed={elapsed:.1f}s, limit={room['time_limit']}s, exceed={exceed_time:.1f}s"
        )
        print(
            f"DEBUG: Player's timer started at: {room['player_turn_start_times'][player_id]}"
        )

        if exceed_time <= 0:
            return False, "within_limit"

        penalty_mode = room["penalty_mode"]

        if penalty_mode == "for_fun":
            return True, {
                "type": "alert",
                "message": f"Time exceeded by {exceed_time:.1f} seconds - this is just for fun!",
                "exceed_time": exceed_time,
            }
        elif penalty_mode == "manual":
            # Calculate score penalty based on exceed time ratio
            exceed_ratio = exceed_time / room["time_limit"]
            penalty_points = min(50, int(exceed_ratio * 25))  # Max 50 point penalty

            return True, {
                "type": "score_penalty",
                "message": f"Time exceeded by {exceed_time:.1f} seconds - {penalty_points} point penalty!",
                "exceed_time": exceed_time,
                "penalty_points": penalty_points,
            }

        return False, "unknown_mode"

    def apply_time_penalty(self, room_id, player_id, penalty_info):
        """Apply time penalty to player"""
        room = self.rooms[room_id]

        if penalty_info["type"] == "score_penalty":
            # Track penalty points for end-of-game calculation using separate tracking
            if player_id not in room["player_penalties"]:
                room["player_penalties"][player_id] = 0
            room["player_penalties"][player_id] += penalty_info["penalty_points"]
            print(
                f"DEBUG: Applied {penalty_info['penalty_points']} penalty to {player_id} ({room['players'][player_id]['name']}). Total penalties now: {room['player_penalties'][player_id]}"
            )
            print(
                f"DEBUG: All player penalties: {[(pid, room['player_penalties'].get(pid, 0), room['players'][pid]['name']) for pid in room['players']]}"
            )

        return penalty_info


# Global game instance
game_manager = BreakTheCodeGame()

NUMBER_CHOICE_OPTIONS = (
    ("#8** or **#9", {8, 9}),
    ("#1** or **#2", {1, 2}),
    ("#3** or **#4", {3, 4}),
    ("#6** or **#7", {6, 7}),
)


def get_allowed_chosen_numbers(question):
    """Return the allowed chosen numbers for number-select questions."""
    for question_marker, allowed_numbers in NUMBER_CHOICE_OPTIONS:
        if question_marker in question:
            return allowed_numbers
    return None


def build_room_players(room):
    """Serialize players in room order for client updates."""
    return [
        {
            "id": pid,
            "name": room["players"][pid]["name"],
            "ready": room["players"][pid]["ready"],
            "score": room["players"][pid]["score"],
            "connected": room["players"][pid]["connected"],
        }
        for pid in room["player_order"]
    ]


def build_player_game_payload(room, player_id):
    """Serialize the active game state for a single player."""
    payload = {
        "tiles": room["players"][player_id]["tiles"],
        "available_questions": room["available_questions"],
        "player_count": len(room["players"]),
        "current_turn": room["current_turn"],
        "game_state": "playing",
        "your_player_id": player_id,
        "all_players": {
            pid: {"name": room["players"][pid]["name"]}
            for pid in room["players"]
            if pid != player_id
        },
        "time_limit": room["time_limit"],
        "penalty_mode": room["penalty_mode"],
        "final_round": room.get("final_round", False),
        "final_round_player": room.get("final_round_player"),
    }

    if len(room["players"]) >= 3 and "center_tiles_count" in room:
        payload["center_tiles_count"] = room["center_tiles_count"]

    return payload


def emit_room_player_update(room_id):
    """Broadcast the latest ordered room/player state."""
    if room_id not in game_manager.rooms:
        return

    room = game_manager.rooms[room_id]
    emit(
        "player_joined",
        {
            "players": build_room_players(room),
            "player_count": len(room["players"]),
            "game_settings": room["game_settings"],
            "score_history": room["score_history"],
            "round_number": room["round_number"],
        },
        room=room_id,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/game/<room_id>")
def game_room(room_id):
    return render_template("game.html", room_id=room_id)


@socketio.on("create_room")
def handle_create_room(data):
    room_id = str(uuid.uuid4())[:8]
    player_name = data.get("player_name", "Anonymous")
    max_players = data.get("max_players", 4)
    num_question_cards = data.get("num_question_cards", 4)  # Get from client
    time_limit = data.get("time_limit", "unlimited")
    custom_time = data.get("custom_time")
    penalty_mode = data.get("penalty_mode", "for_fun")

    game_manager.create_game_room(
        room_id, max_players, num_question_cards, time_limit, custom_time, penalty_mode
    )

    player_id = str(uuid.uuid4())
    success, message = game_manager.join_room(room_id, player_id, player_name)

    if success:
        game_manager.set_player_socket(room_id, player_id, request.sid)

        # Set this player as the host
        game_manager.rooms[room_id]["host"] = player_id

        # Automatically mark the host as ready
        game_manager.set_player_ready(room_id, player_id, True)

        join_room(room_id)
        session["player_id"] = player_id
        session["room_id"] = room_id

        # Get the session key for the response
        session_key = game_manager.rooms[room_id]["players"][player_id]["session_key"]
        session["session_key"] = session_key

        emit(
            "room_created",
            {
                "room_id": room_id,
                "player_id": player_id,
                "player_name": player_name,
                "session_key": session_key,
                "is_host": True,
                "message": "Room created successfully",
            },
        )
    else:
        emit("error", {"message": message})


@socketio.on("join_room")
def handle_join_room(data):
    room_id = data.get("room_id")
    player_name = data.get("player_name", "Anonymous")
    reconnect_data = data.get("reconnect")  # {player_id, session_key}

    print(
        f"Join room request: room_id={room_id}, player_name={player_name}, reconnect={reconnect_data}"
    )

    if room_id not in game_manager.rooms:
        emit("error", {"message": "Room not found"})
        return

    room = game_manager.rooms[room_id]

    # Handle reconnection attempts
    if (
        reconnect_data
        and reconnect_data.get("player_id")
        and reconnect_data.get("session_key")
    ):
        player_id = reconnect_data["player_id"]
        session_key = reconnect_data["session_key"]

        print(f"Attempting reconnection for player {player_id}")
        success, message = game_manager.reconnect_player(
            room_id, player_id, session_key, request.sid
        )

        if success:
            print(f"Player {player_id} successfully reconnected")
            join_room(room_id)
            session["player_id"] = player_id
            session["room_id"] = room_id

            player_data = room["players"][player_id]
            session["session_key"] = player_data["session_key"]

            emit(
                "room_joined",
                {
                    "room_id": room_id,
                    "player_id": player_id,
                    "player_name": player_data["name"],
                    "session_key": player_data["session_key"],
                    "is_host": room.get("host") == player_id,
                    "message": "Reconnected successfully",
                },
            )

            # Notify others about reconnection
            emit(
                "player_reconnected",
                {"player_name": player_data["name"], "player_id": player_id},
                room=room_id,
            )

            emit_room_player_update(room_id)

            # Send current game state if game is active
            if room["game_state"] == "playing":
                emit("game_reconnected", build_player_game_payload(room, player_id))
            return
        else:
            print(f"Reconnection failed: {message}")
            emit("error", {"message": f"Reconnection failed: {message}"})
            return

    # Check if this player is already in the room by session (existing connection)
    existing_player_id = session.get("player_id")
    if existing_player_id and existing_player_id in room["players"]:
        print(f"Player {existing_player_id} already connected via session")
        emit("error", {"message": "You are already connected to this room"})
        return

    duplicate_player_entry = next(
        (
            (pid, player)
            for pid, player in room["players"].items()
            if player["name"].lower().strip() == player_name.lower().strip()
        ),
        None,
    )
    if duplicate_player_entry:
        duplicate_player_id, duplicate_player = duplicate_player_entry

        if duplicate_player.get("connected", True):
            emit(
                "error",
                {"message": "A player with this name already exists in the room"},
            )
            return

        if room["game_state"] == "waiting":
            print(
                f"Reclaiming disconnected waiting-room seat for player {duplicate_player_id}"
            )
            success, message = game_manager.reconnect_player(
                room_id,
                duplicate_player_id,
                duplicate_player["session_key"],
                request.sid,
            )

            if not success:
                emit("error", {"message": f"Failed to reclaim seat: {message}"})
                return

            join_room(room_id)
            session["player_id"] = duplicate_player_id
            session["room_id"] = room_id
            session["session_key"] = duplicate_player["session_key"]

            emit(
                "room_joined",
                {
                    "room_id": room_id,
                    "player_id": duplicate_player_id,
                    "player_name": duplicate_player["name"],
                    "session_key": duplicate_player["session_key"],
                    "is_host": room.get("host") == duplicate_player_id,
                    "message": "Rejoined waiting room successfully",
                },
            )

            emit(
                "player_reconnected",
                {
                    "player_name": duplicate_player["name"],
                    "player_id": duplicate_player_id,
                },
                room=room_id,
            )

            emit_room_player_update(room_id)
            return

        emit(
            "error",
            {
                "message": "This player is disconnected. Reconnect with your saved session on the original device."
            },
        )
        return

    # New player joining
    player_id = str(uuid.uuid4())
    print(f"Creating new player {player_id} with name {player_name}")
    success, message = game_manager.join_room(room_id, player_id, player_name)

    print(f"Join result: success={success}, message={message}")

    if success:
        game_manager.set_player_socket(room_id, player_id, request.sid)

        join_room(room_id)
        session["player_id"] = player_id
        session["room_id"] = room_id

        player_data = room["players"][player_id]
        session["session_key"] = player_data["session_key"]

        print(
            f"Player {player_id} successfully joined. Room now has {len(room['players'])} players"
        )

        emit(
            "room_joined",
            {
                "room_id": room_id,
                "player_id": player_id,
                "player_name": player_name,
                "session_key": player_data["session_key"],
                "is_host": room.get("host") == player_id,
                "message": message,
            },
        )

        emit_room_player_update(room_id)
    else:
        print(f"Failed to join room: {message}")
        emit("error", {"message": message})


@socketio.on("player_ready")
def handle_player_ready(data):
    room_id = session.get("room_id")
    player_id = session.get("player_id")
    ready_status = data.get("ready", False)

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    success, message = game_manager.set_player_ready(room_id, player_id, ready_status)

    if success:
        room = game_manager.rooms[room_id]

        # Send updated player list with ready status
        players_with_status = [
            {
                "id": pid,
                "name": room["players"][pid]["name"],
                "ready": room["players"][pid]["ready"],
                "score": room["players"][pid]["score"],
                "connected": room["players"][pid]["connected"],
            }
            for pid in room["player_order"]
        ]

        all_ready = game_manager.all_players_ready(room_id)

        emit(
            "player_ready_update",
            {"players": players_with_status, "all_ready": all_ready},
            room=room_id,
        )
    else:
        emit("error", {"message": message})


@socketio.on("reorder_players")
def handle_reorder_players(data):
    room_id = session.get("room_id")
    player_id = session.get("player_id")
    new_order = data.get("new_order", [])

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    if not player_id:
        emit("error", {"message": "Player not identified"})
        return

    success, message = game_manager.reorder_players(room_id, new_order, player_id)

    if success:
        room = game_manager.rooms[room_id]

        # Send updated player list with new order
        players_with_status = [
            {
                "id": pid,
                "name": room["players"][pid]["name"],
                "ready": room["players"][pid]["ready"],
                "score": room["players"][pid]["score"],
                "connected": room["players"][pid]["connected"],
            }
            for pid in room["player_order"]
        ]  # Use the new order

        emit(
            "players_reordered",
            {
                "players": players_with_status,
                "message": f'Player order updated by {room["players"][player_id]["name"]}',
            },
            room=room_id,
        )
    else:
        emit("error", {"message": message})


@socketio.on("remove_player")
def handle_remove_player(data):
    room_id = session.get("room_id")
    player_id = session.get("player_id")
    target_player_id = data.get("target_player_id") if isinstance(data, dict) else None

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    if not player_id:
        emit("error", {"message": "Player not identified"})
        return

    if not target_player_id:
        emit("error", {"message": "Choose a player to remove"})
        return

    success, message, removed_player = game_manager.remove_player(
        room_id, player_id, target_player_id
    )

    if not success:
        emit("error", {"message": message})
        return

    removed_player_name = removed_player["name"]
    removed_socket_sid = removed_player.get("socket_sid")

    if removed_socket_sid:
        socketio.emit(
            "player_removed",
            {
                "message": f"You were removed from room {room_id} by the host.",
                "room_id": room_id,
            },
            to=removed_socket_sid,
        )
        leave_room(room_id, sid=removed_socket_sid)

    emit_room_player_update(room_id)
    emit(
        "player_removed_notice",
        {
            "player_id": target_player_id,
            "player_name": removed_player_name,
            "message": f"{removed_player_name} was removed from the room.",
        },
        room=room_id,
    )


@socketio.on("start_game")
def handle_start_game():
    print(f"Start game request received from session: {dict(session)}")

    room_id = session.get("room_id")
    player_id = session.get("player_id")

    print(f"Start game: room_id={room_id}, player_id={player_id}")

    if not room_id or room_id not in game_manager.rooms:
        print(
            f"Invalid room: room_id={room_id}, rooms available: {list(game_manager.rooms.keys())}"
        )
        emit("error", {"message": "Invalid room"})
        return

    room = game_manager.rooms[room_id]

    # Check if player is the host
    if room["host"] != player_id:
        emit("error", {"message": "Only the host can start the game"})
        return

    # Check if all players are ready
    if not game_manager.all_players_ready(room_id):
        emit("error", {"message": "All players must be ready before starting the game"})
        return

    print(
        f"Room {room_id} has {len(room['players'])} players: {[p['name'] for p in room['players'].values()]}"
    )

    success, message = game_manager.start_game(room_id)
    print(f"Start game result: success={success}, message={message}")

    if success:
        room = game_manager.rooms[room_id]

        print(
            f"Game started successfully, sending game data to {len(room['players'])} players"
        )

        # Send game_started event to the entire room, but each client will only see their own data
        # We'll send a generic event first, then personalized data
        emit(
            "game_started",
            {
                "message": "Game has started!",
                "player_count": len(room["players"]),
                "available_questions": room["available_questions"],
                "current_turn": room["current_turn"],
                "game_state": "playing",
                "time_limit": room["time_limit"],
                "penalty_mode": room["penalty_mode"],
            },
            room=room_id,
        )

        # Now send personalized data directly to each player's current socket.
        for player_id in room["players"]:
            player_socket = room["players"][player_id].get("socket_sid")
            if not player_socket:
                continue

            print(
                f"Sending player_game_data to player {player_id} ({room['players'][player_id]['name']})"
            )
            socketio.emit(
                "player_game_data",
                build_player_game_payload(room, player_id),
                to=player_socket,
            )
    else:
        print(f"Failed to start game: {message}")
        emit("error", {"message": message})


@socketio.on("ask_question")
def handle_ask_question(data):
    if not isinstance(data, dict):
        emit("error", {"message": "Invalid question request"})
        return

    room_id = session.get("room_id")
    player_id = session.get("player_id")
    question_index = data.get("question_index")
    chosen_number = data.get(
        "chosen_number"
    )  # Optional parameter for questions requiring number choice

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    room = game_manager.rooms[room_id]

    # Check if it's the player's turn
    if room.get("current_turn") != player_id:
        emit("error", {"message": "It's not your turn!"})
        return

    # Check if game is in final round
    if room.get("final_round"):
        emit("error", {"message": "Questions cannot be asked during final round!"})
        return

    if type(question_index) is not int:
        emit("error", {"message": "Invalid question"})
        return

    if question_index < 0 or question_index >= len(room["available_questions"]):
        emit("error", {"message": "Invalid question"})
        return

    question = room["available_questions"][question_index]

    # Check if this question requires a number choice
    allowed_numbers = get_allowed_chosen_numbers(question)
    if allowed_numbers is not None:
        if chosen_number is None:
            emit(
                "error",
                {"message": "This question requires you to choose a number first!"},
            )
            return
        if type(chosen_number) is not int:
            emit(
                "error",
                {"message": "Invalid number choice. Choose one of the listed numbers."},
            )
            return
        if chosen_number not in allowed_numbers:
            allowed_numbers_display = ", ".join(
                str(number) for number in sorted(allowed_numbers)
            )
            emit(
                "error",
                {
                    "message": f"Invalid number choice. Allowed numbers: {allowed_numbers_display}"
                },
            )
            return

    # Calculate answers for ALL other players
    all_answers = {}
    asking_player_name = room["players"][player_id]["name"]

    for target_player_id in room["players"]:
        if target_player_id != player_id:  # Don't ask the question to yourself
            target_tiles = room["players"][target_player_id]["tiles"]
            answer = calculate_answer(question, target_tiles, chosen_number)
            all_answers[target_player_id] = {
                "name": room["players"][target_player_id]["name"],
                "answer": answer,
            }

    # Broadcast question and all answers to all players
    question_display = question
    if chosen_number is not None:
        question_display = f"{question} (Chosen number: {chosen_number})"

    emit(
        "question_asked",
        {
            "question": question_display,
            "answers": all_answers,
            "asking_player": asking_player_name,
        },
        room=room_id,
    )

    # Remove used question and add to used pile
    used_question = room["available_questions"].pop(question_index)
    room["used_question_cards"].append(used_question)

    # Try to replace with a new question from the remaining deck
    remaining_questions = [
        q
        for q in room["question_cards"]
        if q not in room["used_question_cards"] and q not in room["available_questions"]
    ]

    new_question_added = False
    if remaining_questions:
        # Add a new random question from the remaining deck
        new_question = random.choice(remaining_questions)
        room["available_questions"].append(new_question)
        new_question_added = True

    # Always broadcast updated questions to all players (even if no new question was added)
    emit(
        "questions_updated",
        {
            "available_questions": room["available_questions"],
            "new_question_added": new_question_added,
            "total_questions_remaining": len(room["available_questions"]),
        },
        room=room_id,
    )

    # Check for time violation before changing turn
    time_violation, penalty_info = game_manager.check_time_violation(room_id, player_id)
    if time_violation and penalty_info != "within_limit":
        # Apply penalties and continue
        game_manager.apply_time_penalty(room_id, player_id, penalty_info)
        emit(
            "time_violation",
            {
                "message": penalty_info["message"],
                "penalty_type": penalty_info["type"],
                "player_name": room["players"][player_id]["name"],
            },
            room=room_id,
        )

    # Move to next player's turn
    players = room["player_order"]
    current_index = players.index(player_id)

    next_index = (current_index + 1) % len(players)
    room["current_turn"] = players[next_index]

    # Start timer for the next player
    game_manager.start_turn_timer(room_id, room["current_turn"])

    emit(
        "turn_changed",
        {
            "current_turn": room["current_turn"],
            "current_player_name": room["players"][room["current_turn"]]["name"],
        },
        room=room_id,
    )


def calculate_answer(question, tiles, chosen_number=None):
    """Calculate the answer to a question based on tiles"""

    # Handle questions that require a chosen number
    allowed_numbers = get_allowed_chosen_numbers(question)
    if allowed_numbers is not None:
        if chosen_number is None:
            return "Error: Number not chosen"

        if chosen_number not in allowed_numbers:
            return "Error: Invalid number choice"

        target_positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == chosen_number:
                position = chr(65 + i)  # Convert to A, B, C, D, E
                target_positions.append(position)
        return (
            f"Position(s): {', '.join(target_positions)}"
            if target_positions
            else "Not found"
        )

    # Handle simple counting questions
    if "How many **odd** tiles you have" in question:
        return len([t for t in tiles if t["number"] % 2 == 1])
    elif "How many **even** tiles you have" in question:
        return len([t for t in tiles if t["number"] % 2 == 0])
    elif "How many of **your tiles have the same number**" in question:
        from collections import Counter

        numbers = [t["number"] for t in tiles]
        counts = Counter(numbers)
        return sum(count for count in counts.values() if count > 1)
    elif "How many of your tiles have **a black number**" in question:
        return len([t for t in tiles if t["color"] == "black"])
    elif "How many of your tiles have **a white number**" in question:
        return len([t for t in tiles if t["color"] == "white"])

    # Handle position-based questions
    elif "Which neighbouring tiles have **consecutive numbers**" in question:
        consecutive_pairs = []
        for i in range(len(tiles) - 1):
            current_num = tiles[i]["number"]
            next_num = tiles[i + 1]["number"]
            if abs(current_num - next_num) == 1:
                pos1 = chr(65 + i)
                pos2 = chr(65 + i + 1)
                consecutive_pairs.append(f"{pos1}-{pos2}")
        return ", ".join(consecutive_pairs) if consecutive_pairs else "None"

    elif "Which **neighboring tiles have the same color**" in question:
        same_color_pairs = []
        for i in range(len(tiles) - 1):
            current_color = tiles[i]["color"]
            next_color = tiles[i + 1]["color"]
            if current_color == next_color:
                pos1 = chr(65 + i)
                pos2 = chr(65 + i + 1)
                same_color_pairs.append(f"{pos1}-{pos2}")
        return ", ".join(same_color_pairs) if same_color_pairs else "None"

    # Handle sum questions
    elif "left-most tiles" in question:
        left_tiles = tiles[:3] if len(tiles) >= 5 else tiles[:2]
        return sum(t["number"] for t in left_tiles)
    elif "right-most tiles" in question:
        right_tiles = tiles[-3:] if len(tiles) >= 5 else tiles[-2:]
        return sum(t["number"] for t in right_tiles)
    elif "sum of your central tiles" in question:
        if len(tiles) >= 5:
            central_tiles = tiles[1:4]  # Positions B, C, D (indices 1, 2, 3)
            return sum(t["number"] for t in central_tiles)
        elif len(tiles) >= 4:
            # For 4-tile hands, the middle tiles are B and C.
            central_tiles = tiles[1:3]
            return sum(t["number"] for t in central_tiles)
        else:
            return "Not applicable"
    elif "What is the **sum of your tiles**" in question:
        return sum(t["number"] for t in tiles)

    # Handle specific position questions
    elif "Where are your **#5** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == 5:
                position = chr(65 + i)  # Convert to A, B, C, D, E
                positions.append(position)
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"

    elif "Where are your **#0** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == 0:
                position = chr(65 + i)  # Convert to A, B, C, D, E
                positions.append(position)
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"

    elif "Is your **C tile greater than 4**" in question:
        if len(tiles) >= 3:
            c_tile = tiles[2]  # Position C is index 2
            return "Yes" if c_tile["number"] > 4 else "No"
        else:
            return "Not applicable"

    # Handle mathematical questions
    elif (
        "What is the **difference between your highest and lowest numbers**" in question
    ):
        numbers = [t["number"] for t in tiles]
        return max(numbers) - min(numbers) if numbers else 0

    # Fallback for unrecognized questions
    return "Unknown question"


@socketio.on("make_guess")
def handle_make_guess(data):
    room_id = session.get("room_id")
    player_id = session.get("player_id")
    guess = data.get("guess")
    guess_type = data.get("guess_type", "center")

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    room = game_manager.rooms[room_id]

    if not player_id or player_id not in room["players"]:
        emit("error", {"message": "Invalid player session"})
        return

    if not isinstance(guess, list) or not guess:
        emit("error", {"message": "Guess must include the full set of tiles"})
        return

    if any(
        not isinstance(tile, dict) or "number" not in tile or "color" not in tile
        for tile in guess
    ):
        emit("error", {"message": "Invalid guess format"})
        return

    print(
        f"Guess received from {room['players'][player_id]['name']}: {guess}, type: {guess_type}"
    )

    # Check for time violation before processing the guess
    time_violation, penalty_info = game_manager.check_time_violation(room_id, player_id)
    if time_violation and penalty_info != "within_limit":
        # Apply penalties and continue
        game_manager.apply_time_penalty(room_id, player_id, penalty_info)
        emit(
            "time_violation",
            {
                "message": penalty_info["message"],
                "penalty_type": penalty_info["type"],
                "player_name": room["players"][player_id]["name"],
            },
            room=room_id,
        )

    # Check turn validation
    if room.get("final_round"):
        # In final round, only the final round player can guess
        if room.get("final_round_player") != player_id:
            emit(
                "error",
                {"message": "Only the final round player can make guesses now!"},
            )
            return
    else:
        # Normal round, check if it's the player's turn
        if room.get("current_turn") != player_id:
            emit("error", {"message": "It's not your turn!"})
            return

    player_count = len(room["players"])

    # Validate guess length based on game mode
    expected_length = get_expected_guess_length(player_count, guess_type)
    if len(guess) != expected_length:
        emit("error", {"message": f"Guess must have exactly {expected_length} tiles"})
        return

    # Check guess correctness based on game mode
    is_correct = False
    target_tiles = []

    if player_count == 2:
        # 2-player mode: guess another player's tiles
        if guess_type in room["players"] and guess_type != player_id:
            target_tiles = room["players"][guess_type]["tiles"]
            is_correct = check_guess_correctness(guess, target_tiles)
            target_name = room["players"][guess_type]["name"]
        else:
            emit("error", {"message": "Invalid target player for guess"})
            return
    else:
        # 3-4 player mode: guess center tiles
        if guess_type == "center":
            target_tiles = room["center_tiles"]
            is_correct = check_guess_correctness(guess, target_tiles)
            target_name = "center code"
        else:
            emit("error", {"message": "Invalid guess type for this game mode"})
            return

    # Store the guess result with timestamp for ordering
    timestamp = time.time()
    room["players"][player_id]["guesses"].append(
        {
            "guess": guess,
            "target": guess_type,
            "correct": is_correct,
            "timestamp": timestamp,
        }
    )

    # Track first successful guess for win condition logic
    if is_correct and not room.get("first_successful_guess"):
        room["first_successful_guess"] = {
            "player_id": player_id,
            "timestamp": timestamp,
            "player_name": room["players"][player_id]["name"],
        }

    # Broadcast the guess to all players
    guess.sort(key=lambda x: (x["number"], x["color"]))
    emit(
        "guess_made",
        {
            "player": room["players"][player_id]["name"],
            "guess": guess,
            "target": target_name,
            "correct": is_correct,
            "actual_tiles": target_tiles,
            "player_count": player_count,
        },
        room=room_id,
    )

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
    guess_tiles = [{"number": tile["number"], "color": tile["color"]} for tile in guess]
    target_tiles_copy = [
        {"number": tile["number"], "color": tile["color"]} for tile in target_tiles
    ]

    # Sort both lists the same way for comparison
    guess_tiles.sort(key=lambda x: (x["number"], x["color"]))
    target_tiles_copy.sort(key=lambda x: (x["number"], x["color"]))

    return guess_tiles == target_tiles_copy


def update_player_scores(room_id, winners, is_draw):
    """Update player scores based on game results"""
    room = game_manager.rooms[room_id]

    # Record the round results
    round_result = {
        "round": room["round_number"] + 1,
        "players": [],  # Track all players and their results
        "is_draw": is_draw,
        "timestamp": time.time(),
    }

    # Process all players to determine their results
    for player_id in room["players"]:
        player_data = room["players"][player_id]
        is_winner = player_id in winners

        # Determine result for this player
        if is_draw and is_winner:
            result = "Draw"
        elif is_winner:
            result = "Win"
        else:
            result = "Loss"

        # Calculate points awarded
        if is_winner:
            base_points = 100
            # Calculate total penalties accumulated during this game
            total_penalties = room["player_penalties"].get(player_id, 0)
            # Award points after subtracting penalties, but don't go below 0
            final_points = max(0, base_points - total_penalties)

            old_score = player_data["score"]
            room["players"][player_id]["score"] += final_points

            print(
                f"DEBUG: Player {player_id} ({player_data['name']}) awarded {final_points} points (100 - {total_penalties} penalties)"
            )
        else:
            # Losing player gets no points
            final_points = 0
            total_penalties = room["player_penalties"].get(player_id, 0)
            old_score = player_data["score"]
            # No score change for losing players

        # Record this player's result
        round_result["players"].append(
            {
                "player_id": player_id,
                "player_name": player_data["name"],
                "result": result,
                "points_awarded": final_points,
                "penalties": total_penalties,
                "old_score": old_score,
                "new_score": room["players"][player_id]["score"],
            }
        )

    # Add round result to history
    room["score_history"].append(round_result)
    room["round_number"] += 1


def reset_game_for_next_round(room_id):
    """Reset game state for next round while preserving scores and players"""
    room = game_manager.rooms[room_id]

    # Reset game state
    room["game_state"] = "waiting"
    room["current_turn"] = None
    room["final_round"] = False
    room["final_round_player"] = None
    room["final_round_started_emitted"] = (
        False  # Clear the final round started emission flag
    )
    room["first_successful_guess"] = None
    room["winners"] = None
    room["center_tiles"] = []
    room["center_tiles_count"] = 0
    room["used_question_cards"] = []
    room["correct_guessers"] = []  # Clear the correct guessers list
    room["first_correct_guesser"] = None  # Clear the first correct guesser

    # Reset timer-related variables
    room["turn_start_time"] = None
    room["turn_timers"] = {}
    room["player_penalties"] = {}  # Clear accumulated penalties
    room["player_turn_start_times"] = {}  # Clear individual player timer tracking

    # Reset ready players
    room["ready_players"] = set()

    # Reset player game data but keep scores and names
    for player_id in room["players"]:
        player = room["players"][player_id]
        player["tiles"] = []
        player["guesses"] = []
        player["ready"] = False
        player.pop("correct_guess", None)
        player.pop("guess_timestamp", None)
        player.pop("center_guess_correct", None)
        player.pop("has_guessed", None)  # Clear has_guessed flag
        player.pop("time_violation_loss", None)  # Clear any time violation flags

    # Auto-mark host as ready after the reset so the ready set and player flags match.
    if room.get("host") and room["host"] in room["players"]:
        room["players"][room["host"]]["ready"] = True
        room["ready_players"].add(room["host"])

    # Broadcast updated game info to all players
    emit(
        "game_reset_to_waiting",
        {
            "players": [
                {
                    "id": pid,
                    "name": room["players"][pid]["name"],
                    "ready": room["players"][pid]["ready"],
                    "score": room["players"][pid]["score"],
                    "connected": room["players"][pid]["connected"],
                }
                for pid in room["player_order"]
            ],
            "game_settings": room["game_settings"],
            "score_history": room["score_history"],
            "round_number": room["round_number"],
        },
        room=room_id,
    )


def check_two_player_win_condition_new(room_id, guessing_player_id, is_correct):
    """Check win condition for 2-player game with new logic"""
    room = game_manager.rooms[room_id]
    players = room["player_order"]

    # Determine player order: first in order is player 1, second is player 2
    player_1 = players[0]
    player_2 = players[1]

    # Check if we're already in final round
    if room.get("final_round"):
        # We're in final round, this must be player 2's final guess
        if guessing_player_id == player_2:
            room["game_state"] = "finished"
            if is_correct:
                # Both players guessed correctly - it's a draw
                room["winners"] = [player_1, player_2]
                update_player_scores(room_id, [player_1, player_2], is_draw=True)

                # Calculate actual points awarded after penalties
                player_1_penalties = room["player_penalties"].get(player_1, 0)
                player_2_penalties = room["player_penalties"].get(player_2, 0)
                player_1_points = max(0, 100 - player_1_penalties)
                player_2_points = max(0, 100 - player_2_penalties)

                emit(
                    "game_ended",
                    {
                        "winners": [
                            room["players"][pid]["name"] for pid in [player_1, player_2]
                        ],
                        "message": f'Both players guessed correctly! It\'s a draw! ({room["players"][player_1]["name"]}: +{player_1_points} pts, {room["players"][player_2]["name"]}: +{player_2_points} pts)',
                        "is_draw": True,
                        "redirect_to_waiting": True,
                    },
                    room=room_id,
                )
            else:
                # Only player 1 guessed correctly - player 1 wins
                room["winners"] = [player_1]
                update_player_scores(room_id, [player_1], is_draw=False)

                # Calculate actual points awarded after penalties
                player_1_penalties = room["player_penalties"].get(player_1, 0)
                player_1_points = max(0, 100 - player_1_penalties)

                emit(
                    "game_ended",
                    {
                        "winners": [room["players"][player_1]["name"]],
                        "message": f"{room['players'][player_1]['name']} wins! (+{player_1_points} pts)",
                        "is_draw": False,
                        "redirect_to_waiting": True,
                    },
                    room=room_id,
                )
            # Reset game for next round
            reset_game_for_next_round(room_id)
        return

    # Not in final round yet - only process correct guesses
    if is_correct:
        # Someone guessed correctly, mark them as having a correct guess
        room["players"][guessing_player_id]["correct_guess"] = True
        room["players"][guessing_player_id]["guess_timestamp"] = time.time()

        if guessing_player_id == player_2:
            # Player 2 guessed correctly first - immediate win, game ends
            room["game_state"] = "finished"
            room["winners"] = [player_2]
            update_player_scores(room_id, [player_2], is_draw=False)

            # Calculate actual points awarded after penalties
            player_2_penalties = room["player_penalties"].get(player_2, 0)
            player_2_points = max(0, 100 - player_2_penalties)

            emit(
                "game_ended",
                {
                    "winners": [room["players"][player_2]["name"]],
                    "message": f"{room['players'][player_2]['name']} wins! Game over. (+{player_2_points} pts)",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            # Reset game for next round
            reset_game_for_next_round(room_id)
            return

        elif guessing_player_id == player_1:
            # Player 1 guessed correctly first - give player 2 a final chance
            room["final_round"] = True
            room["final_round_player"] = player_2  # Only player 2 can guess now
            room["current_turn"] = player_2  # Set turn to final round player

            # Start timer for player 2's final turn
            game_manager.start_turn_timer(room_id, player_2)

            emit(
                "final_round_started",
                {
                    "message": f"{room['players'][player_1]['name']} guessed correctly! {room['players'][player_2]['name']} has one final chance to guess.",
                    "first_winner": room["players"][player_1]["name"],
                    "final_player": player_2,
                    "final_player_name": room["players"][player_2]["name"],
                },
                room=room_id,
            )

            # Also emit turn changed event to update the UI
            emit(
                "turn_changed",
                {
                    "current_turn": room["current_turn"],
                    "current_player_name": room["players"][room["current_turn"]][
                        "name"
                    ],
                    "final_round": True,
                    "final_round_player": player_2,
                },
                room=room_id,
            )
            return
    else:  # Guess is INCORRECT, and not in final round
        # The guessing_player_id is the current player. Pass turn to the other player.
        next_player_id = player_1 if guessing_player_id == player_2 else player_2

        room["current_turn"] = next_player_id
        game_manager.start_turn_timer(room_id, next_player_id)
        emit(
            "turn_changed",
            {
                "current_turn": room["current_turn"],
                "current_player_name": room["players"][room["current_turn"]]["name"],
                "final_round": False,  # Explicitly not a final round
            },
            room=room_id,
        )
        return


def check_center_guess_win_condition_new(room_id, guessing_player_id, is_correct):
    """Check win condition for 3-4 player game with center guessing"""
    room = game_manager.rooms[room_id]
    players = room["player_order"]
    num_players = len(players)

    # Get player's position (1, 2, 3, or 4)
    player_position = players.index(guessing_player_id) + 1

    print(
        f"DEBUG: Player {player_position} ({room['players'][guessing_player_id]['name']}) guessed {'correctly' if is_correct else 'incorrectly'}"
    )

    if is_correct:
        # Initialize correct guessers list if not exists
        if "correct_guessers" not in room:
            room["correct_guessers"] = []

        # Only add if not already in the list (prevent duplicates)
        if guessing_player_id not in room["correct_guessers"]:
            room["correct_guessers"].append(guessing_player_id)
            print(
                f"DEBUG: Added {room['players'][guessing_player_id]['name']} to correct guessers. Total: {[room['players'][pid]['name'] for pid in room['correct_guessers']]}"
            )

        # If the last player (Player 3 in 3-player, Player 4 in 4-player) guesses correctly, game ends immediately
        if player_position == num_players:
            print(
                f"DEBUG: Player {player_position} (last player) guessed correctly, ending game immediately"
            )
            room["game_state"] = "finished"
            # Give points to all correct guessers
            update_player_scores(room_id, room["correct_guessers"], is_draw=False)

            # Calculate actual points awarded after penalties for each winner
            winner_details = []
            for winner_id in room["correct_guessers"]:
                penalties = room["player_penalties"].get(winner_id, 0)
                points = max(0, 100 - penalties)
                winner_details.append(
                    f"{room['players'][winner_id]['name']}: +{points} pts"
                )

            # Create winners message
            winner_names = [
                room["players"][pid]["name"] for pid in room["correct_guessers"]
            ]
            winners_msg = ", ".join(winner_details)

            emit(
                "game_ended",
                {
                    "winners": winner_names,
                    "message": f"Game Over! Winners: {winners_msg}",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            reset_game_for_next_round(room_id)
            return

        # For any other player's correct guess - enter final round or continue final round
        if not room.get("final_round"):
            print(
                f"DEBUG: Starting final round because Player {player_position} guessed correctly first"
            )
            room["final_round"] = True
            room["first_correct_guesser"] = guessing_player_id

            # Reset has_guessed flags for all players
            for pid in players:
                room["players"][pid]["has_guessed"] = False

            # Mark the correct guesser as having guessed
            room["players"][guessing_player_id]["has_guessed"] = True
        else:
            # Already in final round, mark this player as having guessed
            print(f"DEBUG: Player {player_position} guessed correctly in final round")
            room["players"][guessing_player_id]["has_guessed"] = True

        # Determine who gets the next turn in final round
        first_guesser_pos = players.index(room["first_correct_guesser"]) + 1
        next_player = None

        print(
            f"DEBUG: First guesser was Player {first_guesser_pos}, looking for next player..."
        )

        # Find the next eligible player (any player with higher position than first guesser who hasn't guessed)
        for pos in range(first_guesser_pos + 1, num_players + 1):
            if pos - 1 < len(players):  # Make sure player exists
                potential_next = players[pos - 1]
                if not room["players"][potential_next].get("has_guessed", False):
                    next_player = potential_next
                    next_pos = pos
                    print(
                        f"DEBUG: Next player is Player {next_pos} ({room['players'][potential_next]['name']})"
                    )
                    break

        if next_player:
            room["current_turn"] = next_player
            room["final_round_player"] = next_player

            # Start timer for the next player in final round
            game_manager.start_turn_timer(room_id, next_player)

            emit(
                "turn_changed",
                {
                    "current_turn": next_player,
                    "current_player_name": room["players"][next_player]["name"],
                    "final_round": True,
                    "final_round_player": next_player,
                },
                room=room_id,
            )
        else:
            # All eligible players have guessed - game ends
            print(f"DEBUG: All eligible players have guessed, ending game")
            room["game_state"] = "finished"
            # Give points to all correct guessers
            update_player_scores(room_id, room["correct_guessers"], is_draw=False)

            # Calculate actual points awarded after penalties for each winner
            winner_details = []
            for winner_id in room["correct_guessers"]:
                penalties = room["player_penalties"].get(winner_id, 0)
                points = max(0, 100 - penalties)
                winner_details.append(
                    f"{room['players'][winner_id]['name']}: +{points} pts"
                )

            # Create winners message
            winner_names = [
                room["players"][pid]["name"] for pid in room["correct_guessers"]
            ]
            winners_msg = ", ".join(winner_details)

            emit(
                "game_ended",
                {
                    "winners": winner_names,
                    "message": f"Game Over! Winners: {winners_msg}",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            reset_game_for_next_round(room_id)
    else:
        # Incorrect guess
        print(f"DEBUG: Player {player_position} guessed incorrectly")
        if room.get("final_round"):
            # Mark this player as having guessed in final round
            room["players"][guessing_player_id]["has_guessed"] = True

            # Find next eligible player based on first guesser's position
            first_guesser_pos = players.index(room["first_correct_guesser"]) + 1
            next_player = None

            print(
                f"DEBUG: In final round, first guesser was Player {first_guesser_pos}"
            )

            # Find the next eligible player (any player with higher position than first guesser who hasn't guessed)
            for pos in range(first_guesser_pos + 1, num_players + 1):
                if pos - 1 < len(players):  # Make sure player exists
                    potential_next = players[pos - 1]
                    if not room["players"][potential_next].get("has_guessed", False):
                        next_player = potential_next
                        print(
                            f"DEBUG: Next player after incorrect guess is Player {pos} ({room['players'][potential_next]['name']})"
                        )
                        break

            if next_player:
                room["current_turn"] = next_player
                room["final_round_player"] = next_player
                game_manager.start_turn_timer(room_id, next_player)
                emit(
                    "turn_changed",
                    {
                        "current_turn": next_player,
                        "current_player_name": room["players"][next_player]["name"],
                        "final_round": True,
                        "final_round_player": next_player,
                    },
                    room=room_id,
                )
            else:
                # No more players to guess - game ends with current correct guessers
                print(
                    f"DEBUG: No more players to guess after incorrect guess, ending game"
                )
                room["game_state"] = "finished"
                # Give points to all correct guessers
                update_player_scores(room_id, room["correct_guessers"], is_draw=False)

                # Calculate actual points awarded after penalties for each winner
                winner_details = []
                for winner_id in room["correct_guessers"]:
                    penalties = room["player_penalties"].get(winner_id, 0)
                    points = max(0, 100 - penalties)
                    winner_details.append(
                        f"{room['players'][winner_id]['name']}: +{points} pts"
                    )

                # Create winners message
                winner_names = [
                    room["players"][pid]["name"] for pid in room["correct_guessers"]
                ]
                winners_msg = ", ".join(winner_details)

                emit(
                    "game_ended",
                    {
                        "winners": winner_names,
                        "message": f"Game Over! Winners: {winners_msg}",
                        "is_draw": False,
                        "redirect_to_waiting": True,
                    },
                    room=room_id,
                )
                reset_game_for_next_round(room_id)
        else:
            # Regular incorrect guess, move to next player
            current_index = players.index(guessing_player_id)
            next_index = (current_index + 1) % len(players)
            next_player_id = players[next_index]

            room["current_turn"] = next_player_id

            # Start timer for the next player
            game_manager.start_turn_timer(room_id, next_player_id)

            emit(
                "turn_changed",
                {
                    "current_turn": next_player_id,
                    "current_player_name": room["players"][next_player_id]["name"],
                    "final_round": False,
                },
                room=room_id,
            )


@socketio.on("disconnect")
def handle_disconnect():
    """Handle player disconnection"""
    room_id = session.get("room_id")
    player_id = session.get("player_id")

    if room_id and player_id:
        print(f"Player {player_id} disconnected from room {room_id}")

        # Mark player as disconnected
        success = game_manager.disconnect_player(room_id, player_id, request.sid)

        if success and room_id in game_manager.rooms:
            room = game_manager.rooms[room_id]
            player_name = room["players"][player_id]["name"]

            # Notify other players about disconnection
            emit(
                "player_disconnected",
                {
                    "player_name": player_name,
                    "player_id": player_id,
                    "message": f"{player_name} has disconnected",
                },
                room=room_id,
            )

            # Update player list with connection status
            emit_room_player_update(room_id)


@socketio.on("get_game_info")
def handle_get_game_info():
    room_id = session.get("room_id")

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    room = game_manager.rooms[room_id]

    # Send game settings and score history
    emit(
        "game_info_update",
        {
            "game_settings": room["game_settings"],
            "score_history": room["score_history"],
            "round_number": room["round_number"],
        },
    )


@socketio.on("get_all_timers")
def handle_get_all_timers():
    room_id = session.get("room_id")

    if not room_id or room_id not in game_manager.rooms:
        emit("error", {"message": "Invalid room"})
        return

    room = game_manager.rooms[room_id]

    # Get timer information for all players
    timer_info = {}
    for player_id in room["players"]:
        remaining_time = game_manager.get_remaining_time(room_id, player_id)
        timer_info[player_id] = {
            "player_name": room["players"][player_id]["name"],
            "remaining_time": remaining_time,
            "is_current_turn": room.get("current_turn") == player_id,
            "time_limit": room["time_limit"],
        }

    emit(
        "all_timers_update",
        {
            "timers": timer_info,
            "current_turn": room.get("current_turn"),
            "time_limit": room["time_limit"],
        },
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
