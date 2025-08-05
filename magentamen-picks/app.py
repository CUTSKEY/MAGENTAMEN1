import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import json
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
    picks = db.relationship('Pick', backref='player', lazy=True)
    results = db.relationship('Result', backref='player', lazy=True)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    home_team = db.Column(db.String(64), nullable=False)
    away_team = db.Column(db.String(64), nullable=False)
    commence_time = db.Column(db.String(32), nullable=False)
    odds_data = db.Column(db.Text, nullable=True)  # Store full odds as JSON
    picks = db.relationship('Pick', backref='game', lazy=True)

class Pick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    value = db.Column(db.String(128), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=True)
    
    # Ensure unique pick per player/week/category
    __table_args__ = (db.UniqueConstraint('week', 'season', 'player_id', 'category'),)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    outcome = db.Column(db.String(16), nullable=False)  # win/loss/tie
    pick_id = db.Column(db.Integer, db.ForeignKey('pick.id'), nullable=True)

# Add this new model after the existing models
class NFLPlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    position = db.Column(db.String(8), nullable=False)  # QB, RB, WR, TE, etc.
    team = db.Column(db.String(8), nullable=False)      # Team abbreviation
    active = db.Column(db.Boolean, default=True)
    
    # Ensure unique player per team
    __table_args__ = (db.UniqueConstraint('name', 'team'),)

# Add this new model after the existing models
class WeekLock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    locked_at = db.Column(db.DateTime, default=datetime.utcnow)
    locked_by = db.Column(db.String(64), nullable=False)
    
    # Ensure only one lock per week/season
    __table_args__ = (db.UniqueConstraint('week', 'season'),)

