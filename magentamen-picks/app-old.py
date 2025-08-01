import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import json
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)

# Configurations
ODDS_API_KEY = os.getenv('ODDS_API_KEY')
ODDS_API_URL = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/'
NFL_2025_WEEK1_START = datetime(2025, 9, 4)
NFL_WEEKS = 18

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///picks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
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
    outcome = db.Column(db.String(16), nullable=False)
    pick_id = db.Column(db.Integer, db.ForeignKey('pick.id'), nullable=True)

with app.app_context():
    db.create_all()

# Utility functions
def load_picks():
    if not os.path.exists('picks.json'):
        return {}
    with open('picks.json', 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_picks(picks):
    with open('picks.json', 'w') as f:
        json.dump(picks, f, indent=2)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/schedule')
def schedule():
    return render_template('schedule.html')

@app.route('/rules')
def rules():
    return render_template('rules.html')

# API Endpoints
@app.route('/api/games')
def get_games():
    week_param = request.args.get('week', type=int)
    today = datetime.utcnow()
    if week_param is None:
        days_since_week1 = (today - NFL_2025_WEEK1_START).days
        week = max(1, min(NFL_WEEKS, days_since_week1 // 7 + 1))
    else:
        week = max(1, min(NFL_WEEKS, week_param))
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
    response = requests.get(ODDS_API_URL, params=params)
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({'error': 'Failed to fetch games'}), 500

@app.route('/api/picks', methods=['GET'])
def get_picks():
    week = request.args.get('week', type=int)
    season = 2025
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    picks = Pick.query.filter_by(week=week, season=season).all()
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
    season = 2025
    player_name = data.get('player')
    category = data.get('category')
    value = data.get('value')
    if not all([week, player_name, category, value]):
        return jsonify({'error': 'Missing data'}), 400
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        player = Player(name=player_name)
        db.session.add(player)
        db.session.commit()
    pick = Pick.query.filter_by(week=week, season=season, player_id=player.id, category=category).first()
    if not pick:
        pick = Pick(week=week, season=season, player_id=player.id, category=category, value=value)
        db.session.add(pick)
    else:
        pick.value = value
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/leaderboard')
def leaderboard_api():
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
    score_map = {'win': 3, 'tie': 1, 'loss': 0}
    all_weeks = sorted(results.keys(), key=lambda w: int(w.split('-')[1]))
    player_stats = {}
    for week in all_weeks:
        week_results = results.get(week, {})
        for player, cats in week_results.items():
            stats = player_stats.setdefault(player, {
                'total_points': 0, 'wins': 0, 'losses': 0, 'ties': 0, 'weekly': []
            })
            week_points = week_wins = week_losses = week_ties = 0
            for outcome in cats.values():
                if outcome in score_map:
                    week_points += score_map[outcome]
                    week_wins += outcome == 'win'
                    week_losses += outcome == 'loss'
                    week_ties += outcome == 'tie'
            stats['total_points'] += week_points
            stats['wins'] += week_wins
            stats['losses'] += week_losses
            stats['ties'] += week_ties
            stats['weekly'].append({
                'week': week, 'points': week_points, 'wins': week_wins,
                'losses': week_losses, 'ties': week_ties
            })
    leaderboard = []
    for player, stats in player_stats.items():
        total_picks = stats['wins'] + stats['losses'] + stats['ties']
        win_pct = (stats['wins'] + 0.5 * stats['ties']) / total_picks if total_picks else 0
        last3 = stats['weekly'][-3:] if len(stats['weekly']) >= 3 else stats['weekly']
        last5 = stats['weekly'][-5:] if len(stats['weekly']) >= 5 else stats['weekly']
        leaderboard.append({
            'player': player,
            'total_points': stats['total_points'],
            'record': f"{stats['wins']}-{stats['losses']}-{stats['ties']}",
            'win_pct': round(win_pct, 3),
            'last3_points': sum(w['points'] for w in last3),
            'last3_record': f"{sum(w['wins'] for w in last3)}-{sum(w['losses'] for w in last3)}-{sum(w['ties'] for w in last3)}",
            'last5_points': sum(w['points'] for w in last5),
            'last5_record': f"{sum(w['wins'] for w in last5)}-{sum(w['losses'] for w in last5)}-{sum(w['ties'] for w in last5)}"
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

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
