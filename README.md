# RoundSense

**Real-time Counter-Strike 2 analytics and round-outcome prediction engine.**

RoundSense ingests live CS2 Game State Integration (GSI) telemetry, computes team/player features, estimates round win probability, stores state history, and streams updates to a React dashboard over WebSockets. It also contains a machine-learning training pipeline and a starter historical-demo ingestion path using Awpy.

> Important: the repository ships with a transparent heuristic predictor so the full app works immediately. Train the ML model on real historical demo-derived data before making any performance claims. The included synthetic dataset generator is only for testing the pipeline.

## Features

- Live CS2 GSI HTTP ingestion
- FastAPI backend + WebSocket broadcasting
- CT/T round win probability
- Player impact ranking
- Economy, health, armor, utility and alive-player tracking
- Recent-round momentum using a bounded deque
- Hash-map based player lookup from GSI payloads
- Live tactical minimap with CT/T player and bomb positions
- Map-aware A/B site pressure, defender coverage, team spread and nearest-enemy analytics
- Hybrid positioning adjustment blended with the trained model in log-odds space
- Spatial player coordinates and nearest-enemy helper
- SQLite state history by default
- React/Vite live dashboard
- XGBoost or logistic-regression training script
- Awpy historical demo parsing starter
- Docker Compose setup
- GSI simulator so the project can be demoed without launching CS2
- Pytest feature/predictor tests

## Architecture

```text
CS2 Game State Integration
          |
          v
   FastAPI /gsi endpoint
          |
          v
   Feature Engine --------> SQLite state history
          |
          v
 Round Predictor
  | heuristic (default)
  | trained ML model
  | tactical positioning adjustment
          |
          v
 WebSocket broadcaster
          |
          v
    React dashboard
```

Historical model-training path:

```text
CS2 .dem files -> Awpy -> feature table -> XGBoost/logistic regression -> joblib model -> live API
```

## 1. Quick demo (Windows/macOS/Linux)

### Backend

Requires Python 3.11+.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000`

Swagger: `http://127.0.0.1:8000/docs`

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

### Generate fake live match data

In a third terminal, from the repository root:

```bash
python scripts/simulate_gsi.py
```

You should immediately see the dashboard update once per second.

### Windows one-command helpers

From PowerShell, you can also use:

```powershell
.\scripts\run_backend.ps1
.\scripts\run_frontend.ps1
.\scripts\run_simulator.ps1
```

To install the CS2 GSI config automatically:

```powershell
.\scripts\install_gsi_windows.ps1
```

## 2. Connect real CS2

Copy `config/gamestate_integration_roundsense.cfg` into the CS2 `game/csgo/cfg/` folder in your Steam installation, then restart CS2 while the backend is running.

Typical Windows Steam path:

```text
C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\cfg\
```

The config posts telemetry to:

```text
http://127.0.0.1:8000/gsi
```

Some `allplayers` information is context-dependent; observer/spectator feeds expose more complete match-wide state than a normal player perspective. For model training, historical `.dem` parsing is the better source of complete data.

## 3. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health and loaded predictor |
| POST | `/gsi` | CS2 GSI telemetry receiver |
| GET | `/api/state` | Latest normalized state |
| GET | `/api/history?limit=60` | Recent normalized states |
| GET | `/api/players` | Current players sorted by impact |
| WS | `/ws` | Live state stream for the dashboard |

## 4. Model features

The live feature vector currently contains:

- CT/T players alive
- CT/T total health
- CT/T total armor
- CT/T money
- CT/T estimated weapon equipment value
- CT/T utility count
- Bomb planted flag
- Round time remaining
- Score
- Recent CT round win rate

The exact historical training feature definition should be kept consistent with the live feature extractor.

### Tactical positioning layer

When full-team position data is available (normally observer/spectator GSI), RoundSense also calculates:

- CT and T team spread
- Distance between team centroids
- Average nearest-enemy distance
- Inferred A/B attack focus
- Number of T players pressuring the focused site
- Number of CT players covering that site
- Bomb location when GSI exposes it

The existing XGBoost model is intentionally kept compatible with the original training feature set. RoundSense converts the tactical state into a bounded **log-odds adjustment** and blends it with the model's probability. For example, if several T players are grouped around A while no CT is close enough to cover A, the positioning layer lowers CT's estimated win probability. Early-round positioning is down-weighted because site locations are less informative before an execute develops.

