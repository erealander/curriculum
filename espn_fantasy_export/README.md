# ESPN Fantasy Baseball Daily Player Log Exporter

Exports daily player-level performance data for **La Flama Blancos** (ESPN league 1600541809, team 3, season 2026) with one row per player per scoring period, validated Active/Bench classification, and derived stats (ERA, WHIP, OBP, SVHD).

---

## Security requirements — read this first

| Item | Requirement |
|------|-------------|
| `espn_s2` cookie | Never commit. Never paste into shared tools. Treat like a password. |
| `SWID` | Never commit. |
| `.env` | Listed in `.gitignore`. Keep local only. |
| Logs | The `espn_s2` value is never printed in logs. |

---

## Setup

### 1. Install dependencies

```bash
cd espn_fantasy_export
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get your ESPN cookies

1. Log into ESPN Fantasy Baseball in your browser.
2. Open **DevTools** (F12 or Cmd+Opt+I) → **Application** tab (Chrome) or **Storage** tab (Firefox).
3. Navigate to **Cookies → https://fantasy.espn.com**.
4. Copy the value of **`SWID`** (includes curly braces: `{XXXX-XXXX-…}`).
5. Copy the value of **`espn_s2`** (long alphanumeric string, ~200 chars).

### 3. Create your `.env` file

```bash
cp .env.example .env
# Edit .env and paste your SWID and espn_s2 values
```

The `.env` file is in `.gitignore` and will never be committed.

---

## Step-by-step workflow

### Step 1 — Inspect the endpoint (required first run)

```bash
python inspect_endpoint.py --scoring-period 1
```

This:
- Hits the ESPN API for scoring period 1
- Prints all lineup slot IDs found and their ESPN classifications
- Lists all stat IDs present and maps them to known names
- Checks IP format (baseball notation vs decimal)
- Saves raw JSON to `outputs/endpoint_sample.json`
- Saves settings to `outputs/settings_sample.json`

**Validate the slot mapping** by opening the ESPN box-score URL that the script prints and comparing each player's row to the slot IDs. This is the critical Active/Bench validation step.

### Step 2 — Fill in manual validation examples

Edit `manual_validation_examples.csv` with 3–5 known player/status examples from the ESPN UI:

```csv
scoringPeriodId,playerName,expected_status
1,Yordan Alvarez,Active
1,Jose Abreu,Bench
5,Sandy Alcantara,Active
```

### Step 3 — Run the full export

```bash
# Full export (scoring periods 1 → auto-detected current period)
python pull_espn_daily_logs.py

# With manual validation
python pull_espn_daily_logs.py --validate-manual manual_validation_examples.csv

# Active roster rows only
python pull_espn_daily_logs.py --active-only

# Include raw ESPN stat blobs for debugging
python pull_espn_daily_logs.py --include-raw-json

