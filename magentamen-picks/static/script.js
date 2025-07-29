// script.js
// Frontend logic will go here 
const NFL_WEEKS = 18;
const weekSelector = document.getElementById('week-selector');
const gamesList = document.getElementById('games-list');
const PLAYERS = ["Jaren", "JB", "Rory", "Zach"];
const CATEGORIES = ["Moneyline", "Favorite", "Underdog", "Over", "Under", "Touchdown Scorer"];

const TEAM_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS"
};

function getCurrentNFLWeek() {
    // NFL 2024 Week 1 starts Sep 5, 2024
    const week1 = new Date(Date.UTC(2024, 8, 5)); // Months are 0-indexed
    const now = new Date();
    const diffDays = Math.floor((now - week1) / (1000 * 60 * 60 * 24));
    let week = Math.floor(diffDays / 7) + 1;
    if (week < 1) week = 1;
    if (week > NFL_WEEKS) week = NFL_WEEKS;
    return week;
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
    gamesList.innerHTML = '<p>Loading games...</p>';
    fetch(`/api/games?week=${week}`)
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data) && data.length > 0) {
                gamesList.innerHTML = `<h2>NFL Games - Week ${week}</h2>`;
                data.forEach(game => {
                    const home = game.home_team;
                    const away = game.away_team;
                    const commence = new Date(game.commence_time).toLocaleString();
                    const div = document.createElement('div');
                    div.className = 'game';
                    div.innerHTML = `<strong>${away} @ ${home}</strong> <br><span>${commence}</span>`;
                    gamesList.appendChild(div);
                });
            } else {
                gamesList.innerHTML = '<p>No games found for this week.</p>';
            }
        })
        .catch(err => {
            gamesList.innerHTML = '<p>Error loading games.</p>';
            console.error(err);
        });
}

function getCurrentWeekKey() {
    return `2025-${weekSelector.value}`;
}

async function fetchPicksForWeek(weekKey) {
    const res = await fetch(`/api/picks?week=${weekKey}`);
    return res.ok ? await res.json() : {};
}

function getTeamOptions(games) {
    const teams = new Set();
    games.forEach(game => {
        teams.add(game.home_team);
        teams.add(game.away_team);
    });
    return Array.from(teams).sort();
}

function getFanDuelBookmaker(game) {
    return game.bookmakers?.find(bm => bm.key === 'fanduel');
}

