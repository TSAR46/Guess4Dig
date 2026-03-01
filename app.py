from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room
import random

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*")

waiting_player = None
games = {}

def generate_secret():
    digits = []
    while len(digits) < 4:
        num = str(random.randint(0, 9))
        if num not in digits:
            digits.append(num)
    return "".join(digits)

def count_matches(secret, guess):
    secret_list = list(secret)
    count = 0
    for digit in guess:
        if digit in secret_list:
            count += 1
            secret_list.remove(digit)
    return count

@app.route("/")
def index():
    return render_template("index.html")

@socketio.on("connect")
def handle_connect():
    global waiting_player

    if waiting_player is None:
        waiting_player = request.sid
        socketio.emit("waiting", to=request.sid)
    else:
        game_id = waiting_player + "#" + request.sid

        games[game_id] = create_new_game(waiting_player, request.sid)

        socketio.server.enter_room(waiting_player, game_id)
        join_room(game_id)

        send_secrets(game_id)

        waiting_player = None

def create_new_game(player1, player2):
    return {
        "player1": player1,
        "player2": player2,
        "player1_secret": generate_secret(),
        "player2_secret": generate_secret(),
        "current_turn": player1,
        "active": True
    }

def send_secrets(game_id):
    game = games[game_id]

    socketio.emit("yourSecret", 
        {"secret": game["player1_secret"]}, 
        to=game["player1"])

    socketio.emit("yourSecret", 
        {"secret": game["player2_secret"]}, 
        to=game["player2"])

    socketio.emit("startGame", {
        "player1": game["player1"],
        "player2": game["player2"],
        "currentTurn": game["current_turn"]
    }, room=game_id)

@socketio.on("makeGuess")
def handle_guess(data):
    guess = data.get("guess")

    game_id = None
    for g in games:
        if request.sid in [games[g]["player1"], games[g]["player2"]]:
            game_id = g
            break

    if not game_id:
        return

    game = games[game_id]

    if not game["active"] or game["current_turn"] != request.sid:
        return

    opponent_secret = (
        game["player2_secret"]
        if request.sid == game["player1"]
        else game["player1_secret"]
    )

    correct_count = count_matches(opponent_secret, guess)

    socketio.emit("guessResult", {
        "player": request.sid,
        "guess": guess,
        "correctCount": correct_count
    }, room=game_id)

    if guess == opponent_secret:
        game["active"] = False
        socketio.emit("gameOver", {
            "winner": request.sid
        }, room=game_id)
        return

    # Switch turn
    game["current_turn"] = (
        game["player2"]
        if request.sid == game["player1"]
        else game["player1"]
    )

    socketio.emit("turnChanged", {
        "currentTurn": game["current_turn"]
    }, room=game_id)

@socketio.on("restartGame")
def restart_game():
    for g in games:
        if request.sid in [games[g]["player1"], games[g]["player2"]]:
            game_id = g
            break

    game = games[game_id]

    games[game_id] = create_new_game(game["player1"], game["player2"])

    send_secrets(game_id)

if __name__ == "__main__":
    socketio.run(app)