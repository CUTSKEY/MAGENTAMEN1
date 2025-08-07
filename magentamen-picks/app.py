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
        {"name": "Tua Tagovailoa", "position": "QB", "team": "MIA"},
        {"name": "Joe Burrow", "position": "QB", "team": "CIN"},
        {"name": "Justin Herbert", "position": "QB", "team": "LAC"},
        {"name": "Trevor Lawrence", "position": "QB", "team": "JAX"},
        {"name": "Deshaun Watson", "position": "QB", "team": "CLE"},
        {"name": "Kenny Pickett", "position": "QB", "team": "PIT"},
        {"name": "C.J. Stroud", "position": "QB", "team": "HOU"},
        {"name": "Anthony Richardson", "position": "QB", "team": "IND"},
        {"name": "Will Levis", "position": "QB", "team": "TEN"},
        {"name": "Russell Wilson", "position": "QB", "team": "DEN"},
        {"name": "Jimmy Garoppolo", "position": "QB", "team": "LV"},
        {"name": "Matthew Stafford", "position": "QB", "team": "LAR"},
        {"name": "Brock Purdy", "position": "QB", "team": "SF"},
        {"name": "Geno Smith", "position": "QB", "team": "SEA"},
        {"name": "Kyler Murray", "position": "QB", "team": "ARI"},
        {"name": "Jared Goff", "position": "QB", "team": "DET"},
        {"name": "Jordan Love", "position": "QB", "team": "GB"},
        {"name": "Kirk Cousins", "position": "QB", "team": "MIN"},
        {"name": "Justin Fields", "position": "QB", "team": "CHI"},
        {"name": "Derek Carr", "position": "QB", "team": "NO"},
        {"name": "Baker Mayfield", "position": "QB", "team": "TB"},
        {"name": "Desmond Ridder", "position": "QB", "team": "ATL"},
        {"name": "Bryce Young", "position": "QB", "team": "CAR"},
        {"name": "Daniel Jones", "position": "QB", "team": "NYG"},
        {"name": "Sam Howell", "position": "QB", "team": "WAS"},
        {"name": "Aaron Rodgers", "position": "QB", "team": "NYJ"},
        {"name": "Mac Jones", "position": "QB", "team": "NE"},
        
        # Running Backs
        {"name": "Christian McCaffrey", "position": "RB", "team": "SF"},
        {"name": "Saquon Barkley", "position": "RB", "team": "PHI"},
        {"name": "Austin Ekeler", "position": "RB", "team": "LAC"},
        {"name": "Derrick Henry", "position": "RB", "team": "BAL"},
        {"name": "Nick Chubb", "position": "RB", "team": "CLE"},
        {"name": "Alvin Kamara", "position": "RB", "team": "NO"},
        {"name": "Josh Jacobs", "position": "RB", "team": "GB"},
        {"name": "Tony Pollard", "position": "RB", "team": "TEN"},
        {"name": "Rachaad White", "position": "RB", "team": "TB"},
        {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
        {"name": "Travis Etienne", "position": "RB", "team": "JAX"},
        {"name": "James Cook", "position": "RB", "team": "BUF"},
        {"name": "Najee Harris", "position": "RB", "team": "PIT"},
        {"name": "Dameon Pierce", "position": "RB", "team": "HOU"},
        {"name": "Jonathan Taylor", "position": "RB", "team": "IND"},
        {"name": "Javonte Williams", "position": "RB", "team": "DEN"},
        {"name": "Josh Jacobs", "position": "RB", "team": "LV"},
        {"name": "Kyren Williams", "position": "RB", "team": "LAR"},
        {"name": "Kenneth Walker", "position": "RB", "team": "SEA"},
        {"name": "James Conner", "position": "RB", "team": "ARI"},
        {"name": "David Montgomery", "position": "RB", "team": "DET"},
        {"name": "Aaron Jones", "position": "RB", "team": "GB"},
        {"name": "Alexander Mattison", "position": "RB", "team": "MIN"},
        {"name": "Khalil Herbert", "position": "RB", "team": "CHI"},
        {"name": "Jamaal Williams", "position": "RB", "team": "NO"},
        {"name": "Rachaad White", "position": "RB", "team": "TB"},
        {"name": "Tyler Allgeier", "position": "RB", "team": "ATL"},
        {"name": "Miles Sanders", "position": "RB", "team": "CAR"},
        {"name": "Saquon Barkley", "position": "RB", "team": "NYG"},
        {"name": "Brian Robinson", "position": "RB", "team": "WAS"},
        
        # Wide Receivers
        {"name": "Tyreek Hill", "position": "WR", "team": "MIA"},
        {"name": "Justin Jefferson", "position": "WR", "team": "MIN"},
        {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
        {"name": "CeeDee Lamb", "position": "WR", "team": "DAL"},
        {"name": "A.J. Brown", "position": "WR", "team": "PHI"},
        {"name": "Stefon Diggs", "position": "WR", "team": "HOU"},
        {"name": "Davante Adams", "position": "WR", "team": "LV"},
        {"name": "Cooper Kupp", "position": "WR", "team": "LAR"},
        {"name": "Deebo Samuel", "position": "WR", "team": "SF"},
        {"name": "DK Metcalf", "position": "WR", "team": "SEA"},
        {"name": "Marquise Brown", "position": "WR", "team": "ARI"},
        {"name": "Amon-Ra St. Brown", "position": "WR", "team": "DET"},
        {"name": "Christian Watson", "position": "WR", "team": "GB"},
        {"name": "D.J. Moore", "position": "WR", "team": "CHI"},
        {"name": "Chris Olave", "position": "WR", "team": "NO"},
        {"name": "Mike Evans", "position": "WR", "team": "TB"},
        {"name": "Drake London", "position": "WR", "team": "ATL"},
        {"name": "Adam Thielen", "position": "WR", "team": "CAR"},
        {"name": "Darius Slayton", "position": "WR", "team": "NYG"},
        {"name": "Terry McLaurin", "position": "WR", "team": "WAS"},
        {"name": "Garrett Wilson", "position": "WR", "team": "NYJ"},
        {"name": "DeVante Parker", "position": "WR", "team": "NE"},
        {"name": "Rashee Rice", "position": "WR", "team": "KC"},
        {"name": "Gabe Davis", "position": "WR", "team": "BUF"},
        {"name": "Zay Flowers", "position": "WR", "team": "BAL"},
        {"name": "DeVonta Smith", "position": "WR", "team": "PHI"},
        {"name": "Jaylen Waddle", "position": "WR", "team": "MIA"},
        {"name": "Tee Higgins", "position": "WR", "team": "CIN"},
        {"name": "Amari Cooper", "position": "WR", "team": "CLE"},
        {"name": "George Pickens", "position": "WR", "team": "PIT"},
        {"name": "Nico Collins", "position": "WR", "team": "HOU"},
        {"name": "Michael Pittman", "position": "WR", "team": "IND"},
        {"name": "Calvin Ridley", "position": "WR", "team": "JAX"},
        {"name": "DeAndre Hopkins", "position": "WR", "team": "TEN"},
        {"name": "Courtland Sutton", "position": "WR", "team": "DEN"},
        {"name": "Jakobi Meyers", "position": "WR", "team": "LV"},
        {"name": "Keenan Allen", "position": "WR", "team": "LAC"},
        {"name": "Puka Nacua", "position": "WR", "team": "LAR"},
        {"name": "Brandon Aiyuk", "position": "WR", "team": "SF"},
        {"name": "Tyler Lockett", "position": "WR", "team": "SEA"},
        
        # Tight Ends
        {"name": "Travis Kelce", "position": "TE", "team": "KC"},
        {"name": "Mark Andrews", "position": "TE", "team": "BAL"},
        {"name": "Dawson Knox", "position": "TE", "team": "BUF"},
        {"name": "Dallas Goedert", "position": "TE", "team": "PHI"},
        {"name": "Durham Smythe", "position": "TE", "team": "MIA"},
        {"name": "Hunter Henry", "position": "TE", "team": "NE"},
        {"name": "Irv Smith", "position": "TE", "team": "CIN"},
        {"name": "David Njoku", "position": "TE", "team": "CLE"},
        {"name": "Pat Freiermuth", "position": "TE", "team": "PIT"},
        {"name": "Dalton Schultz", "position": "TE", "team": "HOU"},
        {"name": "Jelani Woods", "position": "TE", "team": "IND"},
        {"name": "Evan Engram", "position": "TE", "team": "JAX"},
        {"name": "Chigoziem Okonkwo", "position": "TE", "team": "TEN"},
        {"name": "Greg Dulcich", "position": "TE", "team": "DEN"},
        {"name": "Michael Mayer", "position": "TE", "team": "LV"},
        {"name": "Gerald Everett", "position": "TE", "team": "LAC"},
        {"name": "Tyler Higbee", "position": "TE", "team": "LAR"},
        {"name": "George Kittle", "position": "TE", "team": "SF"},
        {"name": "Noah Fant", "position": "TE", "team": "SEA"},
        {"name": "Trey McBride", "position": "TE", "team": "ARI"},
        {"name": "Sam LaPorta", "position": "TE", "team": "DET"},
        {"name": "Luke Musgrave", "position": "TE", "team": "GB"},
        {"name": "T.J. Hockenson", "position": "TE", "team": "MIN"},
        {"name": "Cole Kmet", "position": "TE", "team": "CHI"},
        {"name": "Juwan Johnson", "position": "TE", "team": "NO"},
        {"name": "Cade Otton", "position": "TE", "team": "TB"},
        {"name": "Kyle Pitts", "position": "TE", "team": "ATL"},
        {"name": "Hayden Hurst", "position": "TE", "team": "CAR"},
        {"name": "Darren Waller", "position": "TE", "team": "NYG"},
        {"name": "Logan Thomas", "position": "TE", "team": "WAS"},
        {"name": "Tyler Conklin", "position": "TE", "team": "NYJ"}
    ]
    
    for player_data in sample_nfl_players:
        if not NFLPlayer.query.filter_by(name=player_data["name"], team=player_data["team"]).first():
            player = NFLPlayer(**player_data)
            db.session.add(player)
    
    db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/games')
def get_games():
    week = request.args.get('week', type=int)
    if not week:
        return jsonify([])
    
    # Check if we have games for this week in the database
    games = Game.query.filter_by(week=week, season=2025).all()
    
    if games:
        # Return games from database
        return jsonify([{
            'home_team': game.home_team,
            'away_team': game.away_team,
            'commence_time': game.commence_time,
            'bookmakers': json.loads(game.odds_data) if game.odds_data else []
        } for game in games])
    
    # If no games in database, fetch from API
    if not ODDS_API_KEY:
        return jsonify([])
    
    # Calculate the date for the week
    week_start = NFL_2025_WEEK1_START + timedelta(weeks=week-1)
    week_end = week_start + timedelta(days=7)
    
    # Format dates for API
    start_date = week_start.strftime('%Y-%m-%d')
    end_date = week_end.strftime('%Y-%m-%d')
    
    try:
        # Fetch odds from The Odds API
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
        
        # Filter games for the specific week and store in database
        week_games = []
        for game in games_data:
            game_date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
            if week_start <= game_date < week_end:
                # Store game in database
                db_game = Game(
                    week=week,
                    season=2025,
                    home_team=game['home_team'],
                    away_team=game['away_team'],
                    commence_time=game['commence_time'],
                    odds_data=json.dumps(game['bookmakers'])
                )
                db.session.add(db_game)
                week_games.append({
                    'home_team': game['home_team'],
                    'away_team': game['away_team'],
                    'commence_time': game['commence_time'],
                    'bookmakers': game['bookmakers']
                })
        
        db.session.commit()
        return jsonify(week_games)
        
    except requests.RequestException as e:
        print(f"Error fetching games: {e}")
        return jsonify([])

@app.route('/api/picks', methods=['GET'])
def get_picks():
    week = request.args.get('week', type=int)
    if not week:
        return jsonify({})
    
    picks = Pick.query.filter_by(week=week, season=2025).all()
    
    result = {}
    for pick in picks:
        player_name = pick.player.name
        if player_name not in result:
            result[player_name] = {}
        result[player_name][pick.category] = pick.value
    
    return jsonify(result)

@app.route('/api/picks', methods=['POST'])
def save_pick():
    data = request.get_json()
    week = data.get('week')
    player_name = data.get('player')
    category = data.get('category')
    value = data.get('value')
    
    if not all([week, player_name, category, value]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Get or create player
        player = Player.query.filter_by(name=player_name).first()
        if not player:
            player = Player(name=player_name)
            db.session.add(player)
            db.session.flush()
        
        # Check if pick already exists
        existing_pick = Pick.query.filter_by(
            week=week,
            season=2025,
            player_id=player.id,
            category=category
        ).first()
        
        if existing_pick:
            # Update existing pick
            existing_pick.value = value
        else:
            # Create new pick
            pick = Pick(
                week=week,
                season=2025,
                player_id=player.id,
                category=category,
                value=value
            )
            db.session.add(pick)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/leaderboard')
def leaderboard_page():
    return render_template('leaderboard.html')

@app.route('/api/leaderboard')
def leaderboard_api():
    # Get all results grouped by player
    results = db.session.query(
        Player.name,
        db.func.count(Result.id).label('total_picks'),
        db.func.sum(db.case((Result.outcome == 'win', 1), else_=0)).label('wins'),
        db.func.sum(db.case((Result.outcome == 'loss', 1), else_=0)).label('losses'),
        db.func.sum(db.case((Result.outcome == 'tie', 1), else_=0)).label('ties')
    ).join(Result, Player.id == Result.player_id).group_by(Player.id, Player.name).all()
    
    leaderboard = []
    for result in results:
        total_picks = result.total_picks or 0
        wins = result.wins or 0
        losses = result.losses or 0
        ties = result.ties or 0
        
        if total_picks > 0:
            win_percentage = (wins / total_picks) * 100
            leaderboard.append({
                'player': result.name,
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'total_picks': total_picks,
                'win_percentage': round(win_percentage, 1)
            })
    
    # Sort by win percentage (descending)
    leaderboard.sort(key=lambda x: x['win_percentage'], reverse=True)
    
    return jsonify(leaderboard)

@app.route('/api/starters')
def get_starters():
    teams = request.args.get('teams', '').split(',')
    if not teams or teams[0] == '':
        return jsonify([])
    
    # Get active players for the specified teams
    players = NFLPlayer.query.filter(
        NFLPlayer.team.in_(teams),
        NFLPlayer.active == True
    ).all()
    
    return jsonify([{
        'name': player.name,
        'team': player.team,
        'pos': player.position
    } for player in players])

# Remove the separate results route since we're combining it with picks
# @app.route('/results')
# def results_page():
#     return render_template('results.html')

@app.route('/api/results', methods=['GET'])
def get_results():
    week = request.args.get('week', type=int)
    if not week:
        return jsonify({})
    
    # Get all results for the week
    results = Result.query.filter_by(week=week, season=2025).all()
    
    result_data = {}
    for result in results:
        player_name = result.player.name
        if player_name not in result_data:
            result_data[player_name] = {}
        
        # Get the original pick value
        pick_value = ""
        if result.pick_id:
            pick = Pick.query.get(result.pick_id)
            if pick:
                pick_value = pick.value
        
        result_data[player_name][result.category] = {
            'outcome': result.outcome,
            'pick': pick_value
        }
    
    return jsonify(result_data)

@app.route('/api/results', methods=['POST'])
def save_result():
    data = request.get_json()
    week = data.get('week')
    player_name = data.get('player')
    category = data.get('category')
    outcome = data.get('outcome')
    
    if not all([week, player_name, category, outcome]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Get player
        player = Player.query.filter_by(name=player_name).first()
        if not player:
            return jsonify({'error': 'Player not found'}), 404
        
        # Get the pick for this player/category/week
        pick = Pick.query.filter_by(
            week=week,
            season=2025,
            player_id=player.id,
            category=category
        ).first()
        
        # Check if result already exists
        existing_result = Result.query.filter_by(
            week=week,
            season=2025,
            player_id=player.id,
            category=category
        ).first()
        
        if existing_result:
            # Update existing result
            existing_result.outcome = outcome
            if pick:
                existing_result.pick_id = pick.id
        else:
            # Create new result
            result = Result(
                week=week,
                season=2025,
                player_id=player.id,
                category=category,
                outcome=outcome,
                pick_id=pick.id if pick else None
            )
            db.session.add(result)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/week/lock', methods=['POST'])
def lock_week():
    data = request.get_json()
    week = data.get('week')
    locked_by = data.get('locked_by', 'Admin')
    
    if not week:
        return jsonify({'error': 'Week is required'}), 400
    
    try:
        # Check if week is already locked
        existing_lock = WeekLock.query.filter_by(week=week, season=2025).first()
        if existing_lock:
            return jsonify({'error': 'Week is already locked'}), 400
        
        # Create new lock
        lock = WeekLock(
            week=week,
            season=2025,
            locked_by=locked_by
        )
        db.session.add(lock)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Week {week} locked successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/week/lock/<int:week>')
def get_week_lock_status(week):
    lock = WeekLock.query.filter_by(week=week, season=2025).first()
    
    if lock:
        return jsonify({
            'locked': True,
            'locked_at': lock.locked_at.isoformat(),
            'locked_by': lock.locked_by
        })
    else:
        return jsonify({
            'locked': False,
            'locked_at': None,
            'locked_by': None
        })

@app.route('/api/results/calculate', methods=['POST'])
def calculate_results():
    data = request.get_json()
    week = data.get('week')
    
    if not week:
        return jsonify({'error': 'Week is required'}), 400
    
    try:
        # Get all picks for the week
        picks = Pick.query.filter_by(week=week, season=2025).all()
        
        # Get game results
        game_results = fetch_game_results(week, 2025)
        
        # Get games for reference
        games = Game.query.filter_by(week=week, season=2025).all()
        
        calculated_count = 0
        for pick in picks:
            outcome = calculate_pick_outcome(pick, game_results, games)
            if outcome:
                # Check if result already exists
                existing_result = Result.query.filter_by(
                    week=week,
                    season=2025,
                    player_id=pick.player_id,
                    category=pick.category
                ).first()
                
                if existing_result:
                    existing_result.outcome = outcome
                    existing_result.pick_id = pick.id
                else:
                    result = Result(
                        week=week,
                        season=2025,
                        player_id=pick.player_id,
                        category=pick.category,
                        outcome=outcome,
                        pick_id=pick.id
                    )
                    db.session.add(result)
                
                calculated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Calculated {calculated_count} results for Week {week}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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
    