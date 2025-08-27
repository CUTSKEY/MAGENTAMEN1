#!/usr/bin/env python3
"""
Database Test Script for Magentamen Picks
Tests database structure and sample data
"""

from app import app, db, Game, Player, Pick, Result, NFLPlayer, WeekLock, GameResult

def test_database_structure():
    """Test database structure and sample data"""
    print("🗄️  Testing Database Structure and Sample Data")
    print("=" * 50)
    
    with app.app_context():
        # Test Games
        games = Game.query.all()
        print(f"\n📅 Games: {len(games)} total")
        if games:
            week1_games = Game.query.filter_by(week=1, season=2025).all()
            print(f"   Week 1: {len(week1_games)} games")
            if week1_games:
                sample_game = week1_games[0]
                print(f"   Sample: {sample_game.away_team} @ {sample_game.home_team}")
                print(f"   Has odds: {'Yes' if sample_game.odds_data else 'No'}")
        
        # Test Players
        players = Player.query.all()
        print(f"\n👥 Fantasy Players: {len(players)} total")
        for player in players:
            print(f"   - {player.name}")
        
        # Test NFL Players
        nfl_players = NFLPlayer.query.all()
        print(f"\n🏈 NFL Players: {len(nfl_players)} total")
        
        # Group by team
        teams = {}
        for player in nfl_players:
            team = player.team
            if team not in teams:
                teams[team] = []
            teams[team].append(f"{player.name} ({player.position})")
        
        print("   Players by team:")
        for team, players_list in sorted(teams.items()):
            print(f"   {team}: {len(players_list)} players")
            if len(players_list) <= 3:
                print(f"     {', '.join(players_list)}")
            else:
                print(f"     {', '.join(players_list[:3])}... (+{len(players_list)-3} more)")
        
        # Test Picks
        picks = Pick.query.all()
        print(f"\n🎯 Picks: {len(picks)} total")
        if picks:
            week1_picks = Pick.query.filter_by(week=1, season=2025).all()
            print(f"   Week 1: {len(week1_picks)} picks")
            
            # Group by player
            picks_by_player = {}
            for pick in week1_picks:
                player_name = pick.player.name
                if player_name not in picks_by_player:
                    picks_by_player[player_name] = []
                picks_by_player[player_name].append(f"{pick.category}: {pick.value}")
            
            print("   Picks by player:")
            for player, player_picks in picks_by_player.items():
                print(f"   {player}: {len(player_picks)} picks")
                for pick in player_picks:
                    print(f"     - {pick}")
        
        # Test Results
        results = Result.query.all()
        print(f"\n🏆 Results: {len(results)} total")
        if results:
            week1_results = Result.query.filter_by(week=1, season=2025).all()
            print(f"   Week 1: {len(week1_results)} results")
            
            # Count by outcome
            outcomes = {}
            for result in week1_results:
                outcome = result.outcome
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
            
            print("   Results by outcome:")
            for outcome, count in outcomes.items():
                print(f"     {outcome}: {count}")
        
        # Test Game Results
        game_results = GameResult.query.all()
        print(f"\n📊 Game Results: {len(game_results)} total")
        if game_results:
            week1_game_results = GameResult.query.filter_by(week=1, season=2025).all()
            print(f"   Week 1: {len(week1_game_results)} game results")
            
            for result in week1_game_results[:3]:  # Show first 3
                print(f"   {result.away_team} @ {result.home_team}")
                if result.final:
                    print(f"     Final: {result.away_score} - {result.home_score}")
                    print(f"     Winner: {result.moneyline_winner}")
                else:
                    print(f"     Status: Not final")
        
        # Test Week Locks
        locks = WeekLock.query.all()
        print(f"\n🔒 Week Locks: {len(locks)} total")
        for lock in locks:
            print(f"   Week {lock.week}: {'Locked' if lock else 'Unlocked'} by {lock.locked_by}")

def test_sample_data_quality():
    """Test the quality and completeness of sample data"""
    print("\n🔍 Testing Sample Data Quality")
    print("=" * 50)
    
    with app.app_context():
        # Check if we have games for multiple weeks
        weeks = db.session.query(Game.week).distinct().all()
        weeks = [w[0] for w in weeks]
        print(f"📅 Games available for weeks: {sorted(weeks)}")
        
        # Check odds data coverage
        games_with_odds = Game.query.filter(Game.odds_data.isnot(None)).count()
        total_games = Game.query.count()
        print(f"💰 Games with odds data: {games_with_odds}/{total_games} ({games_with_odds/total_games*100:.1f}%)")
        
        # Check NFL player coverage by position
        positions = db.session.query(NFLPlayer.position, db.func.count(NFLPlayer.id)).group_by(NFLPlayer.position).all()
        print(f"🏈 NFL Players by position:")
        for pos, count in positions:
            print(f"   {pos}: {count}")
        
        # Check team coverage
        teams = db.session.query(NFLPlayer.team, db.func.count(NFLPlayer.id)).group_by(NFLPlayer.team).all()
        print(f"🏟️  NFL Players by team:")
        for team, count in sorted(teams):
            print(f"   {team}: {count}")

if __name__ == "__main__":
    test_database_structure()
    test_sample_data_quality()
    print("\n✅ Database testing completed!")
