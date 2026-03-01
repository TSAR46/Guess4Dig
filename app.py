from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room
import random
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app, async_mode='eventlet')

waiting_player = None
games = {}

def generate_secret():
    digits = []
    while len(digits) < 4:
        num = str(random.randint(0, 9))
        if num not in digits:
            digits.append(num)
    return ''.join(digits)

def count_matches(secret, guess):
    secret_list = list(secret)
    count = 0
    for digit in guess:
        if digit in secret_list:
            count += 1
            secret_list.remove(digit)
    return count

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    global waiting_player

    print("Connected:", request.sid)

    if waiting_player is None:
        waiting_player = request.sid
        socketio.emit("waiting", to=request.sid)
    else:
        game_id = waiting_player + "#" + request.sid
        secret = generate_secret()

        games[game_id] = {
            "secret": secret,
            "players": [waiting_player, request.sid],
            "current_turn": waiting_player,
            "active": True
        }

        socketio.server.enter_room(waiting_player, game_id)
        join_room(game_id)

        socketio.emit("startGame", {
            "player1": waiting_player,
            "player2": request.sid,
            "currentTurn": waiting_player
        }, room=game_id)

        print("Game started:", game_id, "Secret:", secret)

        waiting_player = None

@socketio.on('makeGuess')
def handle_guess(data):
    guess = data.get("guess")

    if not guess or not guess.isdigit() or len(guess) != 4:
        return

    game_id = None
    for g in games:
        if request.sid in games[g]["players"]:
            game_id = g
            break

    if not game_id:
        return

    game = games[game_id]

    if not game["active"]:
        return

    # Check turn
    if game["current_turn"] != request.sid:
        return

    correct_count = count_matches(game["secret"], guess)

    socketio.emit("guessResult", {
        "player": request.sid,
        "guess": guess,
        "correctCount": correct_count
    }, room=game_id)

    # Win condition
    if correct_count == 4:
        game["active"] = False
        socketio.emit("gameOver", {
            "winner": request.sid
        }, room=game_id)
        return

    # Switch turn
    players = game["players"]
    game["current_turn"] = players[0] if request.sid == players[1] else players[1]

    socketio.emit("turnChanged", {
        "currentTurn": game["current_turn"]
    }, room=game_id)

@socketio.on('disconnect')
def handle_disconnect():
    global waiting_player
    print("Disconnected:", request.sid)
    if waiting_player == request.sid:
        waiting_player = None

import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)