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


def calculate_answer(question, tiles, chosen_number=None):
    """Calculate the answer to a question based on tiles."""
    allowed_numbers = get_allowed_chosen_numbers(question)
    if allowed_numbers is not None:
        if chosen_number is None:
            return "Error: Number not chosen"

        if chosen_number not in allowed_numbers:
            return "Error: Invalid number choice"

        target_positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == chosen_number:
                position = chr(65 + i)
                target_positions.append(position)
        return (
            f"Position(s): {', '.join(target_positions)}"
            if target_positions
            else "Not found"
        )

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
    elif "left-most tiles" in question:
        left_tiles = tiles[:3] if len(tiles) >= 5 else tiles[:2]
        return sum(t["number"] for t in left_tiles)
    elif "right-most tiles" in question:
        right_tiles = tiles[-3:] if len(tiles) >= 5 else tiles[-2:]
        return sum(t["number"] for t in right_tiles)
    elif "sum of your central tiles" in question:
        if len(tiles) >= 5:
            central_tiles = tiles[1:4]
            return sum(t["number"] for t in central_tiles)
        elif len(tiles) >= 4:
            central_tiles = tiles[1:3]
            return sum(t["number"] for t in central_tiles)
        else:
            return "Not applicable"
    elif "What is the **sum of your tiles**" in question:
        return sum(t["number"] for t in tiles)
    elif "Where are your **#5** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == 5:
                positions.append(chr(65 + i))
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"
    elif "Where are your **#0** tiles" in question:
        positions = []
        for i, tile in enumerate(tiles):
            if tile["number"] == 0:
                positions.append(chr(65 + i))
        return f"Position(s): {', '.join(positions)}" if positions else "Not found"
    elif "Is your **C tile greater than 4**" in question:
        if len(tiles) >= 3:
            c_tile = tiles[2]
            return "Yes" if c_tile["number"] > 4 else "No"
        else:
            return "Not applicable"
    elif (
        "What is the **difference between your highest and lowest numbers**" in question
    ):
        numbers = [t["number"] for t in tiles]
        return max(numbers) - min(numbers) if numbers else 0

    return "Unknown question"


def get_expected_guess_length(player_count, guess_type):
    """Get expected number of tiles in a guess."""
    if player_count == 2:
        return 5
    elif player_count == 3:
        return 5
    elif player_count == 4:
        return 4
    return 0


def check_guess_correctness(guess, target_tiles):
    """Check if a guess matches the target tiles exactly."""
    if len(guess) != len(target_tiles):
        return False

    guess_tiles = [{"number": tile["number"], "color": tile["color"]} for tile in guess]
    target_tiles_copy = [
        {"number": tile["number"], "color": tile["color"]} for tile in target_tiles
    ]

    guess_tiles.sort(key=lambda x: (x["number"], x["color"]))
    target_tiles_copy.sort(key=lambda x: (x["number"], x["color"]))

    return guess_tiles == target_tiles_copy
