// script.js
const NFL_WEEKS = 18;
const weekSelector = document.getElementById('week-selector');
const gamesList = document.getElementById('games-list');
const PLAYERS = ["Jaren", "JB", "Rory", "Zach"];
const CATEGORIES = ["Moneyline", "Favorite", "Underdog", "Over", "Under", "Touchdown Scorer"];

// Team abbreviations mapping
const TEAM_ABBREVIATIONS = {
    "Kansas City Chiefs": "KC",
    "Baltimore Ravens": "BAL", 
    "Buffalo Bills": "BUF",
    "New York Jets": "NYJ",
    "Dallas Cowboys": "DAL",
    "Philadelphia Eagles": "PHI",
    "Miami Dolphins": "MIA",
    "New England Patriots": "NE",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Pittsburgh Steelers": "PIT",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Tennessee Titans": "TEN",
    "Denver Broncos": "DEN",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Arizona Cardinals": "ARI",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Minnesota Vikings": "MIN",
    "Chicago Bears": "CHI",
    "New Orleans Saints": "NO",
    "Tampa Bay Buccaneers": "TB",
    "Atlanta Falcons": "ATL",
    "Carolina Panthers": "CAR",
    "New York Giants": "NYG",
    "Washington Commanders": "WAS"
};

let currentWeekLocked = false;
let picksMode = true; // true = picks, false = results
let gameResults = {}; // Store game results for automatic outcome calculation

function getTeamAbbreviation(teamName) {
    return TEAM_ABBREVIATIONS[teamName] || teamName;
}

function getCurrentNFLWeek() {
    // NFL 2025 Week 1 starts Sep 4, 2025
    const week1 = new Date(Date.UTC(2025, 8, 4)); // Sep 4, 2025
    const now = new Date();
    const diffDays = Math.floor((now - week1) / (1000 * 60 * 60 * 24));
    let week = Math.floor(diffDays / 7) + 1;
    if (week < 1) week = 1;
    if (week > NFL_WEEKS) week = NFL_WEEKS;
    return week;
}

async function checkWeekLockStatus(week) {
    try {
        const response = await fetch(`/api/week/lock/${week}`);
        const data = await response.json();
        currentWeekLocked = data.locked;
        
        const lockBtn = document.getElementById('lock-week-btn');
        const lockBtnText = document.getElementById('lock-btn-text');
        const lockIcon = lockBtn.querySelector('svg');
        
        if (data.locked) {
            // Show unlock state (grey button)
            lockBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
            lockBtn.classList.add('bg-gray-600', 'hover:bg-gray-700');
            lockBtn.disabled = false;
            lockBtnText.textContent = 'Unlock Week';
            
            // Update icon to show unlocked state
            if (lockIcon) {
                lockIcon.innerHTML = `
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"></path>
                `;
            }
        } else {
            // Show lock state (red button)
            lockBtn.classList.remove('bg-gray-600', 'hover:bg-gray-700');
            lockBtn.classList.add('bg-red-600', 'hover:bg-red-700');
            lockBtn.disabled = false;
            lockBtnText.textContent = 'Lock Week';
            
            // Update icon to show locked state
            if (lockIcon) {
                lockIcon.innerHTML = `
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                `;
            }
        }
        
        return data.locked;
    } catch (error) {
        console.error('Error checking lock status:', error);
        return false;
    }
}

async function toggleWeekLock(week) {
    if (currentWeekLocked) {
        // Week is locked, so unlock it
        if (!confirm('Are you sure you want to unlock this week? This will allow picks to be changed again.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/week/unlock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ week: week })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                alert('Week unlocked successfully!');
                await checkWeekLockStatus(week);
                renderPicksTableWithOptions(); // Re-render to enable dropdowns
            } else {
                alert(data.error || 'Error unlocking week');
            }
        } catch (error) {
            console.error('Error unlocking week:', error);
            alert('Error unlocking week');
        }
    } else {
        // Week is unlocked, so lock it
        if (!confirm('Are you sure you want to lock this week? Once locked, picks cannot be changed until unlocked.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/week/lock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    week: week,
                    locked_by: 'Admin'
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                alert('Week locked successfully!');
                await checkWeekLockStatus(week);
                renderPicksTableWithOptions(); // Re-render to disable dropdowns
            } else {
                alert(data.error || 'Error locking week');
            }
        } catch (error) {
            console.error('Error locking week:', error);
            alert('Error locking week');
        }
    }
}

