#!/usr/bin/env python3
"""
Week Simulation Script for Magentamen Picks
Simulates realistic game results for weeks 1-4 to test the system
"""

import random
import json
from datetime import datetime, timedelta
from app import app, db, Game, GameResult, Result, Pick

def generate_realistic_scores():
    """Generate realistic NFL scores"""
    # NFL scores typically range from 3-45 points per team
    # Most games end with totals between 30-60 points
    home_score = random.randint(7, 42)
    away_score = random.randint(3, 38)
    
    # Ensure we don't have ties (very rare in NFL)
    if home_score == away_score:
        home_score += random.choice([3, 7])
    
    return home_score, away_score

def calculate_game_outcomes(home_score, away_score, spread, total):
    """Calculate game outcomes based on scores and odds"""
    # Determine moneyline winner
    if home_score > away_score:
        moneyline_winner = "home"
    else:
        moneyline_winner = "away"
    
    # Calculate spread winner
    if spread is not None:
        home_with_spread = home_score + spread
        if home_with_spread > away_score:
            spread_winner = "home"
        elif away_score > home_with_spread:
            spread_winner = "away"
        else:
            spread_winner = "push"  # Rare but possible
    else:
        spread_winner = None
    
    # Calculate total result
    if total is not None:
        total_points = home_score + away_score
        if total_points > total:
            total_result = "over"
        elif total_points < total:
            total_result = "under"
        else:
            total_result = "push"  # Rare but possible
    else:
        total_result = None
    
    return moneyline_winner, spread_winner, total_result

def get_team_names_from_game(game):
    """Extract team names from game object"""
    return game.home_team, game.away_team

def simulate_week(week):
    """Simulate all games for a given week"""
    print(f"\n🏈 Simulating Week {week}")
    print("=" * 40)
    
    with app.app_context():
        # Get all games for this week
        games = Game.query.filter_by(week=week, season=2025).all()
        
        if not games:
            print(f"   ⚠️  No games found for Week {week}")
            return
        
        print(f"   📅 Found {len(games)} games")
        
        simulated_count = 0
        
        for game in games:
            home_team, away_team = get_team_names_from_game(game)
            
            # Generate realistic scores
            home_score, away_score = generate_realistic_scores()
            
            # Get odds data to calculate spread and total
            spread = None
            total = None
            
            if game.odds_data:
                try:
                    odds_data = json.loads(game.odds_data)
                    # Handle nested bookmakers structure
                    if isinstance(odds_data, dict) and 'bookmakers' in odds_data:
                        odds_data = odds_data['bookmakers']
                    
                    # Find DraftKings odds
                    for bookmaker in odds_data:
                        if isinstance(bookmaker, dict) and bookmaker.get('key') == 'draftkings':
                            for market in bookmaker.get('markets', []):
                                if market.get('key') == 'spreads':
                                    for outcome in market.get('outcomes', []):
                                        if outcome.get('name') == home_team:
                                            spread = outcome.get('point')
                                            break
                                elif market.get('key') == 'totals':
                                    for outcome in market.get('outcomes', []):
                                        if outcome.get('name') == 'Over':
                                            total = outcome.get('point')
                                            break
                            break
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
            
            # Calculate outcomes
            moneyline_winner, spread_winner, total_result = calculate_game_outcomes(
                home_score, away_score, spread, total
            )
            
            # Convert to team names
            if moneyline_winner == "home":
                moneyline_winner_team = home_team
            else:
                moneyline_winner_team = away_team
            
            if spread_winner == "home":
                spread_winner_team = home_team
            elif spread_winner == "away":
                spread_winner_team = away_team
            else:
                spread_winner_team = None
            
            # Store game result
            existing_result = GameResult.query.filter_by(
                week=week,
                season=2025,
                home_team=home_team,
                away_team=away_team
            ).first()
            
            if existing_result:
                # Update existing result
                existing_result.home_score = home_score
                existing_result.away_score = away_score
                existing_result.final = True
                existing_result.spread = spread
                existing_result.total = total
                existing_result.moneyline_winner = moneyline_winner_team
                existing_result.spread_winner = spread_winner_team
                existing_result.total_result = total_result
                existing_result.last_updated = datetime.utcnow()
            else:
                # Create new result
                new_result = GameResult(
                    week=week,
                    season=2025,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=home_score,
                    away_score=away_score,
                    final=True,
                    spread=spread,
                    total=total,
                    moneyline_winner=moneyline_winner_team,
                    spread_winner=spread_winner_team,
                    total_result=total_result
                )
                db.session.add(new_result)
            
            simulated_count += 1
            print(f"   🏟️  {away_team} @ {home_team}: {away_score}-{home_score}")
            print(f"      Winner: {moneyline_winner_team}")
            if spread_winner_team:
                print(f"      Spread: {spread_winner_team}")
            if total_result:
                print(f"      Total: {total_result}")
        
        # Commit all results
        db.session.commit()
        print(f"   ✅ Simulated {simulated_count} games for Week {week}")