This is a hybrid system rather than a claim that the current XGBoost model itself learned map positioning. A future model version can train directly on the spatial features once a sufficiently large historical dataset is built.

## 5. Train the ML pipeline

### Pipeline test with synthetic data

```bash
python ml/generate_synthetic_training_data.py --rows 30000
python ml/train_model.py --model xgboost
```

Restart the backend after training. `/health` should report `trained_model`.

**Do not use synthetic-model metrics on a resume or portfolio.** They only prove the software pipeline works.

### Real historical data

Install Awpy:

```bash
pip install awpy
```

Build a training set directly from one demo or a folder of demos:

```bash
python ingestion/build_training_from_demos.py path/to/demos --sample-seconds 2
python ml/train_model.py --model xgboost
```

The extractor requests Awpy player properties for side, position, health, armor, inventory and equipment value, samples active rounds, aggregates CT/T state, attaches the round winner, and computes the score and recent-round momentum without leaking the current round outcome. `ct_money`/`t_money` are currently set to zero for historical training because cash is not guaranteed by the selected portable Awpy property set; add a cash property only after verifying it against your installed parser version. Parser schemas can change, so the script supports common Awpy 2.x round-column aliases and prints/continues past incompatible demos.

## 6. Data-structure / algorithms story

This project deliberately exposes more than a model call:

- **Hash maps**: GSI keys players by Steam ID for constant-time identity/state access.
- **Deque/sliding window**: latest round winners are stored in a bounded deque to compute short-term momentum.
- **Priority ordering**: live players are ranked by impact for top-player presentation.
- **Spatial search**: player XYZ data is retained and `nearest_enemy_distance()` provides a baseline O(n) proximity query that can later be upgraded to a KD-tree or grid index.
- **Bounded state buffer**: in-memory history is capped so long-running sessions do not grow without limit.

## 7. Suggested next upgrades

1. Build a robust Awpy-to-feature dataset extractor across hundreds of demos.
2. Add time-aware train/validation/test splits by match to prevent leakage.
3. Add calibration curves and Brier score in addition to ROC-AUC/F1.
4. Train map-specific models or include map encoding.
5. Train a second-generation model directly on team spread, site pressure, nearest-enemy and map-control features.
6. Implement a KD-tree/grid spatial index for larger spatial workloads.
7. Add grenade inventory and utility-value estimation.
8. Add clutch-state features (1vX, retake, post-plant).
9. Add feature importance / SHAP analysis.
10. Replace SQLite with PostgreSQL for deployed use.
11. Add Redis if scaling WebSocket/state workloads.
12. Add authentication before exposing an internet-facing dashboard.

## Resume-ready wording (after you have real results)

**RoundSense — Real-Time CS2 Analytics & Round Prediction Engine**  
*Python, XGBoost, FastAPI, WebSockets, SQL, React, Docker*

- Developed a real-time CS2 analytics platform that ingests live match telemetry and predicts round outcomes using a trained machine-learning classifier.
- Engineered features from player health, economy, equipment, utility, score, bomb state and recent-round momentum across **[REAL NUMBER]+** historical game-state observations.
- Built a FastAPI/WebSocket backend and React dashboard for live win probabilities, economy comparisons and player-impact rankings.
- Implemented bounded sliding-window history, player-indexed state processing and spatial-position features; achieved **[REAL ROC-AUC]** ROC-AUC with **[REAL LATENCY] ms** prediction latency.

Replace every bracketed metric with measurements from the real dataset before using the bullets.

## Project layout

```text
roundsense/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── feature_engine.py
│   │   ├── gsi.py
│   │   ├── main.py
│   │   ├── predictor.py
│   │   ├── schemas.py
│   │   └── store.py
│   └── requirements.txt
├── config/
│   └── gamestate_integration_roundsense.cfg
├── data/
│   ├── processed/
│   └── raw/
├── frontend/
├── ingestion/
│   ├── build_training_from_demos.py
│   └── demo_to_training.py
├── ml/
│   ├── generate_synthetic_training_data.py
│   └── train_model.py
├── models/
├── scripts/
│   └── simulate_gsi.py
├── tests/
├── docker-compose.yml
├── Dockerfile.backend
└── README.md
```

## License

MIT


## Radar data attribution

The dashboard uses Counter-Strike overview metadata and radar images exposed by the open-source [MurkyYT/cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons) project, which extracts current radar assets and overview data from the game depot. RoundSense stores only lightweight transform/site metadata in source and loads radar images from that repository at runtime.