function populateWeekSelector() {
    weekSelector.innerHTML = '';
    for (let i = 1; i <= NFL_WEEKS; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `Week ${i}`;
        weekSelector.appendChild(option);
    }
    weekSelector.value = getCurrentNFLWeek();
}

function fetchGamesForWeek(week) {
    gamesList.innerHTML = '<div class="p-8 text-center"><div class="space-y-4"><div class="shimmer h-8 rounded"></div><div class="shimmer h-6 rounded"></div><div class="shimmer h-6 rounded"></div></div></div>';
    
    fetch(`/api/games?week=${week}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (Array.isArray(data) && data.length > 0) {
                gamesList.innerHTML = '';
                data.forEach(game => {
                    const home = game.home_team;
                    const away = game.away_team;
                    const homeAbbr = getTeamAbbreviation(home);
                    const awayAbbr = getTeamAbbreviation(away);
                    const commence = new Date(game.commence_time).toLocaleString();
                    
                    // Check if we have odds data (bookmakers array with data)
                    let bookmakersArray = game.bookmakers;
                    if (bookmakersArray && typeof bookmakersArray === 'object' && bookmakersArray.bookmakers) {
                        bookmakersArray = bookmakersArray.bookmakers;
                    }
                    const hasOdds = bookmakersArray && Array.isArray(bookmakersArray) && bookmakersArray.length > 0;
                    
                    const div = document.createElement('div');
                    div.className = 'bg-white rounded-lg shadow-lg p-6 transform hover:scale-105 transition';
                    
                    if (hasOdds) {
                        // Show full team names when we have odds
                        div.innerHTML = `
                            <div class="text-center">
                                <div class="text-lg font-bold text-gray-900 mb-2">${away} @ ${home}</div>
                                <div class="text-sm text-gray-600">${commence}</div>
                                <div class="mt-3 flex justify-center space-x-2">
                                    <span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs">${away}</span>
                                    <span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs">${home}</span>
                                </div>
                                <div class="mt-2">
                                    <span class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">Live Odds</span>
                                </div>
                            </div>
                        `;
                    } else {
                        // Show abbreviated format when no odds available
                        div.innerHTML = `
                            <div class="text-center">
                                <div class="text-2xl font-bold text-gray-900 mb-2">${awayAbbr}/${homeAbbr}</div>
                                <div class="text-sm text-gray-600 mb-2">${away} @ ${home}</div>
                                <div class="text-sm text-gray-500">${commence}</div>
                                <div class="mt-3 flex justify-center space-x-2">
                                    <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">${awayAbbr}</span>
                                    <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">${homeAbbr}</span>
                                </div>
                                <div class="mt-2">
                                    <span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs">Schedule Only</span>
                                </div>
                            </div>
                        `;
                    }
                    gamesList.appendChild(div);
                });
            } else {
                gamesList.innerHTML = '<div class="col-span-full text-center py-8"><p class="text-gray-500">No games found for this week.</p></div>';
            }
        })
        .catch(err => {
            console.error('Error loading games:', err);
            gamesList.innerHTML = '<div class="col-span-full text-center py-8"><p class="text-red-500">Error loading games. Please try again.</p></div>';
        });
}

async function fetchGameResults(week) {
    try {
        const response = await fetch(`/api/game-results/${week}`);
        if (response.ok) {
            const results = await response.json();
            gameResults = {};
            results.forEach(game => {
                const gameKey = `${game.away_team} @ ${game.home_team}`;
                gameResults[gameKey] = game;
            });
        } else {
            console.warn('Failed to fetch game results, using empty results');
            gameResults = {};
        }
    } catch (error) {
        console.error('Error fetching game results:', error);
        gameResults = {};
    }
}

async function fetchPicksForWeek(week) {
    try {
        const res = await fetch(`/api/picks?week=${week}`);
        return res.ok ? await res.json() : {};
    } catch (error) {
        console.error('Error fetching picks:', error);
        return {};
    }
}

function getDraftKingsBookmaker(game) {
    // Handle nested bookmakers structure: game.bookmakers.bookmakers
    let bookmakersArray = game.bookmakers;
    
    // If bookmakers is an object with a bookmakers property, use that
    if (bookmakersArray && typeof bookmakersArray === 'object' && bookmakersArray.bookmakers) {
        bookmakersArray = bookmakersArray.bookmakers;
    }
    
    // Ensure bookmakers is an array before trying to find
    if (!bookmakersArray || !Array.isArray(bookmakersArray)) {
        return null;
    }
    return bookmakersArray.find(bm => bm.key === 'draftkings');
}

function getMoneylineOptions(games) {
    const options = [];
    if (!Array.isArray(games)) return options;
    
    games.forEach(game => {
        // Handle nested bookmakers structure
        let bookmakersArray = game.bookmakers;
        if (bookmakersArray && typeof bookmakersArray === 'object' && bookmakersArray.bookmakers) {
            bookmakersArray = bookmakersArray.bookmakers;
        }
        
        // Skip if no bookmakers data
        if (!bookmakersArray || !Array.isArray(bookmakersArray) || bookmakersArray.length === 0) {
            return;
        }
        
        const draftkings = getDraftKingsBookmaker(game);
        if (!draftkings || !draftkings.markets) return;
        
        const h2h = draftkings.markets.find(m => m.key === 'h2h');
        if (!h2h || !h2h.outcomes) return;
        
        h2h.outcomes.forEach(outcome => {
            const price = outcome.price > 0 ? `+${outcome.price}` : `${outcome.price}`;
            options.push({ label: `${outcome.name} (${price})`, value: outcome.name });
        });
    });
    // Remove duplicates by team name
    const map = {};
    options.forEach(o => { map[o.value] = o.label; });
    return Object.entries(map).map(([value, label]) => ({ value, label }));
}

function getFavoriteUnderdogOptions(games) {
    const favorites = [];
    const underdogs = [];
    if (!Array.isArray(games)) return { favorites: [], underdogs: [] };
    
    games.forEach(game => {
        // Handle nested bookmakers structure
        let bookmakersArray = game.bookmakers;
        if (bookmakersArray && typeof bookmakersArray === 'object' && bookmakersArray.bookmakers) {
            bookmakersArray = bookmakersArray.bookmakers;
        }
        
        // Skip if no bookmakers data
        if (!bookmakersArray || !Array.isArray(bookmakersArray) || bookmakersArray.length === 0) {
            return;
        }
        
        const draftkings = getDraftKingsBookmaker(game);
        if (!draftkings || !draftkings.markets) return;
        
        const spreadsMarket = draftkings.markets.find(m => m.key === 'spreads');
        if (spreadsMarket && spreadsMarket.outcomes && spreadsMarket.outcomes.length === 2) {
            const [team1, team2] = spreadsMarket.outcomes;
            if (team1.point < 0) favorites.push({ name: team1.name, spread: team1.point });
            if (team2.point < 0) favorites.push({ name: team2.name, spread: team2.point });
            if (team1.point > 0) underdogs.push({ name: team1.name, spread: team1.point });
            if (team2.point > 0) underdogs.push({ name: team2.name, spread: team2.point });
        }
    });
    // Remove duplicates by team name
    const favMap = {};
    favorites.forEach(f => { favMap[f.name] = f.spread; });
    const undMap = {};
    underdogs.forEach(u => { undMap[u.name] = u.spread; });
    return {
        favorites: Object.entries(favMap).map(([name, spread]) => ({ name, spread })),
        underdogs: Object.entries(undMap).map(([name, spread]) => ({ name, spread }))
    };
}

function getOverUnderOptions(games) {
    const overs = [];
    const unders = [];
    if (!Array.isArray(games)) return { overs: [], unders: [] };
    
    games.forEach(game => {
        // Handle nested bookmakers structure
        let bookmakersArray = game.bookmakers;
        if (bookmakersArray && typeof bookmakersArray === 'object' && bookmakersArray.bookmakers) {
            bookmakersArray = bookmakersArray.bookmakers;
        }
        
        // Skip if no bookmakers data
        if (!bookmakersArray || !Array.isArray(bookmakersArray) || bookmakersArray.length === 0) {
            return;
        }
        
        const draftkings = getDraftKingsBookmaker(game);
        if (!draftkings || !draftkings.markets) return;
        
        const home = game.home_team;
        const away = game.away_team;
        const gameLabel = `${away} @ ${home}`;
        const totalsMarket = draftkings.markets.find(m => m.key === 'totals');
        if (totalsMarket && totalsMarket.outcomes) {
            totalsMarket.outcomes.forEach(outcome => {
                if (outcome.name === 'Over') overs.push({ label: `Over ${outcome.point} (${gameLabel})`, value: `Over ${outcome.point} (${gameLabel})` });
                if (outcome.name === 'Under') unders.push({ label: `Under ${outcome.point} (${gameLabel})`, value: `Under ${outcome.point} (${gameLabel})` });
            });
        }
    });
    // Remove duplicates by label
    const overMap = {};
    overs.forEach(o => { overMap[o.label] = o.value; });
    const underMap = {};
    unders.forEach(u => { underMap[u.label] = u.value; });
    return {
        overs: Object.entries(overMap).map(([label, value]) => ({ label, value })),
        unders: Object.entries(underMap).map(([label, value]) => ({ label, value }))
    };
}

async function getTouchdownScorerOptions(games) {
    try {
        const abbrs = new Set();
        if (!Array.isArray(games)) return [];
        
        games.forEach(game => {
            const homeTeam = game.home_team;
            const awayTeam = game.away_team;
            
            if (TEAM_ABBREVIATIONS[homeTeam]) abbrs.add(TEAM_ABBREVIATIONS[homeTeam]);
            if (TEAM_ABBREVIATIONS[awayTeam]) abbrs.add(TEAM_ABBREVIATIONS[awayTeam]);
        });
        
        const abbrList = Array.from(abbrs);
        if (abbrList.length === 0) return [];
        
        const res = await fetch(`/api/starters?teams=${abbrList.join(',')}`);
        if (!res.ok) return [];
        const players = await res.json();
        
        return players.map(p => ({
            label: `${p.name} (${p.team}) - ${p.pos}`,
            value: `${p.name} (${p.team})`
        }));
    } catch (error) {
        console.error('Error fetching touchdown scorer options:', error);
        return [];
    }
}

async function savePick(player, category, value, week) {
    if (!value) return;
    
    try {
        const response = await fetch('/api/picks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                week: week,
                player: player,
                category: category,
                value: value
            })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            alert(result.error || 'Error saving pick');
            return false;
        }
        
        return true;
    } catch (error) {
        console.error('Error saving pick:', error);
        alert('Error saving pick');
        return false;
    }
}

function calculatePickOutcome(pick, games) {
    if (!pick || !pick.value || !gameResults) return null;
    
    // Find the game this pick relates to
    let gameResult = null;
    for (const [gameKey, result] of Object.entries(gameResults)) {
        if (result.final) {
            // Check if this pick relates to this game
            if (pick.category === "Moneyline") {
                if (pick.value === result.moneyline_winner) {
                    return "win";
                } else if (result.moneyline_winner) {
                    return "loss";
                }
            } else if (pick.category === "Favorite" || pick.category === "Underdog") {
                if (pick.value === result.spread_winner) {
                    return "win";
                } else if (result.spread_winner) {
                    return "loss";
                }
            } else if (pick.category === "Over") {
                if (result.total_result === "over") {
                    return "win";
                } else if (result.total_result === "under") {
                    return "loss";
                }
            } else if (pick.category === "Under") {
                if (result.total_result === "under") {
                    return "win";
                } else if (result.total_result === "over") {
                    return "loss";
                }
            }
        }
    }
    
    return null; // No result available or game not final
}

async function renderPicksTableWithOptions() {
    try {
        const week = weekSelector.value;
        if (!week) {
            console.error('No week selected');
            return;
        }

        // Show loading state
        document.getElementById('picks-table-container').innerHTML = `
            <div class="p-8">
                <div class="text-center">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
                    <p class="mt-4 text-gray-600">Loading picks...</p>
                </div>
            </div>
        `;

        // Fetch data sequentially to avoid race conditions
        let gamesData = [];
        let picksData = {};
        
        try {
            // Fetch games
            const gamesResponse = await fetch(`/api/games?week=${week}`);
            if (gamesResponse.ok) {
                gamesData = await gamesResponse.json();
            } else {
                console.warn('Failed to fetch games, using empty array');
            }
        } catch (error) {
            console.warn('Error fetching games:', error);
        }

        try {
            // Fetch picks
            picksData = await fetchPicksForWeek(week);
        } catch (error) {
            console.warn('Error fetching picks:', error);
        }

        // Fetch game results in background (non-blocking)
        fetchGameResults(week).catch(err => console.warn('Game results fetch failed:', err));

        // Generate options
        const moneylineOptions = getMoneylineOptions(gamesData);
        const { favorites, underdogs } = getFavoriteUnderdogOptions(gamesData);
        const { overs, unders } = getOverUnderOptions(gamesData);
        
        // Fetch touchdown scorer options (with fallback)
        let tdOptions = [];
        try {
            tdOptions = await getTouchdownScorerOptions(gamesData);
        } catch (error) {
            console.warn('Failed to fetch touchdown scorer options:', error);
            // Provide some fallback options
            tdOptions = [
                { label: "Patrick Mahomes (KC) - QB", value: "Patrick Mahomes (KC)" },
                { label: "Josh Allen (BUF) - QB", value: "Josh Allen (BUF)" },
                { label: "Lamar Jackson (BAL) - QB", value: "Lamar Jackson (BAL)" }
            ];
        }

        let html = '<table class="w-full"><thead class="bg-gradient-to-r from-purple-600 to-purple-700 text-white"><tr><th class="px-6 py-4 text-left text-sm font-medium uppercase tracking-wider">Player</th>';
        CATEGORIES.forEach(cat => {
            html += `<th class="px-6 py-4 text-center text-sm font-medium uppercase tracking-wider">${cat}</th>`;
        });
        html += '</tr></thead><tbody class="divide-y divide-gray-200">';

        PLAYERS.forEach((player, playerIndex) => {
            const rowClass = playerIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white';
            html += `<tr class="${rowClass} hover:bg-purple-50 transition"><td class="px-6 py-4 whitespace-nowrap"><div class="flex items-center"><div class="w-10 h-10 bg-purple-500 rounded-full flex items-center justify-center text-white font-bold mr-3">${player.charAt(0)}</div><span class="text-lg font-medium text-gray-900">${player}</span></div></td>`;
            CATEGORIES.forEach(cat => {
                let options = [];
                if (cat === "Moneyline") options = moneylineOptions;
                else if (cat === "Favorite") options = favorites.map(f => ({ label: `${f.name} (${f.spread > 0 ? '+' : ''}${f.spread})`, value: f.name }));
                else if (cat === "Underdog") options = underdogs.map(u => ({ label: `${u.name} (${u.spread > 0 ? '+' : ''}${u.spread})`, value: u.name }));
                else if (cat === "Over") options = overs;
                else if (cat === "Under") options = unders;
                else if (cat === "Touchdown Scorer") options = tdOptions;

                const taken = new Set();
                Object.entries(picksData).forEach(([otherPlayer, cats]) => {
                    if (otherPlayer !== player && cats[cat]) {
                        taken.add(cats[cat]);
                    }
                });

                const currentPick = picksData[player]?.[cat] || "";

                html += `<td class="px-6 py-4 whitespace-nowrap text-center">`;

                if (!picksMode) {
                    // Results mode: show color-coded outcome with automatic calculation
                    const pickValue = currentPick || '';
                    const outcome = calculatePickOutcome({ value: pickValue, category: cat }, gamesData);
                    let outcomeClass = '';
                    let outcomeText = 'pending';
                    
                    if (outcome === 'win') {
                        outcomeClass = 'result-win';
                        outcomeText = 'win';
                    } else if (outcome === 'loss') {
                        outcomeClass = 'result-loss';
                        outcomeText = 'loss';
                    } else if (outcome === 'tie') {
                        outcomeClass = 'result-tie';
                        outcomeText = 'tie';
                    } else {
                        outcomeClass = 'result-pending';
                        outcomeText = 'pending';
                    }

                    html += `<div class="${outcomeClass} rounded-lg p-3">`;
                    html += `<div class="pick-display">${pickValue || '<span class="text-gray-400">No Pick</span>'}</div>`;
                    html += `<div class="text-xs uppercase">${outcomeText}</div>`;
                    html += `</div>`;
                } else if (currentWeekLocked) {
                    // Locked: show static pick with result color if available
                    const outcome = calculatePickOutcome({ value: currentPick, category: cat }, gamesData);
                    let outcomeClass = '';
                    
                    if (outcome === 'win') {
                        outcomeClass = 'result-win';
                    } else if (outcome === 'loss') {
                        outcomeClass = 'result-loss';
                    } else if (outcome === 'tie') {
                        outcomeClass = 'result-tie';
                    } else {
                        outcomeClass = 'result-pending';
                    }

                    html += `<div class="${outcomeClass} rounded-lg p-3">`;
                    if (currentPick) {
                        html += `<div class="pick-display">${currentPick}</div>`;
                    } else {
                        html += `<div class="pick-display text-gray-500">No Pick</div>`;
                    }
                    if (outcome) {
                        html += `<div class="text-xs uppercase">${outcome}</div>`;
                    }
                    html += `</div>`;
                } else {
                    // Editable dropdown with result preview
                    const outcome = calculatePickOutcome({ value: currentPick, category: cat }, gamesData);
                    let dropdownClass = 'pick-dropdown';
                    if (outcome === 'win') dropdownClass += ' border-green-500 bg-green-50';
                    else if (outcome === 'loss') dropdownClass += ' border-red-500 bg-red-50';
                    else if (outcome === 'tie') dropdownClass += ' border-yellow-500 bg-yellow-50';

                    html += `<select class="${dropdownClass}" data-player="${player}" data-category="${cat}">`;
                    html += `<option value="">-- Select --</option>`;
                    options.forEach(opt => {
                        const disabled = taken.has(opt.value) && currentPick !== opt.value ? 'disabled' : '';
                        const selected = currentPick === opt.value ? 'selected' : '';
                        html += `<option value="${opt.value}" ${disabled} ${selected}>${opt.label}</option>`;
                    });
                    html += `</select>`;
                    
                    if (outcome) {
                        html += `<div class="text-xs mt-1 font-medium ${outcome === 'win' ? 'text-green-600' : outcome === 'loss' ? 'text-red-600' : 'text-yellow-600'}">${outcome.toUpperCase()}</div>`;
                    }
                }
                html += `</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody></table>';
        document.getElementById('picks-table-container').innerHTML = html;

        // Add event listeners to dropdowns (only in picks mode and unlocked)
        if (picksMode && !currentWeekLocked) {
            document.querySelectorAll('.pick-dropdown').forEach(dropdown => {
                dropdown.addEventListener('change', async function() {
                    const player = this.dataset.player;
                    const category = this.dataset.category;
                    const value = this.value;
                    const week = weekSelector.value;

                    if (value) {
                        const success = await savePick(player, category, value, week);
                        if (success) {
                            this.style.borderColor = '#10b981';
                            setTimeout(() => {
                                this.style.borderColor = '#e5e7eb';
                            }, 2000);
                        }
                    }
                });
            });
        }

    } catch (error) {
        console.error('Error rendering picks table:', error);
        document.getElementById('picks-table-container').innerHTML = `
            <div class="p-8 text-center">
                <p class="text-red-500">Error loading picks. Please try again.</p>
                <button onclick="renderPicksTableWithOptions()" class="mt-4 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
                    Retry
                </button>
            </div>
        `;
    }
}