def calculate_pick_outcomes_for_week(week):
    """Calculate pick outcomes based on simulated game results"""
    print(f"\n🎯 Calculating pick outcomes for Week {week}")
    
    with app.app_context():
        # Get all picks for this week
        picks = Pick.query.filter_by(week=week, season=2025).all()
        
        if not picks:
            print(f"   ⚠️  No picks found for Week {week}")
            return
        
        print(f"   📝 Found {len(picks)} picks")
        
        # Get game results for this week
        game_results = GameResult.query.filter_by(week=week, season=2025).all()
        
        if not game_results:
            print(f"   ⚠️  No game results found for Week {week}")
            return
        
        # Create lookup for game results
        results_lookup = {}
        for result in game_results:
            game_key = f"{result.away_team} @ {result.home_team}"
            results_lookup[game_key] = result
        
        outcomes_calculated = 0
        
        for pick in picks:
            # Find the game this pick relates to
            game_result = None
            for game_key, result in results_lookup.items():
                # Check if this pick relates to this game
                if pick.category == "Moneyline":
                    if pick.value == result.moneyline_winner:
                        outcome = "win"
                    elif result.moneyline_winner:
                        outcome = "loss"
                    else:
                        outcome = "tie"
                    game_result = result
                    break
                elif pick.category in ["Favorite", "Underdog"]:
                    if pick.value == result.spread_winner:
                        outcome = "win"
                    elif result.spread_winner:
                        outcome = "loss"
                    else:
                        outcome = "tie"
                    game_result = result
                    break
                elif pick.category == "Over":
                    if result.total_result == "over":
                        outcome = "win"
                    elif result.total_result == "under":
                        outcome = "loss"
                    else:
                        outcome = "tie"
                    game_result = result
                    break
                elif pick.category == "Under":
                    if result.total_result == "under":
                        outcome = "win"
                    elif result.total_result == "over":
                        outcome = "loss"
                    else:
                        outcome = "tie"
                    game_result = result
                    break
                elif pick.category == "Touchdown Scorer":
                    # For now, randomly assign outcomes for TD scorers
                    outcome = random.choice(["win", "loss"])
                    game_result = result
                    break
            
            if game_result:
                # Update or create result
                existing_result = Result.query.filter_by(
                    week=week,
                    season=2025,
                    player_id=pick.player_id,
                    category=pick.category
                ).first()
                
                if existing_result:
                    existing_result.outcome = outcome
                else:
                    new_result = Result(
                        week=week,
                        season=2025,
                        player_id=pick.player_id,
                        category=pick.category,
                        outcome=outcome,
                        pick_id=pick.id
                    )
                    db.session.add(new_result)
                
                outcomes_calculated += 1
                print(f"   🎯 {pick.player.name} - {pick.category}: {pick.value} → {outcome}")
        
        # Commit all results
        db.session.commit()
        print(f"   ✅ Calculated {outcomes_calculated} pick outcomes for Week {week}")

def simulate_multiple_weeks(weeks):
    """Simulate multiple weeks"""
    print(f"🚀 Starting simulation for weeks {weeks}")
    print("=" * 50)
    
    for week in weeks:
        simulate_week(week)
        calculate_pick_outcomes_for_week(week)
    
    print(f"\n🎉 Simulation completed for weeks {weeks}!")
    print("\n💡 Next steps:")
    print("   - Check the leaderboard to see updated standings")
    print("   - View results in the UI to see win/loss outcomes")
    print("   - Try different weeks to see the simulated data")

def show_simulation_summary():
    """Show summary of simulated data"""
    print("\n📊 Simulation Summary")
    print("=" * 30)
    
    with app.app_context():
        # Count game results
        total_results = GameResult.query.count()
        print(f"🏟️  Total game results: {total_results}")
        
        # Count by week
        weeks = db.session.query(GameResult.week, db.func.count(GameResult.id)).group_by(GameResult.week).all()
        for week, count in sorted(weeks):
            print(f"   Week {week}: {count} games")
        
        # Count pick results
        total_pick_results = Result.query.count()
        print(f"🎯 Total pick results: {total_pick_results}")
        
        # Count by outcome
        outcomes = db.session.query(Result.outcome, db.func.count(Result.id)).group_by(Result.outcome).all()
        print("📈 Results by outcome:")
        for outcome, count in outcomes:
            print(f"   {outcome}: {count}")

if __name__ == "__main__":
    # Set random seed for reproducible results
    random.seed(42)
    
    # Simulate weeks 1-4
    weeks_to_simulate = [1, 2, 3, 4]
    
    simulate_multiple_weeks(weeks_to_simulate)
    show_simulation_summary()
    
    print("\n🎮 Your simulation is ready!")
    print("   - All weeks 1-4 now have realistic game results")
    print("   - Pick outcomes have been calculated")
    print("   - Leaderboard will show updated standings")
    print("   - You can now test the full system functionality")
