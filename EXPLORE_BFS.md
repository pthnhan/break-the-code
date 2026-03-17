# EXPLORE_BFS

## Scope

- Explored the full working tree under `/home/pthnhan/workspace/break-the-code`, excluding `.git/` internals.
- Original files covered: 18 tracked files plus 1 ignored local file (`.vscode/settings.json`) = 19 files total.
- Generated during this exploration: `EXPLORE_BFS.md` (this document).
- Binary audio assets were treated as nodes through file metadata, template references, and sidecar metadata files rather than raw audio decoding.

## File Inventory

### Tracked files

- `.gitignore`
- `Procfile`
- `README.md`
- `app.py`
- `deploy.sh`
- `nixpacks.toml`
- `railway.json`
- `render.yaml`
- `requirements.txt`
- `static/css/style.css`
- `static/sounds/correct_answer.mp3`
- `static/sounds/correct_answer.mp3:Zone.Identifier`
- `static/sounds/turn_change.mp3`
- `static/sounds/turn_change.mp3:Zone.Identifier`
- `static/sounds/wrong_answer.wav`
- `static/sounds/wrong_answer.wav:Zone.Identifier`
- `templates/game.html`
- `templates/index.html`

### Ignored local file

- `.vscode/settings.json`

### Generated artifact

- `EXPLORE_BFS.md`

## BFS Traversal Log

The repo is small enough that the practical BFS starts from the root-level control files, then expands into rendered templates, then into shared/static assets, then into sibling metadata.

### Level 0 seed queue

- `README.md`
- `app.py`
- `requirements.txt`
- `Procfile`
- `nixpacks.toml`
- `railway.json`
- `render.yaml`
- `deploy.sh`
- `.gitignore`
- `.vscode/settings.json`

### Level 1 discoveries from Level 0

- `templates/index.html`
  - Discovered from `app.py` route `/` and from README file structure/setup docs.
- `templates/game.html`
  - Discovered from `app.py` route `/game/<room_id>` and from README file structure/setup docs.
- `static/css/style.css`
  - Discovered from README file structure and then confirmed by both templates.

### Level 2 discoveries from templates

- `static/sounds/turn_change.mp3`
  - Discovered from audio tag in `templates/game.html`.
- `static/sounds/wrong_answer.wav`
  - Discovered from audio tag in `templates/game.html`.
- `static/sounds/correct_answer.mp3`
  - Discovered from audio tag in `templates/game.html`.

### Level 3 discoveries from sound asset completeness scan

- `static/sounds/turn_change.mp3:Zone.Identifier`
- `static/sounds/wrong_answer.wav:Zone.Identifier`
- `static/sounds/correct_answer.mp3:Zone.Identifier`

These are Windows zone-transfer sidecar files. They are tracked in git and preserve original download origins.

### Completion notes

- No additional original repo files were discovered after the sound metadata pass.
- `.vscode/settings.json` was included for folder completeness even though it is ignored by `.gitignore` and not tracked.
- `EXPLORE_BFS.md` was generated after the read pass and is intentionally not treated as an input node in the original repo graph.

## High-Level Graph Summary

- `app.py` is the single backend and state-management hub.
- `templates/game.html` is the single largest frontend hub; it contains markup, a very large inline style block, and the full client runtime script.
- `static/css/style.css` is the shared stylesheet for both templates, but `templates/game.html` overrides and extends many of its selectors via inline CSS loaded later.
- All deployment files converge on the same Python entrypoint: `app:app` under `gunicorn` with `gevent`.
- The runtime is essentially a two-node application graph:
  - Server node: `app.py`
  - Client node: `templates/game.html`
- Everything else supports that core pair: landing page, CSS, sounds, deployment config, docs, and local tooling.

## Node Catalog

### Backend and runtime nodes

#### `app.py`

Role:
- Monolithic Flask + Flask-SocketIO application.
- Holds all room state in memory in `BreakTheCodeGame.rooms`.
- Owns game setup, reconnection, timers, scoring, and win-condition logic.

Primary structure:
- Imports Flask/SocketIO/stdlib at lines 1-6.
- Creates `app` and `socketio` at lines 8-10.
- Defines `BreakTheCodeGame` at line 12.
- Defines HTTP routes at lines 491-497.
- Defines Socket.IO event handlers from line 499 onward.
- Runs local dev server at line 1828.