# Create tables if not exist
with app.app_context():
    db.create_all()
    
    # Add sample players if they don't exist
    sample_players = ["Jaren", "JB", "Rory", "Zach"]
    for player_name in sample_players:
        if not Player.query.filter_by(name=player_name).first():
            player = Player(name=player_name)
            db.session.add(player)
    
    # Add sample NFL players if they don't exist
    sample_nfl_players = [
        # Quarterbacks
        {"name": "Patrick Mahomes", "position": "QB", "team": "KC"},
        {"name": "Josh Allen", "position": "QB", "team": "BUF"},
        {"name": "Lamar Jackson", "position": "QB", "team": "BAL"},
        {"name": "Jalen Hurts", "position": "QB", "team": "PHI"},
        {"name": "Dak Prescott", "position": "QB", "team": "DAL"},
        {"name": "Justin Herbert", "position": "QB", "team": "LAC"},
        {"name": "Joe Burrow", "position": "QB", "team": "CIN"},
        {"name": "Aaron Rodgers", "position": "QB", "team": "NYJ"},
        
        # Running Backs
        {"name": "Christian McCaffrey", "position": "RB", "team": "SF"},
        {"name": "Saquon Barkley", "position": "RB", "team": "PHI"},
        {"name": "Derrick Henry", "position": "RB", "team": "BAL"},
        {"name": "Nick Chubb", "position": "RB", "team": "CLE"},
        {"name": "Josh Jacobs", "position": "RB", "team": "GB"},
        {"name": "Bijan Robinson", "position": "RB", "team": "ATL"},
        {"name": "Jahmyr Gibbs", "position": "RB", "team": "DET"},
        {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
        
        # Wide Receivers
        {"name": "Tyreek Hill", "position": "WR", "team": "MIA"},
        {"name": "CeeDee Lamb", "position": "WR", "team": "DAL"},
        {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
        {"name": "Amon-Ra St. Brown", "position": "WR", "team": "DET"},
        {"name": "Stefon Diggs", "position": "WR", "team": "HOU"},
        {"name": "AJ Brown", "position": "WR", "team": "PHI"},
        {"name": "Garrett Wilson", "position": "WR", "team": "NYJ"},
        {"name": "Chris Olave", "position": "WR", "team": "NO"},
        
        # Tight Ends
        {"name": "Travis Kelce", "position": "TE", "team": "KC"},
        {"name": "Sam LaPorta", "position": "TE", "team": "DET"},
        {"name": "Mark Andrews", "position": "TE", "team": "BAL"},
        {"name": "T.J. Hockenson", "position": "TE", "team": "MIN"},
        {"name": "George Kittle", "position": "TE", "team": "SF"},
        {"name": "Dallas Goedert", "position": "TE", "team": "PHI"},
        {"name": "Jake Ferguson", "position": "TE", "team": "DAL"},
        {"name": "Dalton Kincaid", "position": "TE", "team": "BUF"},
    ]
    
    for player_data in sample_nfl_players:
        if not NFLPlayer.query.filter_by(name=player_data["name"], team=player_data["team"]).first():
            nfl_player = NFLPlayer(**player_data)
            db.session.add(nfl_player)
    
    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/games')
def get_games():
    week_param = request.args.get('week', type=int)
    season = 2025
    today = datetime.utcnow()
    
    print("=== API GAMES DEBUG ===")
    print(f"Week param: {week_param}")
    print(f"Season: {season}")
    print(f"Today: {today}")
    print(f"NFL_2025_WEEK1_START: {NFL_2025_WEEK1_START}")
    print(f"ODDS_API_KEY exists: {bool(ODDS_API_KEY)}")
    
    if week_param is None:
        days_since_week1 = (today - NFL_2025_WEEK1_START).days
        week = max(1, min(NFL_WEEKS, days_since_week1 // 7 + 1))
        print(f"Calculated week: {week} (days since week 1: {days_since_week1})")
    else:
        week = max(1, min(NFL_WEEKS, week_param))
        print(f"Using provided week: {week}")
    
    # Check if games already exist in database for this week
    existing_games = Game.query.filter_by(week=week, season=season).all()
    print(f"Existing games in database: {len(existing_games)}")
    
    if existing_games:
        print("Returning existing games from database")
        games_data = []
        for game in existing_games:
            game_dict = {
                'id': game.id,
                'home_team': game.home_team,
                'away_team': game.away_team,
                'commence_time': game.commence_time
            }
            if game.odds_data:
                try:
                    odds = json.loads(game.odds_data)
                    game_dict.update(odds)
                except:
                    pass
            games_data.append(game_dict)
        print(f"Returning {len(games_data)} games from database")
        return jsonify(games_data)
    
    print("No existing games found, fetching from API...")
    
    # Fetch from API and store in database
    week_start = NFL_2025_WEEK1_START + timedelta(weeks=week-1)
    week_end = week_start + timedelta(days=7)
    
    print(f"Week start: {week_start}")
    print(f"Week end: {week_end}")
    
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'us',
        'markets': 'h2h,spreads,totals',
        'oddsFormat': 'american',
        'dateFormat': 'iso',
        'commenceTimeFrom': week_start.strftime('%Y-%m-%dT00:00:00Z'),
        'commenceTimeTo': week_end.strftime('%Y-%m-%dT00:00:00Z'),
    }
    
    print(f"API URL: {ODDS_API_URL}")
    print(f"API Params: {params}")
    
    try:
        response = requests.get(ODDS_API_URL, params=params)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"API Response type: {type(data)}")
            print(f"API Response length: {len(data) if isinstance(data, list) else 'Not a list'}")
            print(f"API Response preview: {str(data)[:500]}...")
            
            if not data:
                print("API returned empty data")
                return jsonify([])
            
            if not isinstance(data, list):
                print(f"API returned non-list data: {type(data)}")
                return jsonify([])
            
            # Store games in database
            stored_count = 0
            for game_data in data:
                try:
                    odds_only = {k: v for k, v in game_data.items() 
                                if k not in ['home_team', 'away_team', 'commence_time']}
                    
                    game = Game(
                        week=week,
                        season=season,
                        home_team=game_data['home_team'],
                        away_team=game_data['away_team'],
                        commence_time=game_data['commence_time'],
                        odds_data=json.dumps(odds_only)
                    )
                    db.session.add(game)
                    stored_count += 1
                except Exception as e:
                    print(f"Error processing game data: {e}")
                    print(f"Game data: {game_data}")
            
            db.session.commit()
            print(f"Successfully stored {stored_count} games in database")
            return jsonify(data)
        else:
            print(f"API Error: {response.status_code}")
            print(f"Error response: {response.text}")
            return jsonify({'error': 'Failed to fetch games', 'status_code': response.status_code}), 500
            
    except Exception as e:
        print(f"Exception during API call: {e}")
        return jsonify({'error': f'Exception during API call: {str(e)}'}), 500

@app.route('/api/picks', methods=['GET'])
def get_picks():
    week = request.args.get('week', type=int)
    season = 2025
    
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    
    picks = Pick.query.filter_by(week=week, season=season).all()
    
    # Group picks by player and category
    result = {}
    for pick in picks:
        if pick.player.name not in result:
            result[pick.player.name] = {}
        result[pick.player.name][pick.category] = pick.value
    
    return jsonify(result)

@app.route('/api/picks', methods=['POST'])
def save_pick():
    data = request.get_json()
    
    # Handle week format (could be '2025-1' or just '1')
    week_param = data.get('week')
    if '-' in str(week_param):
        week = int(week_param.split('-')[1])
    else:
        week = int(week_param)
    
    season = 2025
    player_name = data.get('player')
    category = data.get('category')
    value = data.get('value')
    
    if not all([week, player_name, category, value]):
        return jsonify({'error': 'Missing required data'}), 400
    
    # Get or create player
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        player = Player(name=player_name)
        db.session.add(player)
        db.session.commit()
    
    # Check if this value is already taken by another player for this category/week
    existing_pick = Pick.query.filter_by(
        week=week, 
        season=season, 
        category=category, 
        value=value
    ).filter(Pick.player_id != player.id).first()
    
    if existing_pick:
        return jsonify({'error': 'This pick is already taken by another player'}), 400
    
    # Get or create pick for this player/week/category
    pick = Pick.query.filter_by(
        week=week, 
        season=season, 
        player_id=player.id, 
        category=category
    ).first()
    
    if not pick:
        pick = Pick(
            week=week, 
            season=season, 
            player_id=player.id, 
            category=category, 
            value=value
        )
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
    results = Result.query.all()
    
    # Scoring system
    score_map = {'win': 3, 'tie': 1, 'loss': 0}
    
    # Group results by player and week
    player_stats = {}
    week_results = {}
    
    for result in results:
        player_name = result.player.name
        week_key = f"{result.season}-{result.week}"
        
        if player_name not in player_stats:
            player_stats[player_name] = {
                'total_points': 0,
                'wins': 0,
                'losses': 0,
                'ties': 0,
                'weekly': []
            }
        
        if week_key not in week_results:
            week_results[week_key] = {}
        
        if player_name not in week_results[week_key]:
            week_results[week_key][player_name] = {
                'points': 0,
                'wins': 0,
                'losses': 0,
                'ties': 0
            }
        
        # Add to totals
        points = score_map.get(result.outcome, 0)
        player_stats[player_name]['total_points'] += points
        week_results[week_key][player_name]['points'] += points
        
        if result.outcome == 'win':
            player_stats[player_name]['wins'] += 1
            week_results[week_key][player_name]['wins'] += 1
        elif result.outcome == 'loss':
            player_stats[player_name]['losses'] += 1
            week_results[week_key][player_name]['losses'] += 1
        elif result.outcome == 'tie':
            player_stats[player_name]['ties'] += 1
            week_results[week_key][player_name]['ties'] += 1
    
    # Calculate weekly stats for each player
    for player_name in player_stats:
        weekly_stats = []
        for week_key in sorted(week_results.keys(), key=lambda x: int(x.split('-')[1])):
            if player_name in week_results[week_key]:
                weekly_stats.append({
                    'week': week_key,
                    **week_results[week_key][player_name]
                })
        player_stats[player_name]['weekly'] = weekly_stats
    
    # Build leaderboard
    leaderboard = []
    for player_name, stats in player_stats.items():
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
            'player': player_name,
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
    
    # Get players from database for the requested teams
    players = NFLPlayer.query.filter(
        NFLPlayer.team.in_(abbr_list),
        NFLPlayer.active == True
    ).all()
    
    return jsonify([
        {
            "name": player.name,
            "pos": player.position,
            "team": player.team
        }
        for player in players
    ])

@app.route('/results')
def results_page():
    return render_template('results.html')

@app.route('/api/results', methods=['GET'])
def get_results():
    week = request.args.get('week', type=int)
    season = 2025
    
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    
    # Get all picks for the week
    picks = Pick.query.filter_by(week=week, season=season).all()
    results = Result.query.filter_by(week=week, season=season).all()
    
    # Create results lookup
    results_lookup = {}
    for result in results:
        key = f"{result.player.name}_{result.category}"
        results_lookup[key] = result.outcome
    
    # Build response
    data = {}
    for pick in picks:
        if pick.player.name not in data:
            data[pick.player.name] = {}
        
        key = f"{pick.player.name}_{pick.category}"
        outcome = results_lookup.get(key, 'pending')
        
        data[pick.player.name][pick.category] = {
            'pick': pick.value,
            'outcome': outcome
        }
    
    return jsonify(data)

@app.route('/api/results', methods=['POST'])
def save_result():
    data = request.get_json()
    
    week = data.get('week')
    season = 2025
    player_name = data.get('player')
    category = data.get('category')
    outcome = data.get('outcome')  # 'win', 'loss', or 'tie'
    
    if not all([week, player_name, category, outcome]):
        return jsonify({'error': 'Missing required data'}), 400
    
    if outcome not in ['win', 'loss', 'tie']:
        return jsonify({'error': 'Invalid outcome'}), 400
    
    # Get player
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        return jsonify({'error': 'Player not found'}), 400
    
    # Get pick
    pick = Pick.query.filter_by(
        week=week,
        season=season,
        player_id=player.id,
        category=category
    ).first()
    
    if not pick:
        return jsonify({'error': 'Pick not found'}), 400
    
    # Get or create result
    result = Result.query.filter_by(
        week=week,
        season=season,
        player_id=player.id,
        category=category
    ).first()
    
    if not result:
        result = Result(
            week=week,
            season=season,
            player_id=player.id,
            category=category,
            outcome=outcome,
            pick_id=pick.id
        )
        db.session.add(result)
    else:
        result.outcome = outcome
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/week/lock', methods=['POST'])
def lock_week():
    data = request.get_json()
    week = data.get('week')
    season = 2025
    locked_by = data.get('locked_by', 'Admin')
    
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    
    # Check if week is already locked
    existing_lock = WeekLock.query.filter_by(week=week, season=season).first()
    if existing_lock:
        return jsonify({'error': 'Week is already locked'}), 400
    
    # Create lock
    week_lock = WeekLock(week=week, season=season, locked_by=locked_by)
    db.session.add(week_lock)
    db.session.commit()
    
    return jsonify({'success': True, 'locked_at': week_lock.locked_at.isoformat()})

@app.route('/api/week/lock/<int:week>')
def get_week_lock_status(week):
    season = 2025
    lock = WeekLock.query.filter_by(week=week, season=season).first()
    
    if lock:
        return jsonify({
            'locked': True,
            'locked_at': lock.locked_at.isoformat(),
            'locked_by': lock.locked_by
        })
    else:
        return jsonify({'locked': False})

@app.route('/api/results/calculate', methods=['POST'])
def calculate_results():
    data = request.get_json()
    week = data.get('week')
    season = 2025
    
    if not week:
        return jsonify({'error': 'Missing week parameter'}), 400
    
    # Get all picks for the week
    picks = Pick.query.filter_by(week=week, season=season).all()
    
    # Get games for the week
    games = Game.query.filter_by(week=week, season=season).all()
    
    # Fetch game results from external API
    game_results = fetch_game_results(week, season)
    
    # Calculate outcomes for each pick
    results_updated = 0
    for pick in picks:
        outcome = calculate_pick_outcome(pick, game_results, games)
        if outcome:
            # Update or create result
            result = Result.query.filter_by(
                week=week,
                season=season,
                player_id=pick.player_id,
                category=pick.category
            ).first()
            
            if not result:
                result = Result(
                    week=week,
                    season=season,
                    player_id=pick.player_id,
                    category=pick.category,
                    outcome=outcome,
                    pick_id=pick.id
                )
                db.session.add(result)
            else:
                result.outcome = outcome
            
            results_updated += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'results_updated': results_updated,
        'message': f'Updated {results_updated} results for Week {week}'
    })

