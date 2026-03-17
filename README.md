# 🔍 BREAK THE CODE - Web Board Game

A web-based implementation of the logical deduction board game "Break the Code" by Ryohei Kurahashi.  
**Web Implementation:** pthnhan

## 🎯 Game Overview

BREAK THE CODE is a logical deduction game where players use question cards to gather information and deduce the hidden tiles of their opponents or center tiles. Put on your thinking cap and use logic to crack the code!

### Official Rules

For complete and detailed rules, refer to the [official rulebook PDF](https://boardgame.bg/break%20the%20code%20rules.pdf).

### Game Rules

**Objective:**
- **2 Players:** Guess all of your opponent's tiles in correct order
- **3-4 Players:** Guess the face-down center tiles in correct order

**Setup:**
- Each player receives 4-5 tiles arranged in numerical ascending order behind their screen
- Black tiles come before white tiles when numbers are identical
- 4 question cards are available for players to ask each other
- Players take turns asking questions to gather information

**Tiles:**
- Numbers 0, 1, 2, 3, 4, 6, 7, 8, 9 (both white and black colors) - 18 tiles
- Two green 5s (special tiles) - 2 tiles
- Total: 20 tiles with strategic color distribution

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone or download this repository**
   ```bash
   cd break-the-code-webapp
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a local environment file**
   ```bash
   cat <<'EOF' > .env
   PORT=5000
   SECRET_KEY=break_the_code_secret_key_2024
   EOF
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:5000`

## 🚀 VPS CI/CD With GitHub Actions

This repo includes a GitHub Actions workflow at `.github/workflows/deploy.yml` that deploys on every push to `main` by SSHing into your VPS and running `sh deploy.sh`.

Previous platform-specific deployment files have been removed so the repo now documents and uses a single deployment path: GitHub Actions to your VPS over SSH.

### One-time VPS setup

1. Clone this repository onto your VPS in a stable directory such as `/srv/break-the-code`
2. Create the server-side `.env` file in that directory with the values you want for production
3. Make sure the VPS has these commands available:
   - `git`
   - `python3`
   - `python3 -m venv`
   - `pgrep` is recommended but optional
4. Make sure the cloned repository on the VPS can `git pull`
   - For a private repo, this usually means configuring a deploy key or SSH access on the server

### Required GitHub Actions secrets

Add these in GitHub: `Settings -> Secrets and variables -> Actions`

- `VPS_HOST`: server hostname or IP
- `VPS_USER`: SSH username
- `VPS_APP_DIR`: absolute path to the app directory on the server, for example `/srv/break-the-code`
- `VPS_SSH_KEY`: private SSH key used by GitHub Actions to connect to the VPS

### Optional GitHub Actions secrets

- `VPS_PORT`: SSH port if not `22`
- `VPS_KNOWN_HOSTS`: recommended pinned host key entry for strict SSH host verification

### Deployment behavior

- Push to `main`
- GitHub Actions opens an SSH session to the VPS
- The workflow changes into `VPS_APP_DIR`
- The workflow runs `DEPLOY_BRANCH=<pushed-branch> sh deploy.sh`
- `deploy.sh` pulls the latest code, refreshes `.venv`, installs dependencies, and restarts Gunicorn

### Example server `.env`

```bash
PORT=5000
SECRET_KEY=replace-this-in-production
```

## 🎮 How to Play

### Starting a Game

1. **Create a Room:**
   - Enter your name
   - Choose maximum players (2-4)
   - Click "Create Game Room"
   - Share the Room ID with other players

2. **Join a Room:**
   - Enter your name
   - Enter the Room ID shared by the host
   - Click "Join Game"

3. **Start the Game:**
   - Wait for all players to join and be ready
   - Click "Start Game" when all players are ready

### Playing the Game

1. **View Your Tiles:**
   - Your tiles are displayed in numerical order
   - Remember their colors and positions (A, B, C, D, E)

2. **Ask Strategic Questions:**
   - On your turn, select a question card from the 4 available
   - Some questions require choosing a number before asking
   - All players will see the question and answers

3. **Gather Information:**
   - Use the answers to deduce other players' tiles
   - Pay attention to mathematical clues and position information
   - Track revealed information in the game log

4. **Make Your Guess:**
   - When confident, make your final guess
   - Arrange tiles in the exact order you think they are
   - Submit your guess to attempt to win!

### Sample Questions

- "How many **white tiles** do you have?"
- "How many **even** tiles you have?"
- "What is the **sum of your tiles**?"
- "Where are your **#5** tiles?"
- "Which neighboring tiles have **consecutive numbers**?"
- "Where are your **#8** or **#9** tiles? (Choose number first)"

## 🎲 Game Features

### Real-time Multiplayer
- WebSocket-based real-time communication
- Instant updates for all players
- Turn-based strategic gameplay

### Interactive Interface
- Beautiful, modern UI design with gradient backgrounds
- Responsive design for mobile and desktop
- Visual tile representation with colors (white, black, green)
- Comprehensive game log to track all questions and answers

### Game Modes
- **2-Player Mode:** 5 tiles per player
- **3-Player Mode:** 5 tiles per player + 5 center tiles
- **4-Player Mode:** 4 tiles per player + 4 center tiles

### Smart Question System
- 21 different strategic question types
- Automatic answer calculation
- Number selection interface for conditional questions
- Real-time question deck management

### Win Conditions
- **2-Player:** Strategic final round system with catch-up mechanics
- **3-4 Player:** First correct guess triggers final round for all players
- Score tracking across multiple rounds

## 🛠 Technical Details

### Tech Stack
- **Backend:** Python Flask + SocketIO
- **Frontend:** HTML5, CSS3, JavaScript
- **Real-time Communication:** WebSockets
- **Styling:** Modern CSS with gradients and animations

### File Structure
```
break-the-code/
├── .github/
│   └── workflows/
│       └── deploy.yml     # GitHub Actions VPS deploy workflow
├── app.py                 # Main Flask application
├── deploy.sh              # Server-side deploy script run over SSH
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── templates/
│   ├── index.html         # Landing page
│   └── game.html          # Game interface
└── static/
    ├── css/
    │   └── style.css      # Shared styling
    └── sounds/            # Game sound effects
```

### Game Logic
- **Tile Management:** Automatic distribution and sorting
- **Question Processing:** Smart answer calculation with number selection
- **Turn Management:** Automatic turn rotation with final round mechanics
- **Game State:** Real-time synchronization and score tracking

## 🎨 Design Features

- **Modern UI:** Gradient backgrounds and smooth animations
- **Responsive Design:** Works on desktop, tablet, and mobile
- **Visual Feedback:** Hover effects and interactive elements
- **Accessibility:** Clear typography and color contrast
- **Real-time Updates:** Instant feedback for all game actions

## 🔧 Customization

### Adding New Questions
Edit the `create_question_cards()` method in `app.py` to add new question types.

### Modifying Game Rules
Adjust tile distribution in the `distribute_tiles()` method for different game variants.

### Styling Changes
Modify `static/css/style.css` to customize the appearance.

## 🎯 Strategy Tips

1. **Start with Counting Questions:** Ask about colors and basic counts first
2. **Use Mathematical Questions:** Sum and position questions provide valuable info
3. **Process of Elimination:** Use answers to eliminate possibilities systematically
4. **Pattern Recognition:** Look for consecutive numbers and color patterns
5. **Strategic Timing:** Save specific position questions for when you have partial information
6. **Number Selection:** Choose numbers wisely for conditional questions

## 🐛 Troubleshooting

### Common Issues

**Can't connect to game:**
- Ensure Python and dependencies are installed
- Check your `.env` file and make sure `PORT=5000` (or use the port you want)
- Try refreshing the browser

**Game not starting:**
- Make sure you have at least 2 players
- Check that all players have clicked "Ready"

**Questions not working:**
- Ensure it's your turn to ask
- Select a number for questions that require it

## 📱 Browser Compatibility

- Chrome (recommended)
- Firefox
- Safari
- Edge

## 🤝 Contributing

Feel free to contribute improvements:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is for educational and entertainment purposes.

## �� Acknowledgments

- **Original Game Designer:** Ryohei Kurahashi
- **Official Rules:** [Break the Code Rules PDF](https://boardgame.bg/break%20the%20code%20rules.pdf)
- **Web Implementation:** pthnhan
- Built with modern web technologies for optimal user experience

---

**Enjoy breaking the code! 🔍🎯** 

## �� BREAK THE CODE

## Recent Bug Fixes 🔧

### Fixed Issues (Latest Update):
1. **Player Identity Security**: Fixed security vulnerability where anyone could join with the same name
   - Each player now has a unique session key for secure identification
   - No more unauthorized access to other players' sessions
   - Proper authentication system prevents impersonation

2. **Mid-Game Disconnection Handling**: Players can now properly reconnect during active games
   - Other players are notified when someone disconnects (🔴 indicator)
   - Disconnected players can rejoin ongoing games with full state restoration
   - Game continues seamlessly with proper turn management
   - Connection status is displayed in real-time

3. **Duplicate Player Names**: Players can no longer join a room with the same name as an existing player
   - The system validates names and prevents duplicates
   - Users get clear error messages and can choose a different name

### New Security Features:
- **Session Key Authentication**: Each player gets a unique, secure session key
- **Secure Reconnection**: Only the original player can reconnect using their session key
- **Connection Status Tracking**: Real-time display of who's connected/disconnected
- **Game State Restoration**: Mid-game reconnections restore complete game state

### How Secure Reconnection Works:
- When you join a room, you receive a unique session key stored securely in your browser
- If you accidentally leave or get disconnected, your session key allows secure reconnection
- Only you can reconnect to your player slot - no one else can impersonate you
- During active games, you'll rejoin exactly where you left off with all your tiles and progress
- Other players see real-time connection status updates