Outbound file edges:
- `app.py -> templates/index.html`
  - `render_template('index.html')` at line 493.
- `app.py -> templates/game.html`
  - `render_template('game.html', room_id=room_id)` at line 497.

External/runtime edges:
- `app.py -> Flask`
- `app.py -> Flask-SocketIO`
- `app.py -> gevent`
- `app.py -> gunicorn`
- `app.py -> Python stdlib random/uuid/time`

State model:
- Room dictionary contains players, order, game state, tiles, question cards, center tiles, timers, penalties, score history, round number, and persisted game settings.

Core helper methods:
- `create_game_room()` line 16
- `create_tiles()` line 57
- `create_question_cards()` line 72
- `distribute_tiles()` line 97
- `join_room()` line 146
- `reconnect_player()` line 178
- `find_disconnected_player_by_name()` line 195
- `disconnect_player()` line 213
- `reorder_players()` line 224
- `set_player_ready()` line 250
- `all_players_ready()` line 267
- `start_game()` line 276
- `start_turn_timer()` line 400
- `get_remaining_time()` line 416
- `check_time_violation()` line 429
- `apply_time_penalty()` line 474

Guessing logic:
- Active path:
  - `handle_make_guess()` line 1147
  - `check_two_player_win_condition_new()` line 1394
  - `check_center_guess_win_condition_new()` line 1506
- Shared helpers:
  - `get_expected_guess_length()` line 1251
  - `check_guess_correctness()` line 1261
  - `update_player_scores()` line 1277
  - `reset_game_for_next_round()` line 1336
- Question evaluation:
  - `calculate_answer()` line 1014

Inbound Socket.IO edges:
- `create_room` line 499
- `join_room` line 539
- `player_ready` line 749
- `reorder_players` line 782
- `start_game` line 817
- `ask_question` line 909
- `make_guess` line 1147
- `get_room_state` line 1698
- `disconnect` line 1745
- `get_game_info` line 1783
- `get_all_timers` line 1800

Outbound Socket.IO edges:
- `room_created`
- `room_joined`
- `player_joined`
- `player_reconnected`
- `game_reconnected`
- `player_ready_update`
- `players_reordered`
- `game_started`
- `player_game_data`
- `question_asked`
- `questions_updated`
- `time_violation`
- `turn_changed`
- `guess_made`
- `final_round_started`
- `game_ended`
- `game_reset_to_waiting`
- `player_disconnected`
- `game_info_update`
- `all_timers_update`
- `error`

Important observations:
- The app is fully in-memory. There is no database, file persistence, or background worker.
- `SECRET_KEY` is hardcoded in `app.py` line 9.
- Legacy-looking methods `BreakTheCodeGame.handle_guess()` and `BreakTheCodeGame.should_end_game()` exist at lines 291 and 368, but the active guess flow does not call them.
- Imports `request`, `jsonify`, `leave_room`, `rooms`, and `json` appear present but are not part of the active file graph.

#### `requirements.txt`

Role:
- Python dependency lock/pin file for runtime and deployment.

Dependencies:
- Flask 2.3.3
- Flask-SocketIO 5.3.6
- python-socketio 5.8.0
- python-engineio 4.7.1
- gevent 23.9.1
- gevent-websocket 0.10.1
- gunicorn 21.2.0

Edges:
- `requirements.txt -> app.py`
  - Provides runtime dependencies imported by the server.
- `requirements.txt <- Procfile`
- `requirements.txt <- nixpacks.toml`
- `requirements.txt <- render.yaml`
- `requirements.txt <- deploy.sh`

#### `Procfile`

Role:
- Process declaration for platforms that honor Heroku-style Procfiles.

Edge:
- `Procfile -> app.py`
  - Runs `gunicorn --worker-class gevent -w 1 --bind 0.0.0.0:$PORT app:app`.

#### `nixpacks.toml`

Role:
- Nixpacks build config.

Edges:
- `nixpacks.toml -> requirements.txt`
  - Install command: `pip install -r requirements.txt`
