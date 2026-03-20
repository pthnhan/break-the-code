from flask import render_template


def register_routes(app):
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/game/<room_id>")
    def game_room(room_id):
        return render_template("game.html", room_id=room_id)
