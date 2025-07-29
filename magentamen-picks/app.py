import os
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from flask import request
import json
PICKS_FILE = 'picks.json'
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)

ODDS_API_KEY = os.getenv('ODDS_API_KEY')
ODDS_API_URL = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/'

NFL_2025_WEEK1_START = datetime(2025, 9, 4)  # Thursday, Sep 4, 2025
NFL_WEEKS = 18

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///picks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    home_team = db.Column(db.String(64), nullable=False)
    away_team = db.Column(db.String(64), nullable=False)
    commence_time = db.Column(db.String(32), nullable=False)

class Pick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    value = db.Column(db.String(128), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=True)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    outcome = db.Column(db.String(16), nullable=False)  # win/loss/tie
    pick_id = db.Column(db.Integer, db.ForeignKey('pick.id'), nullable=True)

# Create tables if not exist
with app.app_context():
    db.create_all()

# Utility to load picks
def load_picks():
    if not os.path.exists(PICKS_FILE):
        return {}
    with open(PICKS_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# Utility to save picks
def save_picks(picks):
    with open(PICKS_FILE, 'w') as f:
        json.dump(picks, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/games')
def get_games():
    # Get week from query params, default to current week
    week_param = request.args.get('week', type=int)
    today = datetime.utcnow()
    if week_param is None:
        # Calculate current week based on today
        days_since_week1 = (today - NFL_2025_WEEK1_START).days
        week = max(1, min(NFL_WEEKS, days_since_week1 // 7 + 1))
    else:
        week = max(1, min(NFL_WEEKS, week_param))
    # Calculate start and end of the week
    week_start = NFL_2025_WEEK1_START + timedelta(weeks=week-1)
    week_end = week_start + timedelta(days=7)
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'us',
        'markets': 'h2h,spreads,totals',
        'oddsFormat': 'american',
        'dateFormat': 'iso',
        'commenceTimeFrom': week_start.strftime('%Y-%m-%dT00:00:00Z'),
        'commenceTimeTo': week_end.strftime('%Y-%m-%dT00:00:00Z'),
    }
    print(f"Requested week: {week}")
    print(f"Date range: {week_start.strftime('%Y-%m-%dT00:00:00Z')} to {week_end.strftime('%Y-%m-%dT00:00:00Z')}")
    response = requests.get(ODDS_API_URL, params=params)
    print(f"Odds API status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Number of games returned: {len(data)}")
        return jsonify(data)
    else:
        print(f"Error response: {response.text}")
        return jsonify({'error': 'Failed to fetch games', 'status_code': response.status_code}), 500

@app.route('/api/picks', methods=['GET'])
def get_picks():
    week = request.args.get('week', type=int)
    season = 2025  # hardcoded for now
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    picks = Pick.query.filter_by(week=week, season=season).all()
    players = {p.name: p.id for p in Player.query.all()}
    # Group picks by player and category
    result = {}
    for pick in picks:
        player = Player.query.get(pick.player_id)
        if not player:
            continue
        if player.name not in result:
            result[player.name] = {}
        result[player.name][pick.category] = pick.value
    return jsonify(result)

@app.route('/api/picks', methods=['POST'])
def save_pick():
    data = request.get_json()
    week = int(data.get('week').split('-')[1]) if '-' in str(data.get('week')) else int(data.get('week'))
    season = 2025  # hardcoded for now
    player_name = data.get('player')
    category = data.get('category')
    value = data.get('value')
    if not all([week, player_name, category, value]):
        return jsonify({'error': 'Missing data'}), 400
    # Get or create player
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        player = Player(name=player_name)
        db.session.add(player)
        db.session.commit()
    # Check if pick exists
    pick = Pick.query.filter_by(week=week, season=season, player_id=player.id, category=category).first()
    if not pick:
        pick = Pick(week=week, season=season, player_id=player.id, category=category, value=value)
        db.session.add(pick)
    else:
        pick.value = value
    db.session.commit()
    return jsonify({'success': True})

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/api/leaderboard')
def leaderboard_api():
    # Load picks and results
    try:
        with open('picks.json', 'r') as f:
            picks = json.load(f)
    except Exception:
        picks = {}
    try:
        with open('results.json', 'r') as f:
            results = json.load(f)
    except Exception:
        results = {}
    # Scoring
    score_map = {'win': 3, 'tie': 1, 'loss': 0}
    all_weeks = sorted(results.keys(), key=lambda w: int(w.split('-')[1]))
    player_stats = {}
    for week in all_weeks:
        week_results = results.get(week, {})
        for player, cats in week_results.items():
            if player not in player_stats:
                player_stats[player] = {
                    'total_points': 0,
                    'wins': 0,
                    'losses': 0,
                    'ties': 0,
                    'weekly': []  # list of dicts: {week, points, wins, losses, ties}
                }
            week_points = 0
            week_wins = 0
            week_losses = 0
            week_ties = 0
            for cat, outcome in cats.items():
                if outcome in score_map:
                    week_points += score_map[outcome]
                    if outcome == 'win':
                        week_wins += 1
                    elif outcome == 'loss':
                        week_losses += 1
                    elif outcome == 'tie':
                        week_ties += 1
            player_stats[player]['total_points'] += week_points
            player_stats[player]['wins'] += week_wins
            player_stats[player]['losses'] += week_losses
            player_stats[player]['ties'] += week_ties
            player_stats[player]['weekly'].append({
                'week': week,
                'points': week_points,
                'wins': week_wins,
                'losses': week_losses,
                'ties': week_ties
            })
    # Calculate advanced stats
    leaderboard = []
    for player, stats in player_stats.items():
        total_picks = stats['wins'] + stats['losses'] + stats['ties']
        win_pct = (stats['wins'] + 0.5 * stats['ties']) / total_picks if total_picks else 0
        # Last 3 and 5 weeks
        last3 = stats['weekly'][-3:] if len(stats['weekly']) >= 3 else stats['weekly']
        last5 = stats['weekly'][-5:] if len(stats['weekly']) >= 5 else stats['weekly']
        last3_points = sum(w['points'] for w in last3)
        last3_wins = sum(w['wins'] for w in last3)
        last3_losses = sum(w['losses'] for w in last3)
        last3_ties = sum(w['ties'] for w in last3)
        last5_points = sum(w['points'] for w in last5)
        last5_wins = sum(w['wins'] for w in last5)
        last5_losses = sum(w['losses'] for w in last5)
        last5_ties = sum(w['ties'] for w in last5)
        leaderboard.append({
            'player': player,
            'total_points': stats['total_points'],
            'record': f"{stats['wins']}-{stats['losses']}-{stats['ties']}",
            'win_pct': round(win_pct, 3),
            'last3_points': last3_points,
            'last3_record': f"{last3_wins}-{last3_losses}-{last3_ties}",
            'last5_points': last5_points,
            'last5_record': f"{last5_wins}-{last5_losses}-{last5_ties}"
        })
    leaderboard.sort(key=lambda x: x['total_points'], reverse=True)
    return jsonify(leaderboard)

@app.route('/api/starters')
def get_starters():
    team_abbrs = request.args.get('teams', '')
    if not team_abbrs:
        return jsonify([])
    abbr_list = [abbr.strip().upper() for abbr in team_abbrs.split(',') if abbr.strip()]
    try:
        with open('starters.json', 'r') as f:
            starters = json.load(f)
    except Exception:
        return jsonify([])
    players = []
    for abbr in abbr_list:
        for p in starters.get(abbr, []):
            players.append({"name": p["name"], "pos": p["pos"], "team": abbr})
    return jsonify(players)

if __name__ == '__main__':
    app.run(debug=True) 