# Specific range
python pull_espn_daily_logs.py --start-scoring-period 1 --end-scoring-period 54
```

### Step 4 — Review output files

| File | Description |
|------|-------------|
| `outputs/la_flama_blancos_daily_player_logs_2026.csv` | Main export — one row per player per scoring period |
| `outputs/la_flama_blancos_daily_player_logs_2026.xlsx` | Same data as Excel |
| `outputs/slot_mapping_validation.csv` | Every lineup slot ID seen, its assigned classification, and manual validation results |
| `outputs/parse_warnings.csv` | Any rows that had parsing errors, unknown stat IDs, or unknown slot classifications |
| `outputs/endpoint_sample.json` | Raw ESPN API response (first scoring period fetched) |
| `outputs/settings_sample.json` | Raw ESPN league settings |
| `outputs/export_run.log` | Full run log |

---

## How Active vs Bench is determined

### The slot mapping mechanism

ESPN returns a `lineupSlotId` integer for every roster entry in the box-score response. The classification logic is:

1. **Settings lookup**: `inspect_endpoint.py` fetches `view=mSettings`, which contains `positionSlots` — a list of slot definitions including `id` and `defaultDisplay` (e.g. "BE", "SP", "OF").
2. **Name-based classification**: Any slot whose name matches known active prefixes (`C`, `1B`, `2B`, `3B`, `SS`, `OF`, `UTIL`, `SP`, `RP`) is marked `Active`. Slots named `BE` or `BENCH` are marked `Bench`. Slots named `IL`, `IR`, or `NA` are marked `IL`.
3. **ID-based fallback**: If the name cannot be resolved, known ESPN baseball slot IDs are used (13, 16–20 = Bench; 14, 15, 21 = IL; 0–12 = Active).
4. **Unknown escalation**: If a slot cannot be classified by name or ID, the row is marked `Unknown` and a warning is written to `parse_warnings.csv`.

### Validation

- `outputs/slot_mapping_validation.csv` shows every distinct slot ID seen across all scoring periods, with its assigned classification and an example player.
- `--validate-manual manual_validation_examples.csv` compares API-derived statuses against known ground-truth examples. The script **fails loudly** if any example mismatches.
- The ESPN box-score URL printed by `inspect_endpoint.py` lets you open the actual UI for that date and visually confirm which players are active vs bench.

### Common ESPN Baseball slot IDs (default fallback)

| Slot ID | Name | Status |
|---------|------|--------|
| 0 | C | Active |
| 1 | 1B | Active |
| 2 | 2B | Active |
| 3 | 3B | Active |
| 4 | SS | Active |
| 5–7 | OF | Active |
| 8 | UTIL | Active |
| 9–10 | SP | Active |
| 11–12 | RP | Active |
| 13 | BE | **Bench** |
| 14 | IL | **IL** |
| 15 | NA | **IL** |

These are loaded dynamically from `mSettings` at runtime. The table above is the hardcoded fallback only.

---

## Output column reference

### Identity columns

| Column | Description |
|--------|-------------|
| `scoringPeriodId` | ESPN scoring period number (1 = first day/week of season) |
| `matchupPeriodId` | Fantasy week / matchup number |
| `fantasyTeamId` | ESPN team ID (3 for La Flama Blancos) |
| `fantasyTeamName` | Team name |
| `playerId` | ESPN player ID |
| `playerName` | Full player name |
| `proTeamId` | ESPN MLB team ID |
| `defaultPositionId` | Player's default position ID |
| `eligibleSlots` | JSON list of eligible lineup slot IDs |

### Slot / Active-Bench columns

| Column | Description |
|--------|-------------|
| `fantasy_slot_id` | Raw ESPN `lineupSlotId` integer |
| `fantasy_slot_name` | Mapped slot name (e.g. "SP", "BE") |
| `raw_espn_slot_value` | Same as fantasy_slot_id (for cross-reference) |
| `active_status` | `Active` / `Bench` / `IL` / `Unknown` |

### Batting columns

`AB`, `H`, `R`, `HR`, `RBI`, `BB`, `HBP`, `SF`, `SB`, `OBP_espn`, `OBP_calc`, `AVG`, `SLG`, `OPS`, `TB`, `PA`, `2B`, `3B`, `IBB`, `SO_bat`, `XBH`, `GIDP`, `CS`

### Pitching columns

`IP_raw`, `IP_decimal`, `H_allowed`, `BB_allowed`, `ER`, `K`, `QS`, `W`, `L`, `SV`, `HLD`, `SVHD_espn`, `SVHD_calc`, `ERA_espn`, `ERA_calc`, `WHIP_espn`, `WHIP_calc`, `BS`, `CG`, `HR_allowed`, `R_allowed`, `K9`, `GS_p`, `GP_p`

### Derived fields

| Field | Formula | Notes |
|-------|---------|-------|
| `ERA_calc` | `ER × 9 / IP_decimal` | Only calculated when IP > 0 |
| `WHIP_calc` | `(H_allowed + BB_allowed) / IP_decimal` | Only when IP > 0 |
| `OBP_calc` | `(H + BB + HBP) / (AB + BB + HBP + SF)` | Only when all inputs non-null |
| `SVHD_calc` | `SV + HLD` | Only when both SV and HLD are non-null |

ESPN sometimes provides ERA, WHIP, OBP directly (stored in `_espn` columns). Calculated versions are always in `_calc` columns. Use whichever is available and non-null.

---

## IP innings notation

ESPN may return IP in baseball notation:
- `5.1` = 5⅓ innings (5 innings + 1 out), converted to `5.3333`  
- `5.2` = 5⅔ innings (5 innings + 2 outs), converted to `5.6667`
- `6.0` = 6 full innings

`inspect_endpoint.py` detects and reports which format ESPN is using for your league. The `IP_raw` column stores ESPN's original value; `IP_decimal` stores the converted true decimal used for ERA/WHIP calculations.

---

## Stat ID mapping

ESPN returns stats as a JSON object with numeric keys (e.g. `{"0": 4, "5": 1}`). The key-to-column mapping is in `STAT_ID_MAP` in `pull_espn_daily_logs.py`. Any stat ID not in the map will:
- Appear in `raw_stats_json` (if `--include-raw-json` is used)
- Generate an entry in `parse_warnings.csv`

**Confidence levels** are noted in comments in `STAT_ID_MAP`. Run `inspect_endpoint.py` and compare the printed stat IDs against your ESPN league scoring categories to validate.

Key stat IDs for this league's scoring categories:

| Scoring category | Stat ID | Column | Confidence |
|-----------------|---------|--------|------------|
| R | 6 | `R` | HIGH |
| HR | 5 | `HR` | HIGH |
| RBI | 8 | `RBI` | HIGH |
| SB | 11 | `SB` | HIGH |
| OBP | 17 | `OBP_espn` | HIGH |
| K | 30 | `K` | HIGH |
| QS | 47 | `QS` | HIGH |
| ERA | 48 | `ERA_espn` | HIGH |
| WHIP | 49 | `WHIP_espn` | HIGH |
| SVHD | 113 | `SVHD_espn` | LOW — verify |

---

## Troubleshooting

### ESPN 401 Unauthorized
Your `espn_s2` cookie has expired. Re-copy it from browser DevTools. ESPN cookies expire after a few weeks.

### ESPN 403 Forbidden
- Your league may be set to private and ESPN is not accepting your credentials.
- Verify that `ESPN_LEAGUE_ID` and `ESPN_TEAM_ID` match your league.
- Make sure you are logged into the same ESPN account that manages this league.

### Wrong teamId
Run `inspect_endpoint.py` with the correct credentials. The script prints all `teamId` values in the schedule so you can find yours. Common issue: ESPN sometimes re-numbers teams across seasons.

### Missing rows for a scoring period
- Some scoring periods may fall on off-days (no games).
- Early scoring periods before the season started return empty schedules.
- Check `outputs/parse_warnings.csv` for specific periods.

### Unexpected stat IDs
Run with `--include-raw-json` and open `outputs/endpoint_sample.json`. Search for the raw stat IDs and compare values against the ESPN box-score UI. Then add the mapping to `STAT_ID_MAP`.

### Wrong Active/Bench classification
1. Run `inspect_endpoint.py --scoring-period <N>` and check the slot table.
2. Open the ESPN box-score URL it prints.
3. If a slot ID is misclassified, update `DEFAULT_SLOT_MAP` and `classify_slot()` in `pull_espn_daily_logs.py`.
4. Add the known ground-truth example to `manual_validation_examples.csv` and rerun with `--validate-manual`.

### IP values look wrong for ERA/WHIP
Check `IP_raw` vs `IP_decimal` in the output. If ESPN is already returning decimal IP, set `ip_to_decimal` to return the value unchanged (the function detects this automatically for values with fractional part > 0.25). See the IP format check section in `inspect_endpoint.py` output.

### Private league access issues
ESPN fantasy leagues must be set to viewable by authenticated users. Log into ESPN in your browser, navigate to your league, and confirm you can see box scores. If the league is set to "Private", even valid credentials may not suffice for API access — you may need to adjust league privacy settings.

---

## Re-running as the season progresses

The script supports incremental updates. To pull only new scoring periods:

```bash
# Check what the last exported scoringPeriodId was
tail -n 5 outputs/la_flama_blancos_daily_player_logs_2026.csv | cut -d, -f1

# Run from where you left off
python pull_espn_daily_logs.py --start-scoring-period <last+1> --end-scoring-period auto
```

Or just re-run the full export — it overwrites the output files with fresh data.

---

## League context

- **Platform**: ESPN Fantasy Baseball
- **League ID**: 1600541809
- **Season**: 2026
- **Team**: La Flama Blancos (manager: Ethan Realander, teamId: 3)
- **Scoring categories — Batting**: R, HR, RBI, SB, OBP
- **Scoring categories — Pitching**: K, QS, ERA, WHIP, SVHD
