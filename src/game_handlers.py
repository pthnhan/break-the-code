import random
import time

from flask import request, session
from flask_socketio import emit

from src.gameplay import (
    check_center_guess_win_condition_new,
    check_two_player_win_condition_new,
    emit_room_player_update,
)
from src.question_logic import (
    calculate_answer,
    check_guess_correctness,
    get_allowed_chosen_numbers,
    get_expected_guess_length,
)


def register_game_handlers(socketio, game_manager):
    @socketio.on("ask_question")
    def handle_ask_question(data):
        if not isinstance(data, dict):
            emit("error", {"message": "Invalid question request"})
            return

        room_id = session.get("room_id")
        player_id = session.get("player_id")
        question_index = data.get("question_index")
        chosen_number = data.get("chosen_number")

        if not room_id or room_id not in game_manager.rooms:
            emit("error", {"message": "Invalid room"})
            return

        room = game_manager.rooms[room_id]

        if room.get("current_turn") != player_id:
            emit("error", {"message": "It's not your turn!"})
            return

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
                    {
                        "message": "Invalid number choice. Choose one of the listed numbers."
                    },
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

        all_answers = {}
        asking_player_name = room["players"][player_id]["name"]

        for target_player_id in room["players"]:
            if target_player_id != player_id:
                target_tiles = room["players"][target_player_id]["tiles"]
                answer = calculate_answer(question, target_tiles, chosen_number)
                all_answers[target_player_id] = {
                    "name": room["players"][target_player_id]["name"],
                    "answer": answer,
                }

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

        used_question = room["available_questions"].pop(question_index)
        room["used_question_cards"].append(used_question)

        remaining_questions = [
            q
            for q in room["question_cards"]
            if q not in room["used_question_cards"]
            and q not in room["available_questions"]
        ]

        new_question_added = False
        if remaining_questions:
            new_question = random.choice(remaining_questions)
            room["available_questions"].append(new_question)
            new_question_added = True

        emit(
            "questions_updated",
            {
                "available_questions": room["available_questions"],
                "new_question_added": new_question_added,
                "total_questions_remaining": len(room["available_questions"]),
            },
            room=room_id,
        )

        time_violation, penalty_info = game_manager.check_time_violation(
            room_id, player_id
        )
        if time_violation and penalty_info != "within_limit":
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

        players = room["player_order"]
        current_index = players.index(player_id)

        next_index = (current_index + 1) % len(players)
        room["current_turn"] = players[next_index]

        game_manager.start_turn_timer(room_id, room["current_turn"])

        emit(
            "turn_changed",
            {
                "current_turn": room["current_turn"],
                "current_player_name": room["players"][room["current_turn"]]["name"],
            },
            room=room_id,
        )

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

        time_violation, penalty_info = game_manager.check_time_violation(
            room_id, player_id
        )
        if time_violation and penalty_info != "within_limit":
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

        if room.get("final_round"):
            if room.get("final_round_player") != player_id:
                emit(
                    "error",
                    {"message": "Only the final round player can make guesses now!"},
                )
                return
        else:
            if room.get("current_turn") != player_id:
                emit("error", {"message": "It's not your turn!"})
                return

        player_count = len(room["players"])

        expected_length = get_expected_guess_length(player_count, guess_type)
        if len(guess) != expected_length:
            emit(
                "error", {"message": f"Guess must have exactly {expected_length} tiles"}
            )
            return

        is_correct = False
        target_tiles = []

        if player_count == 2:
            if guess_type in room["players"] and guess_type != player_id:
                target_tiles = room["players"][guess_type]["tiles"]
                is_correct = check_guess_correctness(guess, target_tiles)
                target_name = room["players"][guess_type]["name"]
            else:
                emit("error", {"message": "Invalid target player for guess"})
                return
        else:
            if guess_type == "center":
                target_tiles = room["center_tiles"]
                is_correct = check_guess_correctness(guess, target_tiles)
                target_name = "center code"
            else:
                emit("error", {"message": "Invalid guess type for this game mode"})
                return

        timestamp = time.time()
        room["players"][player_id]["guesses"].append(
            {
                "guess": guess,
                "target": guess_type,
                "correct": is_correct,
                "timestamp": timestamp,
            }
        )

        if is_correct and not room.get("first_successful_guess"):
            room["first_successful_guess"] = {
                "player_id": player_id,
                "timestamp": timestamp,
                "player_name": room["players"][player_id]["name"],
            }

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

        if player_count == 2:
            check_two_player_win_condition_new(
                socketio, game_manager, room_id, player_id, is_correct
            )
        else:
            check_center_guess_win_condition_new(
                socketio, game_manager, room_id, player_id, is_correct
            )

    @socketio.on("disconnect")
    def handle_disconnect():
        room_id = session.get("room_id")
        player_id = session.get("player_id")

        if room_id and player_id:
            print(f"Player {player_id} disconnected from room {room_id}")

            success = game_manager.disconnect_player(room_id, player_id, request.sid)

            if success and room_id in game_manager.rooms:
                room = game_manager.rooms[room_id]
                player_name = room["players"][player_id]["name"]

                emit(
                    "player_disconnected",
                    {
                        "player_name": player_name,
                        "player_id": player_id,
                        "message": f"{player_name} has disconnected",
                    },
                    room=room_id,
                )

                emit_room_player_update(socketio, game_manager, room_id)

    @socketio.on("get_game_info")
    def handle_get_game_info():
        room_id = session.get("room_id")

        if not room_id or room_id not in game_manager.rooms:
            emit("error", {"message": "Invalid room"})
            return

        room = game_manager.rooms[room_id]

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

        timer_info = {}
        for current_player_id in room["players"]:
            remaining_time = game_manager.get_remaining_time(room_id, current_player_id)
            timer_info[current_player_id] = {
                "player_name": room["players"][current_player_id]["name"],
                "remaining_time": remaining_time,
                "is_current_turn": room.get("current_turn") == current_player_id,
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
