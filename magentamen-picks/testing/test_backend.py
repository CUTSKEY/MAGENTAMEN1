#!/usr/bin/env python3
"""
Backend Test Script for Magentamen Picks
Tests all major functionality with sample data
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
TEST_WEEK = 1

def test_api_endpoint(endpoint, method="GET", data=None, description=""):
    """Test an API endpoint and return results"""
    print(f"\n🧪 Testing: {description}")
    print(f"   {method} {endpoint}")
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}")
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if isinstance(result, list):
                    print(f"   ✅ Success: {len(result)} items returned")
                    if result and len(result) > 0:
                        print(f"   📊 Sample item: {json.dumps(result[0], indent=2)[:200]}...")
                elif isinstance(result, dict):
                    print(f"   ✅ Success: {result.get('message', 'Data returned')}")
                    if 'games_updated' in result:
                        print(f"   📊 Games updated: {result['games_updated']}")
                    if 'picks_updated' in result:
                        print(f"   📊 Picks updated: {result['picks_updated']}")
                else:
                    print(f"   ✅ Success: {result}")
            except json.JSONDecodeError:
                print(f"   ✅ Success: Non-JSON response ({len(response.text)} chars)")
        else:
            print(f"   ❌ Error: {response.text}")
        
        return response.status_code == 200, response.json() if response.status_code == 200 else None
        
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection Error: Is the Flask app running on {BASE_URL}?")
        return False, None
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False, None

def test_database_data():
    """Test database contains expected data"""
    print("\n🗄️  Testing Database Data")
    
    # Test games endpoint
    success, games_data = test_api_endpoint(f"/api/games?week={TEST_WEEK}", 
                                          description=f"Games for Week {TEST_WEEK}")
    
    if success and games_data:
        print(f"   📈 Found {len(games_data)} games")
        
        # Check if games have odds data
        games_with_odds = [g for g in games_data if g.get('bookmakers')]
        print(f"   🎯 {len(games_with_odds)} games have odds data")
        
        # Sample game analysis
        if games_data:
            sample_game = games_data[0]
            print(f"   🏈 Sample game: {sample_game['away_team']} @ {sample_game['home_team']}")
            if sample_game.get('bookmakers'):
                print(f"   💰 Has odds data: {len(sample_game['bookmakers'])} bookmakers")
    
    # Test starters endpoint
    success, starters_data = test_api_endpoint("/api/starters?teams=KC,BUF,BAL,PHI", 
                                             description="NFL Players for sample teams")
    
    if success and starters_data:
        print(f"   👥 Found {len(starters_data)} players")
        
        # Group by position
        positions = {}
        for player in starters_data:
            pos = player['pos']
            positions[pos] = positions.get(pos, 0) + 1
        
        print(f"   📊 Players by position: {positions}")

def test_picks_functionality():
    """Test picks saving and retrieval"""
    print("\n🎯 Testing Picks Functionality")
    
    # Test getting picks (should be empty initially)
    success, picks_data = test_api_endpoint(f"/api/picks?week={TEST_WEEK}", 
                                          description="Get existing picks")
    
    if success:
        print(f"   📝 Current picks: {len(picks_data)} players have picks")
    
    # Test saving a sample pick
    sample_pick = {
        "week": TEST_WEEK,
        "player": "Jaren",
        "category": "Moneyline",
        "value": "Kansas City Chiefs"
    }
    
    success, result = test_api_endpoint("/api/picks", method="POST", data=sample_pick,
                                      description="Save sample pick")
    
    if success:
        print("   ✅ Sample pick saved successfully")
        
        # Verify pick was saved
        success, updated_picks = test_api_endpoint(f"/api/picks?week={TEST_WEEK}", 
                                                 description="Verify pick was saved")
        if success and "Jaren" in updated_picks:
            print("   ✅ Pick verification successful")

def test_game_results():
    """Test game results functionality"""
    print("\n🏆 Testing Game Results Functionality")
    
    # Test getting game results (should be empty initially)
    success, results_data = test_api_endpoint(f"/api/game-results/{TEST_WEEK}", 
                                            description="Get game results")
    
    if success:
        print(f"   📊 Current results: {len(results_data)} games have results")
    
    # Test refreshing game results (this will try to fetch from API)
    success, refresh_result = test_api_endpoint(f"/api/game-results/refresh/{TEST_WEEK}", 
                                              method="POST",
                                              description="Refresh game results from API")
    
    if success:
        print("   ✅ Game results refresh completed")
        if refresh_result:
            print(f"   📈 {refresh_result.get('message', 'Results updated')}")
    else:
        print("   ⚠️  Game results refresh failed (expected if no live games)")

def test_week_locking():
    """Test week locking functionality"""
    print("\n🔒 Testing Week Locking")
    
    # Check current lock status
    success, lock_status = test_api_endpoint(f"/api/week/lock/{TEST_WEEK}", 
                                           description="Check week lock status")
    
    if success and lock_status:
        is_locked = lock_status.get('locked', False)
        print(f"   🔓 Week {TEST_WEEK} is currently {'locked' if is_locked else 'unlocked'}")
    
    # Test locking the week
    lock_data = {
        "week": TEST_WEEK,
        "locked_by": "Test User"
    }
    
    success, result = test_api_endpoint("/api/week/lock", method="POST", data=lock_data,
                                      description="Lock the week")
    
    if success:
        print("   ✅ Week locked successfully")
        
        # Verify lock status
        success, updated_status = test_api_endpoint(f"/api/week/lock/{TEST_WEEK}", 
                                                  description="Verify week is locked")
        if success and updated_status.get('locked'):
            print("   ✅ Lock verification successful")
    
    # Test unlocking the week
    unlock_data = {"week": TEST_WEEK}
    success, result = test_api_endpoint("/api/week/unlock", method="POST", data=unlock_data,
                                      description="Unlock the week")
    
    if success:
        print("   ✅ Week unlocked successfully")

def test_leaderboard():
    """Test leaderboard functionality"""
    print("\n🏅 Testing Leaderboard")
    
    success, leaderboard_data = test_api_endpoint("/api/leaderboard", 
                                                description="Get leaderboard data")
    
    if success and leaderboard_data:
        print(f"   🏆 Found {len(leaderboard_data)} players in leaderboard")
        if leaderboard_data:
            top_player = leaderboard_data[0]
            print(f"   🥇 Top player: {top_player['player']} ({top_player['total_points']} points)")

def main():
    """Run all backend tests"""
    print("🚀 Starting Backend Tests for Magentamen Picks")
    print("=" * 60)
    
    # Check if Flask app is running
    print("\n🔍 Checking if Flask app is running...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Flask app is running")
        else:
            print(f"⚠️  Flask app responded with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Flask app is not running. Please start it with: python app.py")
        return
    
    # Run all tests
    test_database_data()
    test_picks_functionality()
    test_game_results()
    test_week_locking()
    test_leaderboard()
    
    print("\n" + "=" * 60)
    print("🎉 Backend testing completed!")
    print("\n💡 Tips:")
    print("   - If game results refresh failed, that's normal (no live games)")
    print("   - Try the 'Refresh Data' button in the UI to test live API integration")
    print("   - Check the database directly if you need to verify data persistence")

if __name__ == "__main__":
    main()