def fetch_game_results(week, season):
    """
    Fetch game results from external API.
    This is a placeholder that would integrate with a real sports API.
    """
    # For now, return mock data structure
    # In production, this would call an API like:
    # - ESPN API
    # - NFL API
    # - SportsData.io
    # - The Odds API (for live scores)
    
    mock_results = {
        # Example structure for real API integration
        "Kansas City Chiefs @ Baltimore Ravens": {
            "home_score": 24,
            "away_score": 21,
            "final": True,
            "spread": -3.5,  # Baltimore was favored by 3.5
            "total": 45.5,
            "moneyline_winner": "Baltimore Ravens",
            "spread_winner": "Kansas City Chiefs",  # KC covered the spread
            "total_result": "under"  # 45 total < 45.5
        }
    }
    
    return mock_results

def calculate_pick_outcome(pick, game_results, games):
    """
    Calculate the outcome of a pick based on game results.
    """
    if not game_results:
        return None
    
    # Find the game this pick relates to
    game = None
    for g in games:
        game_key = f"{g.away_team} @ {g.home_team}"
        if game_key in game_results:
            game = game_results[game_key]
            break
    
    if not game or not game.get('final'):
        return None
    
    pick_value = pick.value
    
    if pick.category == "Moneyline":
        # Check if the picked team won
        if pick_value == game.get('moneyline_winner'):
            return "win"
        else:
            return "loss"
    
    elif pick.category == "Favorite":
        # Check if the favorite covered the spread
        if game.get('spread_winner') == pick_value:
            return "win"
        else:
            return "loss"
    
    elif pick.category == "Underdog":
        # Check if the underdog covered the spread
        if game.get('spread_winner') == pick_value:
            return "win"
        else:
            return "loss"
    
    elif pick.category == "Over":
        # Check if total points exceeded the over/under line
        if game.get('total_result') == "over":
            return "win"
        else:
            return "loss"
    
    elif pick.category == "Under":
        # Check if total points were under the over/under line
        if game.get('total_result') == "under":
            return "win"
        else:
            return "loss"
    
    elif pick.category == "Touchdown Scorer":
        # This would require player-specific touchdown data
        # For now, return None (manual entry required)
        return None
    
    return None

@app.route('/api/game-results/<int:week>')
def get_game_results(week):
    """
    API endpoint to fetch game results for a specific week.
    This would integrate with a real sports API.
    """
    season = 2025
    
    # Get games for the week
    games = Game.query.filter_by(week=week, season=season).all()
    
    # Fetch results from external API
    results = fetch_game_results(week, season)
    
    # Format response
    formatted_results = []
    for game in games:
        game_key = f"{game.away_team} @ {game.home_team}"
        game_result = results.get(game_key, {})
        
        formatted_results.append({
            'game': game_key,
            'home_team': game.home_team,
            'away_team': game.away_team,
            'home_score': game_result.get('home_score'),
            'away_score': game_result.get('away_score'),
            'final': game_result.get('final', False),
            'spread': game_result.get('spread'),
            'total': game_result.get('total'),
            'moneyline_winner': game_result.get('moneyline_winner'),
            'spread_winner': game_result.get('spread_winner'),
            'total_result': game_result.get('total_result')
        })
    
    return jsonify(formatted_results)

if __name__ == '__main__':
    app.run(debug=True)
    