- `nixpacks.toml -> app.py`
  - Start command uses `gunicorn ... app:app`

#### `railway.json`

Role:
- Railway deployment descriptor.

Edges:
- `railway.json -> app.py`
  - `startCommand` uses `gunicorn ... app:app`
- `railway.json -> route /`
  - `healthcheckPath` is `/`

#### `render.yaml`

Role:
- Render service definition.

Edges:
- `render.yaml -> requirements.txt`
  - `buildCommand: pip install -r requirements.txt`
- `render.yaml -> app.py`
  - `startCommand` uses `gunicorn ... app:app`
- `render.yaml -> SECRET_KEY env var`
  - Generates a `SECRET_KEY` value, but `app.py` does not read it.

Observation:
- There is config drift between `render.yaml` and `app.py`: the deployment file prepares `SECRET_KEY`, but the application uses a hardcoded secret instead.

#### `deploy.sh`

Role:
- Manual deployment helper script.

Edges:
- `deploy.sh -> git remote/origin main`
  - Pulls latest changes.
- `deploy.sh -> requirements.txt`
  - Runs `pip install -r requirements.txt`
- `deploy.sh -> app.py`
  - Launches `gunicorn ... app:app` on port `5000`
- `deploy.sh -> app.log`
  - Redirects server output there.

Observation:
- This script is operationally separate from platform configs but converges on the same `gunicorn app:app` entrypoint.

### Template and UI nodes

#### `templates/index.html`

Role:
- Landing page and room creation/join page.

Structure:
- Shared CSS link at line 7.
- Socket.IO CDN script at line 8.
- Two forms:
  - Create room form
  - Join room form
- Inline client script at lines 155-249.

Outbound file edges:
- `templates/index.html -> static/css/style.css`
  - `url_for('static', filename='css/style.css')`
- `templates/index.html -> app.py`
  - Emits `create_room` and `join_room`
- `templates/index.html -> templates/game.html`
  - Redirects browser to `/game/<room_id>?player_id=<player_id>`

External edges:
- `templates/index.html -> https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js`
- `templates/index.html -> https://boardgame.bg/break%20the%20code%20rules.pdf`
- `templates/index.html -> browser localStorage`
  - Stores `playerData_<room_id>`

Inbound Socket.IO edges:
- Listens for `room_created`
- Listens for `room_joined`
- Listens for `error`

Outbound Socket.IO edges:
- Emits `create_room`
- Emits `join_room`

Purpose in graph:
- Thin bootstrap client. It only creates or joins a room and then hands control to `templates/game.html`.

#### `templates/game.html`

Role:
- Main application client.
- Contains waiting room UI, game UI, timer UI, score history UI, reorder UI, sounds, and the entire gameplay client runtime.

Structure:
- Shared CSS link at line 7.
- Socket.IO CDN at line 8.
- Large inline `<style>` block at lines 9-2341.
- Main HTML body and UI containers at lines 2344-2543.
- Audio tags at lines 2525-2527.
- Main inline `<script>` block at lines 2546-4541.

Outbound file edges:
- `templates/game.html -> static/css/style.css`
  - Shared base stylesheet.
- `templates/game.html -> static/sounds/turn_change.mp3`
  - Audio tag line 2525.
- `templates/game.html -> static/sounds/wrong_answer.wav`
  - Audio tag line 2526.
- `templates/game.html -> static/sounds/correct_answer.mp3`
  - Audio tag line 2527.
- `templates/game.html -> app.py`
  - Emits almost all gameplay events.

External/browser edges:
- `templates/game.html -> https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js`
- `templates/game.html -> browser localStorage`
  - Reads/writes `playerData_<room_id>`
- `templates/game.html -> browser history API`
  - `window.history.replaceState(...)`
- `templates/game.html -> browser location API`
  - Redirects to `/`
- `templates/game.html -> browser prompt()`
  - Prompts for player name and duplicate-name retry.
- `templates/game.html -> clipboard API`
  - Copies room id.

