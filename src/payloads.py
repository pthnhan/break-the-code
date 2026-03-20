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
