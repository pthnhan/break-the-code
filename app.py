import os

from dotenv import load_dotenv
from flask import Flask
from flask_socketio import SocketIO

from src.game_handlers import register_game_handlers
from src.game_manager import BreakTheCodeGame
from src.lobby_handlers import register_lobby_handlers
from src.routes import register_routes

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "break_the_code_secret_key_2024")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

game_manager = BreakTheCodeGame()

register_routes(app)
register_lobby_handlers(socketio, game_manager)
register_game_handlers(socketio, game_manager)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