Inbound Socket.IO edges:
- `player_joined`
- `room_state`
- `player_reconnected`
- `player_disconnected`
- `game_reconnected`
- `room_joined`
- `game_started`
- `time_violation`
- `player_game_data`
- `question_asked`
- `questions_updated`
- `turn_changed`
- `error`
- `connect`
- `players_reordered`
- `guess_made`
- `final_round_started`
- `game_ended`
- `player_ready_update`
- `disconnect`
- `game_reset_to_waiting`
- `all_timers_update`
- `game_info_update`

Outbound Socket.IO edges:
- `join_room`
- `player_ready`
- `start_game`
- `ask_question`
- `make_guess`
- `reorder_players`
- `get_game_info`
- `get_all_timers`

Major client responsibilities:
- Reconnection using localStorage-backed `player_id` and `session_key`
- Waiting room state rendering
- Start/ready controls
- Player reorder UI for host
- Personalized game data setup
- Question selection and number-choice UI
- Guess builder UI
- Turn indicator and final-round gating
- Game log rendering
- Timer polling and popup timer UI
- Scoreboard and score history rendering
- Celebration and sound playback

Inline CSS relationship:
- `templates/game.html` contains a second styling system layered on top of `static/css/style.css`.
- It overrides or redefines several shared selectors including:
  - `.log-entry`
  - `.scoreboard-section`
  - `.score-item`
  - `.waiting-room`
  - `.player-item`
  - `.question-card`
  - `.question-highlight`
- Because this inline CSS is loaded after the shared stylesheet, the game page versions win for overlapping selectors.

Important observations:
- `socket.on('players_reordered')` is registered twice:
  - once around line 2941
  - again around line 4039
- `socket.on('disconnect')` contains reconnection logic similar to the `connect` handler and tries to emit `join_room` while disconnected.
- `socket.on('room_state')` exists, but no active server emitter named `room_state` was found.
- Multiple timer CSS systems exist:
  - `.timer-clock-popup`
  - `.floating-timer-clock`
  - `.floating-timer-display`
  - only `.floating-timer-display` has an active DOM node in the markup.
- `updateClockHands()` exists at line 4443 and looks for `hourHand`, `minuteHand`, and `secondHand` DOM ids, but those ids are not present in the active markup.

#### `static/css/style.css`

Role:
- Shared stylesheet for both HTML templates.

Coverage:
- Base reset and layout
- Landing page sections
- Buttons and form controls
- Waiting room base layout
- Game interface grid
- Turn indicator base styles and animations
- Tile rendering
- Question cards
- Guess builder and available tile grid
- Status popups
- Celebration effects
- Responsive breakpoints
- Number selection buttons

Edges:
- `static/css/style.css <- templates/index.html`
- `static/css/style.css <- templates/game.html`

Relationship note:
- On the landing page, this is the only stylesheet.
- On the game page, this is the base layer and is partially overridden by `templates/game.html` inline CSS.

### Asset nodes

#### `static/sounds/turn_change.mp3`

Role:
- Turn-change sound effect.

Metadata:
- Binary audio file.
- Size: 34,734 bytes.

Edges:
- `templates/game.html -> static/sounds/turn_change.mp3`
  - Audio tag at line 2525.
- `playSound('turnChangeSound')` called on the active-turn event path.
- `static/sounds/turn_change.mp3:Zone.Identifier -> static/sounds/turn_change.mp3`

#### `static/sounds/wrong_answer.wav`

Role:
- Wrong-guess sound effect.

Metadata:
- Binary audio file.
- Size: 449,768 bytes.

Edges:
- `templates/game.html -> static/sounds/wrong_answer.wav`
  - Audio tag at line 2526.
- `playSound('wrongAnswerSound')` on wrong guess path.
- `static/sounds/wrong_answer.wav:Zone.Identifier -> static/sounds/wrong_answer.wav`

#### `static/sounds/correct_answer.mp3`

Role:
- Correct-guess sound effect.

Metadata:
- Binary audio file.
- Size: 313,637 bytes.

Edges:
- `templates/game.html -> static/sounds/correct_answer.mp3`
  - Audio tag at line 2527.
- `playSound('correctAnswerSound')` on correct guess path.
- `static/sounds/correct_answer.mp3:Zone.Identifier -> static/sounds/correct_answer.mp3`

#### `static/sounds/turn_change.mp3:Zone.Identifier`

Role:
- Windows zone-transfer metadata sidecar for `turn_change.mp3`.

