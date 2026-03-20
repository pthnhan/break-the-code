import random
import time
import uuid


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