function setModeButtonStyles() {
    document.getElementById('picks-mode-btn').classList.toggle('bg-purple-600', picksMode);
    document.getElementById('picks-mode-btn').classList.toggle('text-white', picksMode);
    document.getElementById('picks-mode-btn').classList.toggle('bg-gray-200', !picksMode);
    document.getElementById('picks-mode-btn').classList.toggle('text-gray-700', !picksMode);

    document.getElementById('results-mode-btn').classList.toggle('bg-purple-600', !picksMode);
    document.getElementById('results-mode-btn').classList.toggle('text-white', !picksMode);
    document.getElementById('results-mode-btn').classList.toggle('bg-gray-200', picksMode);
    document.getElementById('results-mode-btn').classList.toggle('text-gray-700', picksMode);
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    populateWeekSelector();
    fetchGamesForWeek(weekSelector.value);
    checkWeekLockStatus(weekSelector.value).then(() => {
        renderPicksTableWithOptions();
    });
    
    weekSelector.addEventListener('change', function() {
        fetchGamesForWeek(this.value);
        checkWeekLockStatus(this.value).then(() => {
            renderPicksTableWithOptions();
        });
    });
    
    // Lock/Unlock week button
    document.getElementById('lock-week-btn').addEventListener('click', function() {
        toggleWeekLock(weekSelector.value);
    });
    
    // Combined refresh data button (odds + results)
    document.getElementById('refresh-data-btn').addEventListener('click', async function() {
        const week = weekSelector.value;
        if (!week) {
            alert('Please select a week first');
            return;
        }
        
        // Disable button and show loading state
        const btn = this;
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `
            <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            <span>Refreshing...</span>
        `;
        
        try {
            // Step 1: Refresh odds
            btn.innerHTML = `
                <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                <span>Refreshing Odds...</span>
            `;
            
            const oddsResponse = await fetch('/api/games/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ week: week })
            });
            
            const oddsResult = await oddsResponse.json();
            let successMessage = '';
            let hasError = false;
            
            if (oddsResponse.ok) {
                successMessage += `Odds: ${oddsResult.message}\n`;
            } else {
                successMessage += `Odds: ${oddsResult.error || 'Error refreshing odds'}\n`;
                hasError = true;
            }
            
            // Step 2: Refresh game results
            btn.innerHTML = `
                <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
                <span>Refreshing Results...</span>
            `;
            
            const resultsResponse = await fetch(`/api/game-results/refresh/${week}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const resultsResult = await resultsResponse.json();
            
            if (resultsResponse.ok) {
                successMessage += `Results: ${resultsResult.message}`;
            } else {
                successMessage += `Results: ${resultsResult.error || 'Error refreshing game results'}`;
                hasError = true;
            }
            
            // Show combined result
            if (hasError) {
                alert(`Refresh completed with some issues:\n\n${successMessage}`);
            } else {
                alert(`Refresh completed successfully!\n\n${successMessage}`);
            }
            
            // Refresh the display
            fetchGamesForWeek(week);
            renderPicksTableWithOptions();
            
        } catch (error) {
            console.error('Error refreshing data:', error);
            alert('Error refreshing data. Please try again.');
        } finally {
            // Re-enable button
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
    
    // Save all button
    document.getElementById('save-all-btn').addEventListener('click', async function() {
        const dropdowns = document.querySelectorAll('.pick-dropdown');
        let savedCount = 0;
        
        for (const dropdown of dropdowns) {
            if (dropdown.value) {
                const player = dropdown.dataset.player;
                const category = dropdown.dataset.category;
                const value = dropdown.value;
                const week = weekSelector.value;
                
                const success = await savePick(player, category, value, week);
                if (success) savedCount++;
            }
        }
        
        if (savedCount > 0) {
            alert(`Successfully saved ${savedCount} picks!`);
        } else {
            alert('No picks to save.');
        }
    });
    
    // Clear all button
    document.getElementById('clear-all-btn').addEventListener('click', function() {
        if (confirm('Are you sure you want to clear all picks?')) {
            document.querySelectorAll('.pick-dropdown').forEach(dropdown => {
                dropdown.value = '';
            });
        }
    });

    // Mode toggle buttons
    document.getElementById('picks-mode-btn').addEventListener('click', function() {
        picksMode = true;
        setModeButtonStyles();
        renderPicksTableWithOptions();
    });
    document.getElementById('results-mode-btn').addEventListener('click', function() {
        picksMode = false;
        setModeButtonStyles();
        renderPicksTableWithOptions();
    });
});