Contents:
- `ZoneId=3`
- `HostUrl=https://soundbible.com/grab.php?id=1598&type=mp3`

Edge:
- Metadata-for `static/sounds/turn_change.mp3`

#### `static/sounds/wrong_answer.wav:Zone.Identifier`

Role:
- Windows zone-transfer metadata sidecar for `wrong_answer.wav`.

Contents:
- `ZoneId=3`
- `ReferrerUrl=https://mixkit.co/`
- `HostUrl=https://assets.mixkit.co/active_storage/sfx/948/948.wav`

Edge:
- Metadata-for `static/sounds/wrong_answer.wav`

#### `static/sounds/correct_answer.mp3:Zone.Identifier`

Role:
- Windows zone-transfer metadata sidecar for `correct_answer.mp3`.

Contents:
- `ZoneId=3`
- `HostUrl=https://soundbible.com/grab.php?id=1260&type=mp3`

Edge:
- Metadata-for `static/sounds/correct_answer.mp3`

### Documentation and local tooling nodes

#### `README.md`

Role:
- Human-facing project overview, setup guide, rules summary, feature list, troubleshooting, and security/reconnection notes.

Edges:
- `README.md -> app.py`
  - Names it as main Flask application.
- `README.md -> requirements.txt`
  - Installation step.
- `README.md -> templates/index.html`
- `README.md -> templates/game.html`
- `README.md -> static/css/style.css`
- `README.md -> official rules PDF`

Observation:
- README reflects the main app architecture, but it does not fully describe:
  - deployment files
  - sound assets
  - tracked zone-identifier sidecars
  - the large inline CSS and client runtime contained in `templates/game.html`

#### `.gitignore`

Role:
- Generic Python/IDE/environment ignore file with some project-specific additions.

Key edges:
- `.gitignore -> .vscode/settings.json`
  - `.vscode/` is ignored at line 182.

Graph relevance:
- Explains why `.vscode/settings.json` exists locally but is outside the tracked repo graph.

#### `.vscode/settings.json`

Role:
- Local editor preference file.

Contents:
- `chatgpt.openOnStartup: false`

Edges:
- No runtime edges.
- Inbound tooling edge from `.gitignore` ignore rule.

Observation:
- Included only for folder completeness, not because it participates in the application.

## Edge Map

### HTTP and template edges

| Source | Edge | Target | Evidence |
| --- | --- | --- | --- |
| `app.py` | route `/` renders | `templates/index.html` | line 493 |
| `app.py` | route `/game/<room_id>` renders | `templates/game.html` | line 497 |
| `templates/index.html` | links stylesheet | `static/css/style.css` | line 7 |
| `templates/game.html` | links stylesheet | `static/css/style.css` | line 7 |
| `templates/index.html` | redirects browser to | `templates/game.html` route | lines 218, 235 |

### Deployment edges

| Source | Edge | Target |
| --- | --- | --- |
| `Procfile` | starts | `app.py` via `gunicorn ... app:app` |
| `nixpacks.toml` | installs | `requirements.txt` |
| `nixpacks.toml` | starts | `app.py` via `gunicorn ... app:app` |
| `railway.json` | starts | `app.py` via `gunicorn ... app:app` |
| `render.yaml` | installs | `requirements.txt` |
| `render.yaml` | starts | `app.py` via `gunicorn ... app:app` |
| `deploy.sh` | installs | `requirements.txt` |
| `deploy.sh` | starts | `app.py` via `gunicorn ... app:app` |

### Static asset edges

| Source | Edge | Target | Evidence |
| --- | --- | --- | --- |
| `templates/game.html` | audio tag | `static/sounds/turn_change.mp3` | line 2525 |
| `templates/game.html` | audio tag | `static/sounds/wrong_answer.wav` | line 2526 |
| `templates/game.html` | audio tag | `static/sounds/correct_answer.mp3` | line 2527 |
| `static/sounds/turn_change.mp3:Zone.Identifier` | metadata-for | `static/sounds/turn_change.mp3` | file contents |
| `static/sounds/wrong_answer.wav:Zone.Identifier` | metadata-for | `static/sounds/wrong_answer.wav` | file contents |
| `static/sounds/correct_answer.mp3:Zone.Identifier` | metadata-for | `static/sounds/correct_answer.mp3` | file contents |

