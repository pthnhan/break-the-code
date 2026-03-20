import time

from src.payloads import build_room_players


def emit_room_player_update(socketio, game_manager, room_id):
    """Broadcast the latest ordered room/player state."""
    if room_id not in game_manager.rooms:
        return

    room = game_manager.rooms[room_id]
    socketio.emit(
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


def update_player_scores(game_manager, room_id, winners, is_draw):
    """Update player scores based on game results."""
    room = game_manager.rooms[room_id]

    round_result = {
        "round": room["round_number"] + 1,
        "players": [],
        "is_draw": is_draw,
        "timestamp": time.time(),
    }

    for player_id in room["players"]:
        player_data = room["players"][player_id]
        is_winner = player_id in winners

        if is_draw and is_winner:
            result = "Draw"
        elif is_winner:
            result = "Win"
        else:
            result = "Loss"

        if is_winner:
            base_points = 100
            total_penalties = room["player_penalties"].get(player_id, 0)
            final_points = max(0, base_points - total_penalties)

            old_score = player_data["score"]
            room["players"][player_id]["score"] += final_points

            print(
                f"DEBUG: Player {player_id} ({player_data['name']}) awarded {final_points} points (100 - {total_penalties} penalties)"
            )
        else:
            final_points = 0
            total_penalties = room["player_penalties"].get(player_id, 0)
            old_score = player_data["score"]

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

    room["score_history"].append(round_result)
    room["round_number"] += 1


def reset_game_for_next_round(socketio, game_manager, room_id):
    """Reset game state for next round while preserving scores and players."""
    room = game_manager.rooms[room_id]

    room["game_state"] = "waiting"
    room["current_turn"] = None
    room["final_round"] = False
    room["final_round_player"] = None
    room["final_round_started_emitted"] = False
    room["first_successful_guess"] = None
    room["winners"] = None
    room["center_tiles"] = []
    room["center_tiles_count"] = 0
    room["used_question_cards"] = []
    room["correct_guessers"] = []
    room["first_correct_guesser"] = None

    room["turn_start_time"] = None
    room["turn_timers"] = {}
    room["player_penalties"] = {}
    room["player_turn_start_times"] = {}

    room["ready_players"] = set()

    for player_id in room["players"]:
        player = room["players"][player_id]
        player["tiles"] = []
        player["guesses"] = []
        player["ready"] = False
        player.pop("correct_guess", None)
        player.pop("guess_timestamp", None)
        player.pop("center_guess_correct", None)
        player.pop("has_guessed", None)
        player.pop("time_violation_loss", None)

    if room.get("host") and room["host"] in room["players"]:
        room["players"][room["host"]]["ready"] = True
        room["ready_players"].add(room["host"])

    socketio.emit(
        "game_reset_to_waiting",
        {
            "players": build_room_players(room),
            "game_settings": room["game_settings"],
            "score_history": room["score_history"],
            "round_number": room["round_number"],
        },
        room=room_id,
    )


def check_two_player_win_condition_new(
    socketio, game_manager, room_id, guessing_player_id, is_correct
):
    """Check win condition for 2-player game with current final-round rules."""
    room = game_manager.rooms[room_id]
    players = room["player_order"]

    player_1 = players[0]
    player_2 = players[1]

    if room.get("final_round"):
        if guessing_player_id == player_2:
            room["game_state"] = "finished"
            if is_correct:
                room["winners"] = [player_1, player_2]
                update_player_scores(
                    game_manager, room_id, [player_1, player_2], is_draw=True
                )

                player_1_penalties = room["player_penalties"].get(player_1, 0)
                player_2_penalties = room["player_penalties"].get(player_2, 0)
                player_1_points = max(0, 100 - player_1_penalties)
                player_2_points = max(0, 100 - player_2_penalties)

                socketio.emit(
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
                room["winners"] = [player_1]
                update_player_scores(game_manager, room_id, [player_1], is_draw=False)

                player_1_penalties = room["player_penalties"].get(player_1, 0)
                player_1_points = max(0, 100 - player_1_penalties)

                socketio.emit(
                    "game_ended",
                    {
                        "winners": [room["players"][player_1]["name"]],
                        "message": f"{room['players'][player_1]['name']} wins! (+{player_1_points} pts)",
                        "is_draw": False,
                        "redirect_to_waiting": True,
                    },
                    room=room_id,
                )
            reset_game_for_next_round(socketio, game_manager, room_id)
        return

    if is_correct:
        room["players"][guessing_player_id]["correct_guess"] = True
        room["players"][guessing_player_id]["guess_timestamp"] = time.time()

        if guessing_player_id == player_2:
            room["game_state"] = "finished"
            room["winners"] = [player_2]
            update_player_scores(game_manager, room_id, [player_2], is_draw=False)

            player_2_penalties = room["player_penalties"].get(player_2, 0)
            player_2_points = max(0, 100 - player_2_penalties)

            socketio.emit(
                "game_ended",
                {
                    "winners": [room["players"][player_2]["name"]],
                    "message": f"{room['players'][player_2]['name']} wins! Game over. (+{player_2_points} pts)",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            reset_game_for_next_round(socketio, game_manager, room_id)
            return

        if guessing_player_id == player_1:
            room["final_round"] = True
            room["final_round_player"] = player_2
            room["current_turn"] = player_2

            game_manager.start_turn_timer(room_id, player_2)

            socketio.emit(
                "final_round_started",
                {
                    "message": f"{room['players'][player_1]['name']} guessed correctly! {room['players'][player_2]['name']} has one final chance to guess.",
                    "first_winner": room["players"][player_1]["name"],
                    "final_player": player_2,
                    "final_player_name": room["players"][player_2]["name"],
                },
                room=room_id,
            )

            socketio.emit(
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
    else:
        next_player_id = player_1 if guessing_player_id == player_2 else player_2

        room["current_turn"] = next_player_id
        game_manager.start_turn_timer(room_id, next_player_id)
        socketio.emit(
            "turn_changed",
            {
                "current_turn": room["current_turn"],
                "current_player_name": room["players"][room["current_turn"]]["name"],
                "final_round": False,
            },
            room=room_id,
        )
        return


def check_center_guess_win_condition_new(
    socketio, game_manager, room_id, guessing_player_id, is_correct
):
    """Check win condition for 3-4 player game with center guessing."""
    room = game_manager.rooms[room_id]
    players = room["player_order"]
    num_players = len(players)

    player_position = players.index(guessing_player_id) + 1

    print(
        f"DEBUG: Player {player_position} ({room['players'][guessing_player_id]['name']}) guessed {'correctly' if is_correct else 'incorrectly'}"
    )

    if is_correct:
        if "correct_guessers" not in room:
            room["correct_guessers"] = []

        if guessing_player_id not in room["correct_guessers"]:
            room["correct_guessers"].append(guessing_player_id)
            print(
                f"DEBUG: Added {room['players'][guessing_player_id]['name']} to correct guessers. Total: {[room['players'][pid]['name'] for pid in room['correct_guessers']]}"
            )

        if player_position == num_players:
            print(
                f"DEBUG: Player {player_position} (last player) guessed correctly, ending game immediately"
            )
            room["game_state"] = "finished"
            update_player_scores(
                game_manager, room_id, room["correct_guessers"], is_draw=False
            )

            winner_details = []
            for winner_id in room["correct_guessers"]:
                penalties = room["player_penalties"].get(winner_id, 0)
                points = max(0, 100 - penalties)
                winner_details.append(
                    f"{room['players'][winner_id]['name']}: +{points} pts"
                )

            winner_names = [
                room["players"][pid]["name"] for pid in room["correct_guessers"]
            ]
            winners_msg = ", ".join(winner_details)

            socketio.emit(
                "game_ended",
                {
                    "winners": winner_names,
                    "message": f"Game Over! Winners: {winners_msg}",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            reset_game_for_next_round(socketio, game_manager, room_id)
            return

        if not room.get("final_round"):
            print(
                f"DEBUG: Starting final round because Player {player_position} guessed correctly first"
            )
            room["final_round"] = True
            room["first_correct_guesser"] = guessing_player_id

            for pid in players:
                room["players"][pid]["has_guessed"] = False

            room["players"][guessing_player_id]["has_guessed"] = True
        else:
            print(f"DEBUG: Player {player_position} guessed correctly in final round")
            room["players"][guessing_player_id]["has_guessed"] = True

        first_guesser_pos = players.index(room["first_correct_guesser"]) + 1
        next_player = None

        print(
            f"DEBUG: First guesser was Player {first_guesser_pos}, looking for next player..."
        )

        for pos in range(first_guesser_pos + 1, num_players + 1):
            if pos - 1 < len(players):
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

            game_manager.start_turn_timer(room_id, next_player)

            socketio.emit(
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
            print("DEBUG: All eligible players have guessed, ending game")
            room["game_state"] = "finished"
            update_player_scores(
                game_manager, room_id, room["correct_guessers"], is_draw=False
            )

            winner_details = []
            for winner_id in room["correct_guessers"]:
                penalties = room["player_penalties"].get(winner_id, 0)
                points = max(0, 100 - penalties)
                winner_details.append(
                    f"{room['players'][winner_id]['name']}: +{points} pts"
                )

            winner_names = [
                room["players"][pid]["name"] for pid in room["correct_guessers"]
            ]
            winners_msg = ", ".join(winner_details)

            socketio.emit(
                "game_ended",
                {
                    "winners": winner_names,
                    "message": f"Game Over! Winners: {winners_msg}",
                    "is_draw": False,
                    "redirect_to_waiting": True,
                },
                room=room_id,
            )
            reset_game_for_next_round(socketio, game_manager, room_id)
    else:
        print(f"DEBUG: Player {player_position} guessed incorrectly")
        if room.get("final_round"):
            room["players"][guessing_player_id]["has_guessed"] = True

            first_guesser_pos = players.index(room["first_correct_guesser"]) + 1
            next_player = None

            print(
                f"DEBUG: In final round, first guesser was Player {first_guesser_pos}"
            )

            for pos in range(first_guesser_pos + 1, num_players + 1):
                if pos - 1 < len(players):
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
                socketio.emit(
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
                print(
                    "DEBUG: No more players to guess after incorrect guess, ending game"
                )
                room["game_state"] = "finished"
                update_player_scores(
                    game_manager, room_id, room["correct_guessers"], is_draw=False
                )

                winner_details = []
                for winner_id in room["correct_guessers"]:
                    penalties = room["player_penalties"].get(winner_id, 0)
                    points = max(0, 100 - penalties)
                    winner_details.append(
                        f"{room['players'][winner_id]['name']}: +{points} pts"
                    )

                winner_names = [
                    room["players"][pid]["name"] for pid in room["correct_guessers"]
                ]
                winners_msg = ", ".join(winner_details)

                socketio.emit(
                    "game_ended",
                    {
                        "winners": winner_names,
                        "message": f"Game Over! Winners: {winners_msg}",
                        "is_draw": False,
                        "redirect_to_waiting": True,
                    },
                    room=room_id,
                )
                reset_game_for_next_round(socketio, game_manager, room_id)
        else:
            current_index = players.index(guessing_player_id)
            next_index = (current_index + 1) % len(players)
            next_player_id = players[next_index]

            room["current_turn"] = next_player_id

            game_manager.start_turn_timer(room_id, next_player_id)

            socketio.emit(
                "turn_changed",
                {
                    "current_turn": next_player_id,
                    "current_player_name": room["players"][next_player_id]["name"],
                    "final_round": False,
                },
                room=room_id,
            )
