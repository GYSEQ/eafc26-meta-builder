# EA FC 26 Squad Builder

An advanced squad optimization tool for EA Sports FC 26 Ultimate Team that uses constraint programming to build optimal squads based on metaratings, chemistry, and budget constraints.

## Features

- **Smart Player Data Collection**: Scrapes player data and metaratings from fut.gg API
- **Owned Player Tracking**: Chrome userscript + Flask API to track your club
- **Chemistry System**: Full EA FC 26 squad-threshold chemistry implementation
- **CP-SAT Optimization**: Uses Google OR-Tools for constraint programming with chemistry as a hard constraint
- **Performance Tuning**: Configurable candidate limits and minimum metarating filters

## Architecture

The application consists of three independent components:

```
┌─────────────────┐
│   fut.gg API    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│    Scraper      │─────▶│    MongoDB       │
└─────────────────┘      │  - players       │
                         │  - my_club       │
┌─────────────────┐      │                  │
│  EA FC Web App  │      └────────┬─────────┘
└────────┬────────┘               │
         │                        │
         ▼                        │
┌─────────────────┐               │
│  Userscript +   │───────────────┘
│   Flask API     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Squad Optimizer │
│   (CP-SAT)      │
└─────────────────┘
```

## Technology Stack

- **Python 3.10+** - Core application
- **MongoDB** - Document database for player data
- **Google OR-Tools** - Constraint Programming (CP-SAT solver)
- **Flask** - REST API for userscript communication
- **Cloudscraper** - API client with Cloudflare bypass
- **JavaScript** - Chrome userscript for web app integration

## Installation

### Prerequisites

1. **Python 3.10 or higher**
   ```bash
   python --version
   ```