function getMoneylineOptions(games) {
    // For each game, get FanDuel h2h outcomes
    const options = [];
    games.forEach(game => {
        const fanduel = getFanDuelBookmaker(game);
        if (!fanduel) return;
        const h2h = fanduel.markets?.find(m => m.key === 'h2h');
        if (!h2h) return;
        h2h.outcomes.forEach(outcome => {
            // Format price as +245 or -300
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
    games.forEach(game => {
        const fanduel = getFanDuelBookmaker(game);
        if (!fanduel) return;
        const spreadsMarket = fanduel.markets?.find(m => m.key === 'spreads');
        if (spreadsMarket && spreadsMarket.outcomes.length === 2) {
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
    games.forEach(game => {
        const fanduel = getFanDuelBookmaker(game);
        if (!fanduel) return;
        const home = game.home_team;
        const away = game.away_team;
        const abbr = `${TEAM_ABBR[away] || away}/${TEAM_ABBR[home] || home}`;
        const totalsMarket = fanduel.markets?.find(m => m.key === 'totals');
        if (totalsMarket) {
            totalsMarket.outcomes.forEach(outcome => {
                if (outcome.name === 'Over') overs.push({ label: `Over ${outcome.point} (${abbr})`, value: `Over ${outcome.point} (${abbr})` });
                if (outcome.name === 'Under') unders.push({ label: `Under ${outcome.point} (${abbr})`, value: `Under ${outcome.point} (${abbr})` });
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
    // Get all unique team abbreviations for the week
    const abbrs = new Set();
    games.forEach(game => {
        abbrs.add(TEAM_ABBR[game.home_team] || game.home_team);
        abbrs.add(TEAM_ABBR[game.away_team] || game.away_team);
    });
    const abbrList = Array.from(abbrs);
    if (abbrList.length === 0) return [];
    const res = await fetch(`/api/starters?teams=${abbrList.join(',')}`);
    if (!res.ok) return [];
    const players = await res.json();
    // Format as 'Player Name (TEAM_ABBR) - POS'
    return players.map(p => ({
        label: `${p.name} (${p.team}) - ${p.pos}`,
        value: `${p.name} (${p.team})`
    }));
}

async function renderPicksTableWithOptions() {
    const weekKey = getCurrentWeekKey();
    const gamesRes = await fetch(`/api/games?week=${weekSelector.value}`);
    const games = gamesRes.ok ? await gamesRes.json() : [];
    const picks = await fetchPicksForWeek(weekKey);
    const moneylineOptions = getMoneylineOptions(games);
    const { favorites, underdogs } = getFavoriteUnderdogOptions(games);
    const { overs, unders } = getOverUnderOptions(games);
    const tdOptions = await getTouchdownScorerOptions(games);

    let html = '<h2>Picks</h2>';
    html += '<table id="picks-table"><thead><tr><th>Player</th>';
    CATEGORIES.forEach(cat => {
        html += `<th>${cat}</th>`;
    });
    html += '</tr></thead><tbody>';
    PLAYERS.forEach(player => {
        html += `<tr><td>${player}</td>`;
        CATEGORIES.forEach(cat => {
            let options = [];
            if (cat === "Moneyline") options = moneylineOptions;
            else if (cat === "Favorite") options = favorites.map(f => ({ label: `${f.name} (${f.spread > 0 ? '+' : ''}${f.spread})`, value: f.name }));
            else if (cat === "Underdog") options = underdogs.map(u => ({ label: `${u.name} (${u.spread > 0 ? '+' : ''}${u.spread})`, value: u.name }));
            else if (cat === "Over") options = overs;
            else if (cat === "Under") options = unders;
            else if (cat === "Touchdown Scorer") options = tdOptions;
            // Disable options already picked by others for this category
            const taken = new Set();
            Object.entries(picks).forEach(([otherPlayer, cats]) => {
                if (otherPlayer !== player && cats[cat]) taken.add(cats[cat]);
            });
            const currentPick = picks[player]?.[cat] || "";
            html += `<td>`;
            html += `<select class="pick-dropdown" data-player="${player}" data-category="${cat}">`;
            html += `<option value="">-- Select --</option>`;
            options.forEach(opt => {
                const disabled = taken.has(opt.value) ? 'disabled' : '';
                const selected = currentPick === opt.value ? 'selected' : '';
                html += `<option value="${opt.value}" ${disabled} ${selected}>${opt.label}</option>`;
            });
            html += `</select> <button class="save-pick" data-player="${player}" data-category="${cat}">Save</button>`;
            html += `</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    // Insert after games list
    let picksSection = document.getElementById('picks-section');
    if (!picksSection) {
        picksSection = document.createElement('section');
        picksSection.id = 'picks-section';
        gamesList.parentNode.insertBefore(picksSection, gamesList.nextSibling);
    }
    picksSection.innerHTML = html;

    // Add event listeners for Save buttons
    document.querySelectorAll('.save-pick').forEach(btn => {
        btn.onclick = async function() {
            const player = btn.getAttribute('data-player');
            const category = btn.getAttribute('data-category');
            const select = document.querySelector(`select.pick-dropdown[data-player="${player}"][data-category="${category}"]`);
            const value = select.value;
            if (!value) return alert('Please select a pick.');
            await fetch('/api/picks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    week: weekKey,
                    player,
                    category,
                    value
                })
            });
            renderPicksTableWithOptions();
        };
    });
}

// Replace old renderPicksTable with new one
function onWeekChange() {
    fetchGamesForWeek(weekSelector.value);
    renderPicksTableWithOptions();
}

document.addEventListener('DOMContentLoaded', () => {
    populateWeekSelector();
    fetchGamesForWeek(weekSelector.value);
    renderPicksTableWithOptions();
    weekSelector.addEventListener('change', onWeekChange);
}); 