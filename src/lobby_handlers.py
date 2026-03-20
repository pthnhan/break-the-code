import uuid

from flask import request, session
from flask_socketio import emit, join_room, leave_room

from src.gameplay import emit_room_player_update
from src.payloads import build_player_game_payload, build_room_players


def register_lobby_handlers(socketio, game_manager):
    @socketio.on("create_room")
    def handle_create_room(data):
        room_id = str(uuid.uuid4())[:8]
        player_name = data.get("player_name", "Anonymous")
        max_players = data.get("max_players", 4)
        num_question_cards = data.get("num_question_cards", 4)
        time_limit = data.get("time_limit", "unlimited")
        custom_time = data.get("custom_time")
        penalty_mode = data.get("penalty_mode", "for_fun")

        game_manager.create_game_room(
            room_id,
            max_players,
            num_question_cards,
            time_limit,
            custom_time,
            penalty_mode,
        )

        player_id = str(uuid.uuid4())
        success, message = game_manager.join_room(room_id, player_id, player_name)

        if success:
            game_manager.set_player_socket(room_id, player_id, request.sid)

            game_manager.rooms[room_id]["host"] = player_id
            game_manager.set_player_ready(room_id, player_id, True)

            join_room(room_id)
            session["player_id"] = player_id
            session["room_id"] = room_id

            session_key = game_manager.rooms[room_id]["players"][player_id][
                "session_key"
            ]
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
        reconnect_data = data.get("reconnect")

        print(
            f"Join room request: room_id={room_id}, player_name={player_name}, reconnect={reconnect_data}"
        )

        if room_id not in game_manager.rooms:
            emit("error", {"message": "Room not found"})
            return

        room = game_manager.rooms[room_id]

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

                emit(
                    "player_reconnected",
                    {"player_name": player_data["name"], "player_id": player_id},
                    room=room_id,
                )

                emit_room_player_update(socketio, game_manager, room_id)

                if room["game_state"] == "playing":
                    emit("game_reconnected", build_player_game_payload(room, player_id))
                return

            print(f"Reconnection failed: {message}")
            emit("error", {"message": f"Reconnection failed: {message}"})
            return

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

                emit_room_player_update(socketio, game_manager, room_id)
                return

            emit(
                "error",
                {
                    "message": "This player is disconnected. Reconnect with your saved session on the original device."
                },
            )
            return

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

            emit_room_player_update(socketio, game_manager, room_id)
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

        success, message = game_manager.set_player_ready(
            room_id, player_id, ready_status
        )

        if success:
            room = game_manager.rooms[room_id]
            all_ready = game_manager.all_players_ready(room_id)

            emit(
                "player_ready_update",
                {"players": build_room_players(room), "all_ready": all_ready},
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

            emit(
                "players_reordered",
                {
                    "players": build_room_players(room),
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
        target_player_id = (
            data.get("target_player_id") if isinstance(data, dict) else None
        )

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

        emit_room_player_update(socketio, game_manager, room_id)
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

        if room["host"] != player_id:
            emit("error", {"message": "Only the host can start the game"})
            return

        if not game_manager.all_players_ready(room_id):
            emit(
                "error",
                {"message": "All players must be ready before starting the game"},
            )
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

            for current_player_id in room["players"]:
                player_socket = room["players"][current_player_id].get("socket_sid")
                if not player_socket:
                    continue

                print(
                    f"Sending player_game_data to player {current_player_id} ({room['players'][current_player_id]['name']})"
                )
                socketio.emit(
                    "player_game_data",
                    build_player_game_payload(room, current_player_id),
                    to=player_socket,
                )
        else:
            print(f"Failed to start game: {message}")
            emit("error", {"message": message})
