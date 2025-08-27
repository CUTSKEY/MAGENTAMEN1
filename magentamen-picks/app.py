import os
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta, timezone
import json
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)

ODDS_API_KEY = os.getenv('ODD_API_KEY')
ODDS_API_URL = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/'
SCORES_API_URL = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/scores/'

NFL_2025_WEEK1_START = datetime(2025, 9, 4, tzinfo=timezone.utc)  # Thursday, Sep 4, 2025
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

# Add this new model to store game results
class GameResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    home_team = db.Column(db.String(64), nullable=False)
    away_team = db.Column(db.String(64), nullable=False)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    final = db.Column(db.Boolean, default=False)
    spread = db.Column(db.Float, nullable=True)
    total = db.Column(db.Float, nullable=True)
    moneyline_winner = db.Column(db.String(64), nullable=True)
    spread_winner = db.Column(db.String(64), nullable=True)
    total_result = db.Column(db.String(16), nullable=True)  # 'over', 'under', or None for push
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ensure only one result per game
    __table_args__ = (db.UniqueConstraint('week', 'season', 'home_team', 'away_team'),)

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

@app.route('/api/games/refresh', methods=['POST'])
def refresh_games():
    """Force refresh games and odds data from API"""
    week = request.json.get('week') if request.is_json else request.form.get('week')
    if not week:
        return jsonify({'error': 'Week parameter required'}), 400
    
    if not ODDS_API_KEY:
        return jsonify({'error': 'No API key configured'}), 400
    
    try:
        # Fetch fresh data from API
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'dateFormat': 'iso',
            'oddsFormat': 'american'
        }
        
        response = requests.get(ODDS_API_URL, params=params)
        response.raise_for_status()
        
        games_data = response.json()
        
        # Process games and determine their week
        week_games_map = {}
        
        for game in games_data:
            try:
                # Parse game date
                game_date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                
                # Calculate which NFL week this game belongs to
                days_since_week1 = (game_date - NFL_2025_WEEK1_START).days
                game_week = max(1, min(18, (days_since_week1 // 7) + 1))
                
                if game_week not in week_games_map:
                    week_games_map[game_week] = []
                
                week_games_map[game_week].append({
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'commence_time': game['commence_time'],
                    'bookmakers': game.get('bookmakers', [])
                })
                
            except Exception as e:
                print(f"Error processing game {game}: {e}")
                continue
        
        # Update games for the requested week
        updated_count = 0
        print(f"Requested week: {week}")
        print(f"Available weeks in API response: {list(week_games_map.keys())}")
        if int(week) in week_games_map:
            for game_data in week_games_map[int(week)]:
                # Find existing game
                existing_game = Game.query.filter_by(
                    week=int(week),
                    season=2025,
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team']
                ).first()
                
                if existing_game:
                    # Update existing game with fresh odds
                    if game_data['bookmakers']:
                        existing_game.odds_data = json.dumps(game_data['bookmakers'])
                        updated_count += 1
                else:
                    # Create new game if it doesn't exist
                    odds_data = json.dumps(game_data['bookmakers']) if game_data['bookmakers'] else None
                    db_game = Game(
                        week=int(week),
                        season=2025,
                        home_team=game_data['home_team'],
                        away_team=game_data['away_team'],
                        commence_time=game_data['commence_time'],
                        odds_data=odds_data
                    )
                    db.session.add(db_game)
                    updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Refreshed odds for {updated_count} games in Week {week}',
            'updated_count': updated_count
        })
        
    except requests.RequestException as e:
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error refreshing games: {str(e)}'}), 500

@app.route('/api/games')
def get_games():
    week = request.args.get('week', type=int)
    if not week:
        return jsonify([])
    
    # Check if we have games for this week in the database
    games = Game.query.filter_by(week=week, season=2025).all()
    
    if games:
        # Return games from database (with or without odds)
        return jsonify([{
            'home_team': game.home_team,
            'away_team': game.away_team,
            'commence_time': game.commence_time,
            'bookmakers': json.loads(game.odds_data) if game.odds_data else []
        } for game in games])
    
    # If no games in database, fetch from API
    if not ODDS_API_KEY:
        return jsonify([])
    
    try:
        # Fetch from The Odds API - don't filter by date initially
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'dateFormat': 'iso',
            'oddsFormat': 'american'
        }
        
        response = requests.get(ODDS_API_URL, params=params)
        response.raise_for_status()
        
        games_data = response.json()
        
        # Process ALL games from API and determine their week
        week_games_map = {}  # week -> [games]
        
        for game in games_data:
            try:
                # Parse game date
                game_date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                
                # Calculate which NFL week this game belongs to
                days_since_week1 = (game_date - NFL_2025_WEEK1_START).days
                game_week = max(1, min(18, (days_since_week1 // 7) + 1))
                
                if game_week not in week_games_map:
                    week_games_map[game_week] = []
                
                week_games_map[game_week].append({
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'commence_time': game['commence_time'],
                    'bookmakers': game.get('bookmakers', [])
                })
                
            except Exception as e:
                print(f"Error processing game {game}: {e}")
                continue
        
        # Store ALL weeks of games in database
        for game_week, games_list in week_games_map.items():
            for game_data in games_list:
                # Check if this exact game already exists
                existing_game = Game.query.filter_by(
                    week=game_week,
                    season=2025,
                    home_team=game_data['home_team'],
                    away_team=game_data['away_team']
                ).first()
                
                if not existing_game:
                    # Store new game (with or without odds)
                    odds_data = None
                    if game_data['bookmakers']:
                        odds_data = json.dumps(game_data['bookmakers'])
                    
                    db_game = Game(
                        week=game_week,
                        season=2025,
                        home_team=game_data['home_team'],
                        away_team=game_data['away_team'],
                        commence_time=game_data['commence_time'],
                        odds_data=odds_data
                    )
                    db.session.add(db_game)
                else:
                    # Update existing game with new odds if available
                    if game_data['bookmakers'] and not existing_game.odds_data:
                        existing_game.odds_data = json.dumps(game_data['bookmakers'])
        
        # Commit all changes
        db.session.commit()
        print(f"Stored games for {len(week_games_map)} weeks")
        
        # Return games for the requested week
        if week in week_games_map:
            return jsonify(week_games_map[week])
        else:
            # Check database again in case we just stored them
            games = Game.query.filter_by(week=week, season=2025).all()
            return jsonify([{
                'home_team': game.home_team,
                'away_team': game.away_team,
                'commence_time': game.commence_time,
                'bookmakers': json.loads(game.odds_data) if game.odds_data else []
            } for game in games])
        
    except requests.RequestException as e:
        print(f"Error fetching games from API: {e}")
        return jsonify([])
    except Exception as e:
        db.session.rollback()
        print(f"Error processing games: {e}")
        return jsonify([])
    
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


@app.route('/api/week/unlock', methods=['POST'])
def unlock_week():
    data = request.get_json()
    week = data.get('week')
    
    if not week:
        return jsonify({'error': 'Week is required'}), 400
    
    try:
        # Find and delete the existing lock
        existing_lock = WeekLock.query.filter_by(week=week, season=2025).first()
        if not existing_lock:
            return jsonify({'error': 'Week is not currently locked'}), 400
        
        db.session.delete(existing_lock)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Week {week} unlocked successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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
    Fetch live game results from The Odds API scores endpoint
    """
    if not ODDS_API_KEY:
        print("No API key available for fetching game results")
        return {}
    
    try:
        # Calculate date range for the week
        week_start = NFL_2025_WEEK1_START + timedelta(days=(week - 1) * 7)
        week_end = week_start + timedelta(days=7)
        
        # Format dates for API
        start_date = week_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date = week_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Fetch scores from The Odds API
        scores_url = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/scores/'
        params = {
            'apiKey': ODDS_API_KEY,
            'dateFormat': 'iso',
            'commenceTimeFrom': start_date,
            'commenceTimeTo': end_date
        }
        
        response = requests.get(scores_url, params=params)
        response.raise_for_status()
        
        scores_data = response.json()
        
        # Process the scores data
        game_results = {}
        for game in scores_data:
            if game.get('completed') and game.get('scores'):
                home_team = game['home_team']
                away_team = game['away_team']
                game_key = f"{away_team} @ {home_team}"
                
                # Extract scores
                home_score = None
                away_score = None
                for score in game['scores']:
                    if score['name'] == home_team:
                        home_score = score['score']
                    elif score['name'] == away_team:
                        away_score = score['score']
                
                if home_score is not None and away_score is not None:
                    # Determine moneyline winner
                    if home_score > away_score:
                        moneyline_winner = home_team
                    elif away_score > home_score:
                        moneyline_winner = away_team
                    else:
                        moneyline_winner = None  # Tie
                    
                    # Get spread and total from stored odds data
                    spread_winner = None
                    total_result = None
                    spread = None
                    total = None
                    
                    # Find the corresponding game in our database to get odds
                    db_game = Game.query.filter_by(
                        week=week,
                        season=season,
                        home_team=home_team,
                        away_team=away_team
                    ).first()
                    
                    if db_game and db_game.odds_data:
                        try:
                            odds_data = json.loads(db_game.odds_data)
                            # Find DraftKings odds
                            draftkings = None
                            for bookmaker in odds_data:
                                if bookmaker.get('key') == 'draftkings':
                                    draftkings = bookmaker
                                    break
                            
                            if draftkings and draftkings.get('markets'):
                                # Get spread data
                                spreads_market = None
                                for market in draftkings['markets']:
                                    if market.get('key') == 'spreads':
                                        spreads_market = market
                                        break
                                
                                if spreads_market and spreads_market.get('outcomes'):
                                    for outcome in spreads_market['outcomes']:
                                        if outcome['name'] == home_team:
                                            spread = outcome['point']
                                            break
                                
                                # Get total data
                                totals_market = None
                                for market in draftkings['markets']:
                                    if market.get('key') == 'totals':
                                        totals_market = market
                                        break
                                
                                if totals_market and totals_market.get('outcomes'):
                                    for outcome in totals_market['outcomes']:
                                        if outcome['name'] == 'Over':
                                            total = outcome['point']
                                            break
                                
                                # Calculate spread winner
                                if spread is not None:
                                    home_with_spread = home_score + spread
                                    if home_with_spread > away_score:
                                        spread_winner = home_team
                                    elif away_score > home_with_spread:
                                        spread_winner = away_team
                                    # else it's a push (tie)
                                
                                # Calculate total result
                                if total is not None:
                                    total_points = home_score + away_score
                                    if total_points > total:
                                        total_result = "over"
                                    elif total_points < total:
                                        total_result = "under"
                                    # else it's a push
                                        
                        except (json.JSONDecodeError, KeyError) as e:
                            print(f"Error parsing odds data for {game_key}: {e}")
                    
                    game_results[game_key] = {
                        "home_score": home_score,
                        "away_score": away_score,
                        "final": True,
                        "spread": spread,
                        "total": total,
                        "moneyline_winner": moneyline_winner,
                        "spread_winner": spread_winner,
                        "total_result": total_result
                    }
        
        return game_results
        
    except requests.RequestException as e:
        print(f"Error fetching game results from API: {e}")
        return {}
    except Exception as e:
        print(f"Error processing game results: {e}")
        return {}

def store_game_results(week, season, game_results):
    """
    Store game results in the database
    """
    stored_count = 0
    for game_key, result_data in game_results.items():
        # Parse team names from game key
        parts = game_key.split(' @ ')
        if len(parts) != 2:
            continue
        
        away_team = parts[0]
        home_team = parts[1]
        
        # Check if result already exists
        existing_result = GameResult.query.filter_by(
            week=week,
            season=season,
            home_team=home_team,
            away_team=away_team
        ).first()
        
        if existing_result:
            # Update existing result
            existing_result.home_score = result_data.get('home_score')
            existing_result.away_score = result_data.get('away_score')
            existing_result.final = result_data.get('final', False)
            existing_result.spread = result_data.get('spread')
            existing_result.total = result_data.get('total')
            existing_result.moneyline_winner = result_data.get('moneyline_winner')
            existing_result.spread_winner = result_data.get('spread_winner')
            existing_result.total_result = result_data.get('total_result')
            existing_result.last_updated = datetime.utcnow()
        else:
            # Create new result
            new_result = GameResult(
                week=week,
                season=season,
                home_team=home_team,
                away_team=away_team,
                home_score=result_data.get('home_score'),
                away_score=result_data.get('away_score'),
                final=result_data.get('final', False),
                spread=result_data.get('spread'),
                total=result_data.get('total'),
                moneyline_winner=result_data.get('moneyline_winner'),
                spread_winner=result_data.get('spread_winner'),
                total_result=result_data.get('total_result')
            )
            db.session.add(new_result)
        
        stored_count += 1
    
    try:
        db.session.commit()
        print(f"Stored {stored_count} game results for Week {week}")
        return stored_count
    except Exception as e:
        db.session.rollback()
        print(f"Error storing game results: {e}")
        return 0

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
    API endpoint to fetch game results for a specific week from database
    """
    season = 2025
    
    # Get stored game results from database
    game_results = GameResult.query.filter_by(week=week, season=season).all()
    
    # Format response
    formatted_results = []
    for result in game_results:
        formatted_results.append({
            'game': f"{result.away_team} @ {result.home_team}",
            'home_team': result.home_team,
            'away_team': result.away_team,
            'home_score': result.home_score,
            'away_score': result.away_score,
            'final': result.final,
            'spread': result.spread,
            'total': result.total,
            'moneyline_winner': result.moneyline_winner,
            'spread_winner': result.spread_winner,
            'total_result': result.total_result,
            'last_updated': result.last_updated.isoformat() if result.last_updated else None
        })
    
    return jsonify(formatted_results)

@app.route('/api/game-results/refresh/<int:week>', methods=['POST'])
def refresh_game_results(week):
    """
    API endpoint to fetch fresh game results from external API and store them
    """
    season = 2025
    
    try:
        # Fetch fresh results from API
        game_results = fetch_game_results(week, season)
        
        if not game_results:
            return jsonify({
                'success': False,
                'message': 'No game results found or API error'
            }), 400
        
        # Store results in database
        stored_count = store_game_results(week, season, game_results)
        
        # Automatically calculate pick outcomes
        picks = Pick.query.filter_by(week=week, season=season).all()
        games = Game.query.filter_by(week=week, season=season).all()
        
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
            'message': f'Refreshed {stored_count} game results and updated {results_updated} pick outcomes for Week {week}',
            'games_updated': stored_count,
            'picks_updated': results_updated
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Error refreshing game results: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
    