2. **MongoDB**
   - **Option A**: Local installation
     - Download [MongoDB Community Edition](https://www.mongodb.com/try/download/community)
     - Start MongoDB service: `mongod`
   - **Option B**: MongoDB Atlas (cloud)
     - Create free account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
     - Get connection string

3. **Chrome Browser + Tampermonkey Extension**
   - Install [Tampermonkey](https://www.tampermonkey.net/)

### Setup Steps

1. **Clone or download the repository**

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   # Copy example environment file
   copy .env.example .env

   # Edit .env with your settings
   notepad .env
   ```

   Example `.env` file:
   ```env
   MONGODB_URI=mongodb://localhost:27017/
   MONGODB_DB_NAME=fut_builder
   FUTGG_API_BASE=https://www.fut.gg/api/fut
   FLASK_HOST=localhost
   FLASK_PORT=5000
   ```

4. **Verify installation**
   ```bash
   python -m config.database
   ```

## Quick Start

### Step 1: Scrape Player Data

Collect player data from fut.gg:

```bash
# Test with 5 pages (fast, ~2 minutes)
python -m scraper.main --max-pages 5

# Full scrape (all players, ~30-40 minutes)
python -m scraper.main
```

The scraper will:
- Fetch all players with their attributes
- Collect metaratings for each position
- Store data in MongoDB with proper indexing

**Progress output:**
```
Starting fut.gg player scraper...
Fetching page 1...
  Found 50 players
  Fetching metaratings in bulk...
  Upserting 50 players to database
Fetching page 2...
...
```

### Step 2: Track Your Owned Players (Optional)

If you want to build squads using only your owned players:

1. **Start the Flask API**
   ```bash
   python -m userscript_api.app
   ```

2. **Install the userscript**
   - Open Tampermonkey dashboard
   - Click "Create a new script"
   - Copy contents from `userscripts/ea_fc_club_scraper.user.js`
   - Save

3. **Scrape your club**
   - Navigate to [EA FC Web App](https://www.ea.com/fifa/ultimate-team/web-app/)
   - Go to your club
   - Click the "Scrape EA FC Club" button that appears
   - Navigate through your club pages
   - Check console for progress

4. **Verify**
   ```bash
   # Check how many players were tracked
   curl http://localhost:5000/api/my-club/stats
   ```

### Step 3: Build Optimal Squads

Build squads using the optimizer:

```bash
# Basic 4-3-3 squad with 100k budget
python -m optimizer.main \
  --positions "GK,RB,CB,CB,LB,CDM,CDM,CAM,RM,ST,LM" \
  --budget 100000 \
  --min-chemistry 25

# Use only owned players
python -m optimizer.main \
  --positions "GK,RB,CB,CB,LB,CDM,CDM,CAM,RM,ST,LM" \
  --budget 0 \
  --owned-only \
  --min-chemistry 20

# Fast optimization with filters
python -m optimizer.main \
  --positions "GK,RB,CB,CB,LB,CDM,CDM,CAM,RM,ST,LM" \
  --budget 500000 \
  --min-chemistry 30 \
  --candidate-limit 50 \
  --min-metarating 75
```

## Usage Guide

### Optimizer CLI Reference

```bash
python -m optimizer.main [OPTIONS]
```

#### Required Arguments

- `--positions` "GK,RB,CB,CB,LB,CDM,CDM,CAM,RM,ST,LM"
- `--budget` - Maximum budget in coins

#### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--min-chemistry` | 20 | Minimum squad chemistry (0-33) |
| `--owned-only` | False | Only use owned players |
| `--candidate-limit` | 100 | Max candidates per position |
| `--min-metarating` | 0.0 | Minimum metarating filter |
| `--timeout` | 300 | Solver timeout in seconds |

#### Performance Tuning

**For faster results** (with quality tradeoff):
```bash
--candidate-limit 50 --min-metarating 75
```

**For best quality** (slower):
```bash
--candidate-limit 200 --min-metarating 0
```

**Balanced approach**:
```bash
--candidate-limit 100 --min-metarating 70
```

### Available Formations

The following formations are currently supported:

- **4-3-3 (4)** - Classic 4-3-3 with attacking midfielders
- **4-4-2** - Traditional two strikers
- **4-2-3-1 (2)** - Modern defensive formation

> **Note**: Additional formations can be added by creating formation documents in the `formations` MongoDB collection with position coordinates and adjacency maps.

### Output Example

```
Starting CP-SAT optimization with HARD chemistry constraint...
  Positions: GK, RB, CB, CB, LB, CDM, CM, CAM, RW, ST, LW
  Budget: 100,000
  Min Chemistry: 25 (HARD CONSTRAINT)
  Owned Only: False
  Candidate Limit: 100 per position
  Min Metarating: 70.0
  Timeout: 300s

Owned players in database: 217

Fetching candidates...
  Position 1 (GK): 100 candidates
  Position 2 (RB): 100 candidates
  ...

Total decision variables: 1100

Building CP-SAT model with chemistry as HARD constraint...
  Creating decision variables...
  Decision variables: 1100
  Basic constraints added
  Building chemistry constraints...
    Unique clubs: 145, leagues: 28, nations: 52
    HARD constraint: total_chemistry >= 25
  Chemistry constraints added

Solving with CP-SAT...
  This may take up to 300s for complex chemistry constraints...

Solver finished!
  Status: OPTIMAL
  Wall time: 2.87s

╔════════════════════════════════════════════════════════════════╗
║                      OPTIMIZATION RESULT                        ║
╠════════════════════════════════════════════════════════════════╣
║ Status:          OPTIMAL                                        ║
║ Formation:       4-2-3-1 (2)                                    ║
║ Total Cost:      95,450                                         ║
║ Metarating:      82.3                                           ║
║ Chemistry:       33/33 ⚡                                        ║
║ Owned Players:   7/11                                           ║
║ Solve Time:      2.87s                                          ║
╚════════════════════════════════════════════════════════════════╝

Squad Details:
╭──────┬──────┬─────────────────────┬──────┬──────┬──────┬──────────╮
│ Slot │ Pos  │ Player              │ Meta │ Chem │ Cost │ Status   │
├──────┼──────┼─────────────────────┼──────┼──────┼──────┼──────────┤
│  1   │ GK   │ Alisson Becker      │ 85.2 │  3   │   0  │ OWNED ✓  │
│  2   │ RB   │ Trent Alexander     │ 83.5 │  3   │   0  │ OWNED ✓  │
│  3   │ CB   │ Virgil van Dijk     │ 86.8 │  3   │   0  │ OWNED ✓  │
│  4   │ CB   │ Ibrahima Konaté     │ 81.2 │  3   │   0  │ OWNED ✓  │
│  5   │ LB   │ Andy Robertson      │ 80.9 │  3   │   0  │ OWNED ✓  │
│  6   │ CDM  │ Fabinho             │ 79.5 │  3   │   0  │ OWNED ✓  │
│  7   │ CDM  │ Declan Rice         │ 82.1 │  3   │ 45k  │ BUY      │
│  8   │ CAM  │ Martin Ødegaard     │ 84.3 │  3   │ 35k  │ BUY      │
│  9   │ RW   │ Bukayo Saka         │ 83.7 │  3   │ 15k  │ BUY      │
│ 10   │ ST   │ Darwin Núñez        │ 81.8 │  3   │   0  │ OWNED ✓  │
│ 11   │ LW   │ Luis Díaz           │ 80.3 │  3   │ 450  │ BUY      │
╰──────┴──────┴─────────────────────┴──────┴──────┴──────┴──────────╯
```

## Chemistry System

### EA FC 26 Squad-Threshold Chemistry

Unlike previous FIFA titles, EA FC uses a squad-threshold system where players earn chemistry based on how many teammates share attributes:

#### Chemistry Thresholds

| Attribute | Threshold → Chemistry |
|-----------|----------------------|
| **Club**  | 2→1, 4→2, 7→3 |
| **League** | 3→1, 5→2, 8→3 |
| **Nation** | 2→1, 5→2, 8→3 |

#### Special Rules

- **Icons**: Count double for nation thresholds (automatically get 3 chemistry)
- **Heroes**: Count double for league thresholds (automatically get 3 chemistry)
- **Individual Chemistry**: 0-3 per player (capped at 3)
- **Squad Chemistry**: Sum of all 11 players (maximum 33)

#### Example

If you have 7 players from Liverpool:
- Each Liverpool player gets **3 chemistry from club** (7 ≥ 7 threshold)
- If 8+ players are from Premier League, they also get **3 from league**
- Chemistry is capped at 3 per player max

### Chemistry as Hard Constraint

The optimizer uses **chemistry as a hard constraint**, meaning:
- Solutions are **guaranteed** to meet minimum chemistry requirement
- If no solution exists, the solver will report "INFEASIBLE"
- No soft penalties or approximations - either meets requirement or fails

## Database Schema

### Collections

#### players
Stores all player data from fut.gg.

**Key Fields**:
```javascript
{
  "ea_id": 123456,              // Unique EA player ID
  "name": "Cristiano Ronaldo",
  "club_ea_id": 243,
  "league_ea_id": 53,
  "nation_ea_id": 38,
  "market_price": 25000,        // null if extinct
  "metarating": 8.7,            // Best metarating score
  "metarating_position": "ST",  // Position for best metarating
  "is_icon": false,
  "is_hero": false
}
```

**Indexes**:
- `ea_id` (unique)
- `metarating_position` (compound with metarating)
- `club_ea_id`, `league_ea_id`, `nation_ea_id`

#### my_club
Tracks owned players.

**Schema**:
```javascript
{
  "player_ea_id": 123456  // References players.ea_id
}
```

**Indexes**:
- `player_ea_id` (unique)

#### formations
Stores formation definitions.

**Schema**:
```javascript
{
  "name": "4-3-3 (4)",
  "positions": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CM", "RW", "ST", "LW"]
}
```

## API Reference

### Flask API Endpoints

The Flask API runs on `http://localhost:5000` (configurable in `.env`).

#### POST /api/my-club
Add players to your club.

**Request**:
```json
{
  "player_ea_ids": [123456, 234567, 345678]
}
```

**Response**:
```json
{
  "success": true,
  "count": 15,
  "total_players": 217,
  "message": "Successfully processed 15 players"
}
```

#### GET /api/my-club/stats
Get club statistics.

**Response**:
```json
{
  "success": true,
  "total_players": 217
}
```

#### DELETE /api/my-club/clear
Clear all owned players (useful for testing).

**Response**:
```json
{
  "success": true,
  "deleted_count": 217,
  "message": "Deleted 217 players from your club"
}
```

#### GET /health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

## Advanced Usage

### Building Multiple Squads

Compare different formations:

```bash
# Build 4-3-3
python -m optimizer.main --formation "4-3-3 (4)" --budget 100000 --min-chemistry 25

# Build 4-4-2
python -m optimizer.main --formation "4-4-2" --budget 100000 --min-chemistry 25

# Build 4-2-3-1
python -m optimizer.main --formation "4-2-3-1 (2)" --budget 100000 --min-chemistry 25
```

### Progressive Budget Strategy

Start low and increase budget until chemistry requirement is met:

```bash
# Try 50k
python -m optimizer.main --formation "4-3-3 (4)" --budget 50000 --min-chemistry 30

# If infeasible, try 100k
python -m optimizer.main --formation "4-3-3 (4)" --budget 100000 --min-chemistry 30

# If still infeasible, try 200k
python -m optimizer.main --formation "4-3-3 (4)" --budget 200000 --min-chemistry 30
```

### Hybrid Squads

Build squads mixing owned and market players:

```bash
# Let owned players provide chemistry base, buy meta attackers
python -m optimizer.main \
  --formation "4-2-3-1 (2)" \
  --budget 150000 \
  --min-chemistry 28 \
  --min-metarating 75
```

## Troubleshooting

### Scraper Issues

**Problem**: "Connection failed" or "Cloudflare blocking"
- **Solution**: Wait a few minutes and retry. Cloudscraper should handle most blocks automatically.

**Problem**: Scraper stops early
- **Solution**: Normal - fut.gg API returns empty pages when all data is fetched.

**Problem**: Missing metaratings for some players
- **Solution**: Some players don't have metaratings yet (new cards, low-rated cards). This is expected.

### Userscript Issues

**Problem**: Button not appearing in Web App
- **Solution**:
  1. Check Tampermonkey is enabled
  2. Verify script is active for `ea.com` domain
  3. Refresh the page

**Problem**: "Failed to connect to API"
- **Solution**: Start Flask API: `python -m userscript_api.app`

**Problem**: No players scraped
- **Solution**: Navigate through your club pages after clicking the button. The script captures data as pages load.

### Optimizer Issues

**Problem**: "No eligible players found"
- **Solution**: Run the scraper first to populate the database.

**Problem**: "INFEASIBLE - No feasible solution"
- **Solutions**:
  1. Lower `--min-chemistry` requirement
  2. Increase `--budget`
  3. If using `--owned-only`, check you have enough players
  4. Try different formation

**Problem**: Solver takes too long
- **Solutions**:
  1. Reduce `--candidate-limit` (try 50)
  2. Increase `--min-metarating` (try 70-75)
  3. Reduce `--timeout` to get feasible (non-optimal) solution faster

**Problem**: Chemistry is exactly at minimum, not higher
- **Explanation**: This is expected. CP-SAT optimizes for metarating, not chemistry. It will meet the chemistry constraint exactly if that gives better metarating.

### Database Issues

**Problem**: "Connection refused" to MongoDB
- **Solution**:
  1. Check MongoDB is running: `mongod` (local) or check Atlas dashboard (cloud)
  2. Verify `MONGODB_URI` in `.env` file

**Problem**: Slow queries
- **Solution**: Indexes should be created automatically. Run any script once to ensure indexes exist.

## Performance Optimization

### Scraper Performance

- **Bulk operations**: Uses MongoDB `bulk_write` for efficiency
- **Rate limiting**: 1.5s delay between requests to avoid blocking
- **Concurrent metaratings**: Fetches metaratings in bulk (up to 100 players per request)

**Estimated times**:
- 5 pages: ~2 minutes (~250 players)
- 50 pages: ~20 minutes (~2,500 players)
- Full scrape: ~30-40 minutes (~7,000+ players)

### Optimizer Performance

The CP-SAT solver performance depends on several factors:

**Fast (< 5 seconds)**:
- `--candidate-limit 50`
- `--min-metarating 75`
- Lower `--min-chemistry` (20-25)

**Medium (5-30 seconds)**:
- `--candidate-limit 100`
- `--min-metarating 70`
- Medium `--min-chemistry` (25-30)

**Slow (30+ seconds)**:
- `--candidate-limit 200`
- `--min-metarating 0`
- High `--min-chemistry` (30-33)

**Memory usage**: ~100-500MB depending on candidate pool size

## Project Structure

```
FUT BUILDER V2/
├── config/
│   └── database.py           # MongoDB connection and indexing
├── scraper/
│   ├── futgg_service.py      # fut.gg API client
│   └── main.py               # Scraper CLI
├── optimizer/
│   ├── chemistry.py          # Chemistry calculation
│   ├── solver.py             # CP-SAT optimization
│   └── main.py               # Optimizer CLI
├── userscript_api/
│   └── app.py                # Flask API for userscript
├── userscripts/
│   └── ea_fc_club_scraper.user.js  # Chrome userscript
├── utils/
│   └── position_mappings.py  # Position ID to code mappings
├── requirements.txt          # Python dependencies
├── .env              # environment config
└── README.md                 # This file
```

## Technical Details

### Constraint Programming Model

The optimizer uses Google OR-Tools CP-SAT solver with the following model:

**Decision Variables**:
- `x[pos][player]` ∈ {0, 1} - Binary variable for each player-position pair

**Constraints**:
1. **One player per position**: `∑ x[pos][player] = 1` for each position
2. **Unique players**: Each player can only be selected once across all positions
3. **Budget**: `∑ (price[player] * x[pos][player]) ≤ budget`
4. **Chemistry** (HARD): Uses counting variables and threshold lookup tables

**Objective**:
- **Maximize**: `∑ (metarating[player] * x[pos][player])`

**Chemistry Implementation**:
- Count variables track how many players share club/league/nation
- `AddElement` constraints map counts to chemistry points via lookup tables
- Icons/Heroes handled with double-counting multipliers
- Total chemistry enforced as hard constraint: `total_chemistry ≥ min_chemistry`

### Why CP-SAT over MILP?

1. **Better logical constraints**: Chemistry thresholds are naturally expressed as logical rules
2. **Faster solving**: CP-SAT handles counting and lookup tables more efficiently
3. **Guaranteed feasibility**: Hard chemistry constraint ensures valid squads
4. **Multi-threading**: CP-SAT can use multiple CPU cores

## Future Enhancements

### Potential Features

- [ ] Web UI with interactive formation builder
- [ ] More formations (5-3-2, 3-5-2, 4-1-2-1-2, etc.)
- [ ] SBC solver for Squad Building Challenges
- [ ] Evolution card tracking
- [ ] PlayStyle/PlayStyle+ integration
- [ ] Historical price tracking
- [ ] Multi-squad builder (fitness rotation)
- [ ] Custom rating systems
- [ ] Squad export (FUTBIN, JSON, etc.)

### Algorithm Improvements

- [ ] Multi-objective optimization (chemistry + metarating)
- [ ] Iterative refinement for better solutions
- [ ] Position flexibility (automatically try alt positions)
- [ ] Chemistry prediction before solving

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## License

This project is for educational and personal use only.

**Disclaimers**:
- Not affiliated with EA Sports or fut.gg
- Use responsibly and respect API rate limits
- Web app automation may violate EA's Terms of Service

## Acknowledgments

- **fut.gg** - Player data and metaratings
- **Google OR-Tools** - Constraint programming solver
- **EA Sports** - EA FC 26 game

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Check your Python and MongoDB installations

---

**Built with ❤️ for the EA FC 26 Ultimate Team community**