## Socket.IO Event Matrix

### Landing page flow

| Client file | Emits | Server handler in `app.py` | Server emits back | Client listeners |
| --- | --- | --- | --- | --- |
| `templates/index.html` | `create_room` | `handle_create_room` | `room_created`, `error` | `templates/index.html` |
| `templates/index.html` | `join_room` | `handle_join_room` | `room_joined`, `error` | `templates/index.html` |

### Main game flow

| Client file | Emits | Server handler in `app.py` | Server emits back | Client listener file |
| --- | --- | --- | --- | --- |
| `templates/game.html` | `join_room` | `handle_join_room` | `room_joined`, `player_joined`, `player_reconnected`, `game_reconnected`, `error` | `templates/game.html` |
| `templates/game.html` | `player_ready` | `handle_player_ready` | `player_ready_update`, `error` | `templates/game.html` |
| `templates/game.html` | `reorder_players` | `handle_reorder_players` | `players_reordered`, `error` | `templates/game.html` |
| `templates/game.html` | `start_game` | `handle_start_game` | `game_started`, `player_game_data`, `error` | `templates/game.html` |
| `templates/game.html` | `ask_question` | `handle_ask_question` | `question_asked`, `questions_updated`, `turn_changed`, optional `time_violation`, `error` | `templates/game.html` |
| `templates/game.html` | `make_guess` | `handle_make_guess` | `guess_made`, plus downstream `turn_changed` / `final_round_started` / `game_ended` / `game_reset_to_waiting`, optional `time_violation`, `error` | `templates/game.html` |
| `templates/game.html` | `get_game_info` | `handle_get_game_info` | `game_info_update`, `error` | `templates/game.html` |
| `templates/game.html` | `get_all_timers` | `handle_get_all_timers` | `all_timers_update`, `error` | `templates/game.html` |
| Socket disconnect | implicit transport event | `handle_disconnect` | `player_disconnected`, `player_joined` | `templates/game.html` |

## One-Sided, Duplicate, or Legacy Relationships

These edges exist in source but are not symmetrical or not clearly active.

- `templates/game.html` listens for `room_state`, but `app.py` does not emit `room_state`.
- `app.py` exposes `get_room_state`, but no client emitter for `get_room_state` was found.
- `BreakTheCodeGame.handle_guess()` and `BreakTheCodeGame.should_end_game()` still exist, but the active guess pipeline uses `handle_make_guess()` plus the newer `check_*_win_condition_new()` helpers.
- `templates/game.html` has two separate `socket.on('players_reordered')` registrations.
- `templates/game.html` has reconnect logic in both `connect` and `disconnect` handlers; the `disconnect` path tries to emit over a broken connection and therefore looks like leftover or redundant behavior.
- `templates/game.html` defines several unused timer styling systems (`.timer-clock-popup`, `.floating-timer-clock`) while only `.floating-timer-display` is instantiated in the DOM.
- `render.yaml` generates `SECRET_KEY`, but `app.py` never consumes it.
- `.vscode/settings.json` exists in the folder but is intentionally outside the tracked repo graph because `.gitignore` ignores `.vscode/`.
- `EXPLORE_BFS.md` is a generated documentation node, not part of the original application graph.

## Final BFS Conclusion

The repository is a small monolith with one backend file (`app.py`), one lightweight landing page (`templates/index.html`), one very large gameplay page (`templates/game.html`), one shared stylesheet (`static/css/style.css`), three sound assets plus their tracked Windows metadata sidecars, and several deployment wrappers that all point to the same `gunicorn app:app` entrypoint.

In graph terms:

- Primary runtime hub: `app.py`
- Primary client hub: `templates/game.html`
- Shared style node: `static/css/style.css`
- Deployment fan-in: `Procfile`, `nixpacks.toml`, `railway.json`, `render.yaml`, `deploy.sh`
- Documentation/tooling side nodes: `README.md`, `.gitignore`, `.vscode/settings.json`
- Asset side nodes: `static/sounds/*` and `*:Zone.Identifier`

The BFS pass is complete for every non-`.git` file present in the folder.
