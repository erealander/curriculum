#!/usr/bin/env python3
"""
pull_espn_daily_logs.py

Exports daily player-level performance logs for an ESPN Fantasy Baseball team.
Produces one row per player per scoring period, with a validated Active/Bench
status field.

Usage:
    python pull_espn_daily_logs.py
    python pull_espn_daily_logs.py --start-scoring-period 1 --end-scoring-period auto
    python pull_espn_daily_logs.py --active-only
    python pull_espn_daily_logs.py --include-raw-json
    python pull_espn_daily_logs.py --validate-manual manual_validation_examples.csv
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / "outputs"

# ESPN moved their Fantasy Baseball API to lm-api-reads in 2024.
# The old fantasy.espn.com/apis/v3/... URL now returns HTML instead of JSON.
BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
    "/seasons/{season}/segments/0/leagues/{league_id}"
)

# ─────────────────────────────────────────────────────────────────────────────
# Slot definitions
# ─────────────────────────────────────────────────────────────────────────────

# Default fallback lineup slot names for ESPN Fantasy Baseball.
# These are loaded from mSettings at runtime and this dict is updated in-place.
# IMPORTANT: Validate these against your ESPN UI — run inspect_endpoint.py first.
DEFAULT_SLOT_MAP: dict[int, str] = {
    0:  "C",
    1:  "1B",
    2:  "2B",
    3:  "3B",
    4:  "SS",
    5:  "OF",
    6:  "OF",
    7:  "OF",
    8:  "UTIL",
    9:  "SP",
    10: "SP",
    11: "RP",
    12: "RP",
    13: "BE",
    14: "IL",
    15: "NA",
    16: "BE",
    17: "BE",
    19: "BE",
    20: "BE",
    21: "IL",
}

# Slot names that are considered Active (stats count for the week/day).
ACTIVE_SLOT_PREFIXES = ("C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP", "P")
BENCH_SLOT_SUBSTRINGS = ("BE", "BENCH")
IL_SLOT_SUBSTRINGS = ("IL", " IR", "NA")

# ─────────────────────────────────────────────────────────────────────────────
# ESPN stat ID → (column_name, description, category)
#
# Confidence:
#   HIGH  = confirmed from multiple community/API sources
#   MED   = confirmed from at least one source, plausible
#   LOW   = inferred; validate against endpoint_sample.json
#
# If ESPN returns a stat ID not in this map, it will appear in raw_stats_json
# and a parse warning will be written.
# ─────────────────────────────────────────────────────────────────────────────

STAT_ID_MAP: dict[int, tuple[str, str, str]] = {
    # ── Batting (HIGH confidence) ─────────────────────────────────────────────
    0:  ("AB",          "At Bats",                         "batting"),
    1:  ("H",           "Hits",                            "batting"),
    2:  ("AVG",         "Batting Average",                 "batting"),
    3:  ("2B",          "Doubles",                         "batting"),
    4:  ("3B",          "Triples",                         "batting"),
    5:  ("HR",          "Home Runs",                       "batting"),
    6:  ("R",           "Runs",                            "batting"),
    8:  ("RBI",         "Runs Batted In",                  "batting"),
    10: ("CS",          "Caught Stealing",                 "batting"),
    11: ("SB",          "Stolen Bases",                    "batting"),
    13: ("BB",          "Walks (batting)",                 "batting"),
    14: ("IBB",         "Intentional Walks",               "batting"),
    15: ("SO_bat",      "Strikeouts (batter)",             "batting"),
    16: ("PA",          "Plate Appearances",               "batting"),
    17: ("OBP",         "On-Base Percentage (ESPN)",       "batting"),
    18: ("SLG",         "Slugging Percentage",             "batting"),
    19: ("OPS",         "On-Base Plus Slugging",           "batting"),
    20: ("TB",          "Total Bases",                     "batting"),
    21: ("XBH",         "Extra Base Hits",                 "batting"),
    22: ("HBP",         "Hit By Pitch",                    "batting"),
    23: ("GIDP",        "Grounded Into Double Play",       "batting"),
    24: ("SF",          "Sacrifice Fly",                   "batting"),
    25: ("SH",          "Sacrifice Hit",                   "batting"),
    # ── Pitching (HIGH confidence) ────────────────────────────────────────────
    26: ("IP",          "Innings Pitched",                 "pitching"),
    27: ("H_allowed",   "Hits Allowed (pitching)",         "pitching"),
    28: ("ER",          "Earned Runs",                     "pitching"),
    29: ("BB_allowed",  "Walks Allowed (pitching)",        "pitching"),
    30: ("K",           "Strikeouts (pitcher)",            "pitching"),
    31: ("R_allowed",   "Runs Allowed",                    "pitching"),
    32: ("HR_allowed",  "Home Runs Allowed",               "pitching"),
    33: ("W",           "Wins",                            "pitching"),
    34: ("L",           "Losses",                          "pitching"),
    35: ("SV_35",       "Saves (alt id 35?)",              "pitching"),   # LOW
    36: ("BS",          "Blown Saves",                     "pitching"),
    37: ("HLD",         "Holds",                           "pitching"),   # MED
    40: ("CG",          "Complete Games",                  "pitching"),
    41: ("SV",          "Saves",                           "pitching"),   # MED
    42: ("SV2",         "Saves (alt id 42?)",              "pitching"),   # LOW
    45: ("BS2",         "Blown Saves (alt id 45?)",        "pitching"),   # LOW
    47: ("QS",          "Quality Starts",                  "pitching"),   # HIGH
    48: ("ERA_espn",    "ERA (from ESPN)",                 "pitching"),
    49: ("WHIP_espn",   "WHIP (from ESPN)",                "pitching"),
    50: ("K9",          "Strikeouts per 9 IP",             "pitching"),
    53: ("KBB",         "K/BB Ratio",                      "pitching"),
    57: ("GS_p",        "Games Started (pitcher)",         "pitching"),
    59: ("GP_p",        "Games Pitched",                   "pitching"),
    63: ("SV_63",       "Saves (alt id 63?)",              "pitching"),   # LOW
    72: ("HLD_72",      "Holds (alt id 72?)",              "pitching"),   # LOW
    113: ("SVHD_espn",  "Saves+Holds (from ESPN)",         "pitching"),   # LOW
}

# ─────────────────────────────────────────────────────────────────────────────
# IP handling
# ─────────────────────────────────────────────────────────────────────────────

def ip_to_decimal(ip_value: float) -> float:
    """
    Convert innings pitched to a true decimal.

    ESPN Fantasy Baseball sometimes returns IP in baseball notation where the
    digit after the decimal indicates outs (not tenths):
        5.1 → 5⅓ innings → 5.3333
        5.2 → 5⅔ innings → 5.6667
        6.0 → 6 full innings → 6.0

    If ESPN already returns true decimal (5.333…), this function leaves it
    unchanged (fractional part > 0.25 → treated as decimal already).

    Check outputs/endpoint_sample.json under stat ID 26 to verify which
    format your league uses.
    """
    if ip_value is None or ip_value == 0:
        return 0.0
    whole = int(ip_value)
    frac = round(ip_value - whole, 6)
    if frac == 0:
        return float(whole)
    if frac <= 0.25:
        # Baseball notation: .1 = 1 out = 1/3 inning, .2 = 2 outs = 2/3 inning
        outs = round(frac * 10)
        return whole + outs / 3.0
    # Already a true decimal (ESPN pre-converted it)
    return ip_value


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Return numerator/denominator, or None if denominator is zero/None."""
    if denominator is None or denominator == 0 or numerator is None:
        return None
    return numerator / denominator


# ─────────────────────────────────────────────────────────────────────────────
# Slot classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_slot(slot_name: str, slot_id: int | None = None) -> str:
    """
    Return 'Active', 'Bench', 'IL', or 'Unknown' for a lineup slot.

    Does NOT silently guess. If a slot cannot be classified, returns 'Unknown'
    so the user can investigate and update the mapping.
    """
    name = slot_name.upper().strip()
    if any(sub in name for sub in BENCH_SLOT_SUBSTRINGS):
        return "Bench"
    if any(sub in name for sub in IL_SLOT_SUBSTRINGS):
        return "IL"
    if any(name.startswith(p) for p in ACTIVE_SLOT_PREFIXES):
        return "Active"
    # Fallback: known ESPN bench/IL slot IDs
    if slot_id is not None:
        if slot_id in (13, 16, 17, 19, 20):
            return "Bench"
        if slot_id in (14, 15, 21):
            return "IL"
        # IDs 0–12 are typically active positions in standard ESPN baseball
        if 0 <= slot_id <= 12:
            return "Active"
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Authentication / session
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load credentials and league info from .env or environment."""
    load_dotenv()
    required = ["ESPN_SWID", "ESPN_S2", "ESPN_LEAGUE_ID", "ESPN_SEASON_ID", "ESPN_TEAM_ID"]
    config = {}
    missing = []
    for key in required:
        val = os.environ.get(key)
        if not val:
            missing.append(key)
        config[key] = val
    if missing:
        logging.error("Missing required environment variables: %s", missing)
        logging.error("Copy .env.example → .env and fill in your ESPN credentials.")
        sys.exit(1)
    return config


def build_session(swid: str, espn_s2: str) -> requests.Session:
    """Return an authenticated requests.Session."""
    session = requests.Session()
    session.cookies.set("SWID", swid)
    session.cookies.set("espn_s2", espn_s2)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://fantasy.espn.com/baseball/",
        "x-fantasy-source": "kona",
        "x-fantasy-platform": "kona-PROD",
    })
    return session


def fetch_json(
    session: requests.Session,
    url: str,
    params: dict,
    retries: int = 2,
) -> dict | None:
    """GET the ESPN endpoint; retry on transient errors. Returns JSON or None."""
    for attempt in range(1 + retries):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            logging.warning("Request error (attempt %d): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return None

        if resp.status_code == 401:
            logging.error(
                "ESPN 401 Unauthorized. SWID/espn_s2 cookies are expired or wrong. "
                "Re-copy from your browser DevTools → Cookies."
            )
            return None
        if resp.status_code == 403:
            logging.error(
                "ESPN 403 Forbidden for league %s. Private league? Check teamId and authentication.",
                params.get("leagueId", "?"),
            )
            return None
        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            logging.warning("ESPN rate-limited (429). Waiting %ds…", wait)
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            logging.warning("ESPN HTTP %d for params %s", resp.status_code, params)
            return None

        try:
            return resp.json()
        except ValueError:
            logging.warning("Non-JSON response for params %s: %.200s", params, resp.text)
            return None

    return None


# ─────────────────────────────────────────────────────────────────────────────
# League settings
# ─────────────────────────────────────────────────────────────────────────────

def load_league_settings(
    session: requests.Session,
    base_url: str,
) -> dict:
    """
    Fetch mSettings and mSchedule to learn:
      - slot ID → slot name mapping
      - scoring periods per matchup period (to build the SP→MP map)
      - current / final scoring period
    Returns a dict with keys: slot_map, scoring_period_to_matchup, current_scoring_period.
    """
    result: dict = {
        "slot_map": dict(DEFAULT_SLOT_MAP),
        "scoring_period_to_matchup": {},
        "current_scoring_period": None,
        "final_scoring_period": None,
    }

    logging.info("Fetching mSettings…")
    data = fetch_json(session, base_url, {"view": "mSettings"})
    if not data:
        logging.warning("Could not fetch mSettings; using fallback slot map.")
        return result

    settings = data.get("settings", {})
    status = data.get("status", {})

    # Current / final scoring period from status
    result["current_scoring_period"] = (
        status.get("currentScoringPeriod")
        or status.get("latestScoringPeriod")
    )
    result["final_scoring_period"] = (
        status.get("finalScoringPeriod")
        or status.get("latestScoringPeriod")
    )
    logging.info(
        "League status: currentScoringPeriod=%s, finalScoringPeriod=%s",
        result["current_scoring_period"],
        result["final_scoring_period"],
    )

    # Slot name map — start from DEFAULT_SLOT_MAP and update with any names ESPN provides.
    # ESPN settings rarely include readable names for baseball leagues; the default map
    # is more reliable than relying solely on the API response.
    pos_slots = (
        settings.get("positionSlots")
        or settings.get("rosterSettings", {}).get("positionSlots")
        or []
    )
    if pos_slots:
        names_added = 0
        for slot in pos_slots:
            sid = slot.get("slotCategoryId") or slot.get("id")
            name = (
                slot.get("defaultDisplay")
                or slot.get("abbrev")
                or slot.get("name")
            )
            # Only overwrite if ESPN actually provided a real name
            if sid is not None and name:
                result["slot_map"][int(sid)] = name
                names_added += 1
        logging.info("Updated slot map with %d real names from mSettings.", names_added)
    else:
        logging.warning(
            "mSettings did not contain positionSlots. Using DEFAULT_SLOT_MAP. "
            "Run inspect_endpoint.py to validate."
        )
    # Add any new slot IDs from lineupSlotCounts not already in the map
    slot_counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {})
    for sid_str in slot_counts:
        sid = int(sid_str)
        if sid not in result["slot_map"]:
            result["slot_map"][sid] = f"slot_{sid}"

    # Schedule (to map scoringPeriodId → matchupPeriodId)
    logging.info("Fetching schedule for SP→matchup period map…")
    sched_data = fetch_json(session, base_url, {"view": "mSchedule"})
    if sched_data:
        for matchup in sched_data.get("schedule", []):
            mp = matchup.get("matchupPeriodId")
            # Scoring periods that belong to this matchup period
            for sp in matchup.get("scoringPeriodIds", []):
                result["scoring_period_to_matchup"][int(sp)] = int(mp)
            # Some response shapes embed it directly
            sp_direct = matchup.get("scoringPeriodId")
            if sp_direct is not None and mp is not None:
                result["scoring_period_to_matchup"][int(sp_direct)] = int(mp)

    if result["scoring_period_to_matchup"]:
        logging.info(
            "SP→matchup map has %d entries (sp 1 → mp %s)",
            len(result["scoring_period_to_matchup"]),
            result["scoring_period_to_matchup"].get(1, "?"),
        )
    else:
        logging.warning(
            "Could not build SP→matchup map from mSchedule. "
            "matchupPeriodId will be derived from boxscore responses."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Box-score fetching and parsing
# ─────────────────────────────────────────────────────────────────────────────

def fetch_boxscore(
    session: requests.Session,
    base_url: str,
    scoring_period: int,
) -> dict | None:
    """Fetch the mBoxscore view for a specific scoring period."""
    return fetch_json(
        session,
        base_url,
        {"view": "mBoxscore", "scoringPeriodId": scoring_period},
    )


def fetch_player_stats_kona(
    session: requests.Session,
    base_url: str,
    scoring_period: int,
    player_ids: list[int],
) -> dict[int, list[dict]]:
    """
    Fetch per-player per-scoring-period stats via ESPN's kona_player_info view.

    The mBoxscore view returns lineup slots but not stats. The kona_player_info
    view with an x-fantasy-filter header returns per-player stat blocks for a
    specific scoring period. Returns {player_id: [stat_block, ...]} for each
    player found.

    Tries two filter variants: with filterStatsForCurrentSeasonScoringPeriodId
    first (returns only stats for the requested period), then without it (returns
    all stat blocks so the caller can filter by scoringPeriodId locally). ESPN
    sometimes omits stats with the period filter for historical scoring periods.
    """
    if not player_ids:
        return {}

    season_str = base_url.split("/seasons/")[1].split("/")[0] if "/seasons/" in base_url else "2026"

    filter_variants = [
        # Variant 1: ESPN-side period filter (preferred; may return empty for historical periods)
        {
            "players": {
                "filterStatsForCurrentSeasonScoringPeriodId": {"value": [scoring_period]},
                "filterIds": {"value": player_ids},
                "limit": len(player_ids) + 5,
                "sortAppliedStatTotal": {
                    "sortPriority": 1,
                    "value": f"00{season_str}{scoring_period:03d}",
                },
            }
        },
        # Variant 2: No period filter; ESPN returns all stat blocks and we filter locally
        {
            "players": {
                "filterIds": {"value": player_ids},
                "limit": len(player_ids) + 5,
                "sortAppliedStatTotal": {
                    "sortPriority": 1,
                    "value": f"00{season_str}{scoring_period:03d}",
                },
            }
        },
    ]

    for attempt, filters in enumerate(filter_variants):
        old_filter = session.headers.pop("x-fantasy-filter", None)
        session.headers["x-fantasy-filter"] = json.dumps(filters, separators=(",", ":"))

        data = fetch_json(
            session,
            base_url,
            {"view": "kona_player_info", "scoringPeriodId": scoring_period},
        )

        del session.headers["x-fantasy-filter"]
        if old_filter is not None:
            session.headers["x-fantasy-filter"] = old_filter

        if not data:
            continue

        result: dict[int, list[dict]] = {}
        for player in data.get("players", []):
            pid = player.get("id")
            ppe = player.get("playerPoolEntry", {})
            stats = ppe.get("stats", [])
            if pid is not None and stats:
                result[int(pid)] = stats

        if result:
            if attempt > 0:
                logging.info("  kona: variant 2 (no period filter) succeeded for %d players.", len(result))
            return result

        if attempt == 0 and data.get("players"):
            logging.debug(
                "  kona variant 1 returned %d player objects but all had empty stats; "
                "retrying without filterStatsForCurrentSeasonScoringPeriodId.",
                len(data.get("players", [])),
            )

    return {}


def extract_team_stats_from_boxscore(
    data: dict,
    team_id: int,
) -> dict[int, list[dict]]:
    """
    Fallback stats source: extract playerPoolEntry.stats from teams[] in a
    mBoxscore response. teams[] is populated even when schedule[].
    rosterForCurrentScoringPeriod.entries[].playerPoolEntry.stats is absent.
    Returns {player_id: [stat_block, ...]} for players that have any stats.
    """
    result: dict[int, list[dict]] = {}
    for team in data.get("teams", []):
        if team.get("id") != team_id:
            continue
        roster_obj = (
            team.get("roster")
            or team.get("rosterForCurrentScoringPeriod", {})
        )
        for entry in roster_obj.get("entries", []):
            ppe = entry.get("playerPoolEntry", {})
            pid = ppe.get("id") or ppe.get("playerId")
            stats = ppe.get("stats", [])
            if pid is not None and stats:
                result[int(pid)] = stats
    return result


def find_team_roster(
    schedule: list,
    team_id: int,
    scoring_period: int,
) -> tuple[list, int | None]:
    """
    Locate and return the roster entries list for team_id in the schedule.
    Also returns the matchupPeriodId for this scoring period.
    Tries multiple field name patterns because ESPN changes the response shape.
    """
    for matchup in schedule:
        mp_id = matchup.get("matchupPeriodId")
        for side in ("home", "away"):
            team = matchup.get(side, {})
            if team.get("teamId") != team_id:
                continue
            # Try roster field names in priority order
            roster_obj = (
                team.get("rosterForCurrentScoringPeriod")
                or team.get("rosterForScoringPeriod", {}).get(str(scoring_period))
                or team.get("rosterForScoringPeriod", {}).get(scoring_period)
                or team.get("rosterForMatchupPeriod")
            )
            if roster_obj:
                return roster_obj.get("entries", []), mp_id
    return [], None


def extract_player_stats(
    player_pool_entry: dict,
    scoring_period: int,
    kona_stats: list[dict] | None = None,
) -> tuple[dict, dict]:
    """
    Extract actual per-scoring-period stats for a player.

    Tries (in order):
      1. kona_stats — stat blocks from fetch_player_stats_kona (preferred)
      2. player_pool_entry.stats — from the mBoxscore response (fallback)

    Returns:
        (named_stats, raw_stats_dict) where named_stats maps column names to
        values and raw_stats_dict maps stat_id → value for all stats found.
    """
    named: dict[str, Any] = {}
    raw: dict[str, Any] = {}

    if kona_stats is not None:
        # kona was already scoped to this scoring period in the request.
        # ESPN sometimes returns daily stats under a different scoringPeriodId
        # than requested, tagged with statSplitTypeId=5 (daily split).
        # Priority: exact period match → daily-split blocks → give up.
        # Never fall through to season totals (statSplitTypeId=0) for a daily log.
        actual = [s for s in kona_stats if s.get("statSourceId", -1) == 0]
        exact = [s for s in actual if s.get("scoringPeriodId") == scoring_period]
        daily = [s for s in actual if s.get("statSplitTypeId") == 5]
        stat_blocks = exact or daily
    else:
        # mBoxscore fallback: enforce period to avoid picking up weekly/season blocks.
        stat_blocks = [
            s for s in player_pool_entry.get("stats", [])
            if s.get("statSourceId", -1) == 0
            and (s.get("scoringPeriodId") is None or s.get("scoringPeriodId") == scoring_period)
        ]

    for stat_block in stat_blocks:
        for str_id, value in stat_block.get("stats", {}).items():
            sid = int(str_id)
            raw[sid] = value
            info = STAT_ID_MAP.get(sid)
            if info:
                named[info[0]] = value

    return named, raw


def build_row(
    scoring_period: int,
    matchup_period: int | None,
    team_id: int,
    team_name: str,
    entry: dict,
    slot_map: dict[int, str],
    kona_stats: list[dict] | None = None,
    include_raw_json: bool = False,
    warnings: list | None = None,
) -> dict:
    """
    Parse one roster entry into a flat output row.
    kona_stats: stat blocks from fetch_player_stats_kona for this player; used
    in preference to playerPoolEntry.stats which is absent in mBoxscore responses.
    All fields from the spec are attempted; missing ones are None.
    """
    slot_id = entry.get("lineupSlotId")
    slot_name = slot_map.get(slot_id, f"slot_{slot_id}") if slot_id is not None else "Unknown"
    active_status = classify_slot(slot_name, slot_id)

    if active_status == "Unknown" and warnings is not None:
        warnings.append({
            "scoringPeriodId": scoring_period,
            "issue": f"Unknown slot classification for slot_id={slot_id}, slot_name={slot_name!r}",
            "action": "Manually map this slot in DEFAULT_SLOT_MAP",
        })

    ppe = entry.get("playerPoolEntry", {})
    player = ppe.get("player", {})
    player_id = ppe.get("playerId") or ppe.get("id") or player.get("id")
    first = player.get("firstName", "")
    last = player.get("lastName", "")
    full_name = player.get("fullName") or f"{first} {last}".strip() or str(player_id)
    pro_team_id = player.get("proTeamId")
    default_pos_id = player.get("defaultPositionId")
    eligible_slots = player.get("eligibleSlots", [])

    named_stats, raw_stats = extract_player_stats(ppe, scoring_period, kona_stats=kona_stats)

    # ── Derived stats ─────────────────────────────────────────────────────────
    # IP decimal conversion
    ip_raw = named_stats.get("IP")
    ip_decimal: float | None = None
    if ip_raw is not None:
        try:
            ip_decimal = ip_to_decimal(float(ip_raw))
        except (TypeError, ValueError):
            ip_decimal = None
            if warnings is not None:
                warnings.append({
                    "scoringPeriodId": scoring_period,
                    "issue": f"Could not convert IP={ip_raw!r} for player {full_name}",
                    "action": "Check raw_stats_json for IP stat format",
                })

    # ERA = ER * 9 / IP  (only if ESPN didn't provide it)
    era_calc: float | None = None
    if ip_decimal and ip_decimal > 0:
        er = named_stats.get("ER")
        if er is not None:
            era_calc = (float(er) * 9) / ip_decimal

    # WHIP = (H_allowed + BB_allowed) / IP
    whip_calc: float | None = None
    if ip_decimal and ip_decimal > 0:
        h_a = named_stats.get("H_allowed")
        bb_a = named_stats.get("BB_allowed")
        if h_a is not None and bb_a is not None:
            whip_calc = (float(h_a) + float(bb_a)) / ip_decimal

    # OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    obp_calc: float | None = None
    h = named_stats.get("H")
    bb_bat = named_stats.get("BB")
    hbp = named_stats.get("HBP")
    ab = named_stats.get("AB")
    sf = named_stats.get("SF") or 0
    if all(v is not None for v in (h, bb_bat, hbp, ab)):
        denom = float(ab) + float(bb_bat) + float(hbp) + float(sf)
        if denom > 0:
            obp_calc = (float(h) + float(bb_bat) + float(hbp)) / denom

    # SVHD = SV + HLD  (if ESPN didn't provide it)
    sv = named_stats.get("SV") or named_stats.get("SV_35") or named_stats.get("SV2") or named_stats.get("SV_63")
    hld = named_stats.get("HLD") or named_stats.get("HLD_72")
    svhd_calc: float | None = None
    if sv is not None and hld is not None:
        svhd_calc = float(sv) + float(hld)
    # Use ESPN-provided SVHD if available
    svhd_espn = named_stats.get("SVHD_espn")

    # ── Assemble row ──────────────────────────────────────────────────────────
    row: dict[str, Any] = {
        # Identity
        "scoringPeriodId": scoring_period,
        "matchupPeriodId": matchup_period,
        "fantasyTeamId": team_id,
        "fantasyTeamName": team_name,
        "playerId": player_id,
        "playerName": full_name,
        "proTeamId": pro_team_id,
        "defaultPositionId": default_pos_id,
        "eligibleSlots": json.dumps(eligible_slots) if eligible_slots else None,
        # Slot / Active-Bench
        "fantasy_slot_id": slot_id,
        "fantasy_slot_name": slot_name,
        "raw_espn_slot_value": slot_id,
        "active_status": active_status,
        # Batting
        "AB": named_stats.get("AB"),
        "H": named_stats.get("H"),
        "R": named_stats.get("R"),
        "HR": named_stats.get("HR"),
        "RBI": named_stats.get("RBI"),
        "BB": named_stats.get("BB"),
        "HBP": named_stats.get("HBP"),
        "SF": named_stats.get("SF"),
        "SB": named_stats.get("SB"),
        "OBP_espn": named_stats.get("OBP"),
        "OBP_calc": round(obp_calc, 4) if obp_calc is not None else None,
        "AVG": named_stats.get("AVG"),
        "SLG": named_stats.get("SLG"),
        "OPS": named_stats.get("OPS"),
        "TB": named_stats.get("TB"),
        "PA": named_stats.get("PA"),
        "2B": named_stats.get("2B"),
        "3B": named_stats.get("3B"),
        "IBB": named_stats.get("IBB"),
        "SO_bat": named_stats.get("SO_bat"),
        "XBH": named_stats.get("XBH"),
        "GIDP": named_stats.get("GIDP"),
        "CS": named_stats.get("CS"),
        # Pitching
        "IP_raw": ip_raw,
        "IP_decimal": round(ip_decimal, 4) if ip_decimal is not None else None,
        "H_allowed": named_stats.get("H_allowed"),
        "BB_allowed": named_stats.get("BB_allowed"),
        "ER": named_stats.get("ER"),
        "K": named_stats.get("K"),
        "QS": named_stats.get("QS"),
        "W": named_stats.get("W"),
        "L": named_stats.get("L"),
        "SV": sv,
        "HLD": hld,
        "SVHD_espn": svhd_espn,
        "SVHD_calc": svhd_calc,
        "ERA_espn": named_stats.get("ERA_espn"),
        "ERA_calc": round(era_calc, 4) if era_calc is not None else None,
        "WHIP_espn": named_stats.get("WHIP_espn"),
        "WHIP_calc": round(whip_calc, 4) if whip_calc is not None else None,
        "BS": named_stats.get("BS") or named_stats.get("BS2"),
        "CG": named_stats.get("CG"),
        "HR_allowed": named_stats.get("HR_allowed"),
        "R_allowed": named_stats.get("R_allowed"),
        "K9": named_stats.get("K9"),
        "GS_p": named_stats.get("GS_p"),
        "GP_p": named_stats.get("GP_p"),
        # Metadata
        "source_endpoint": BASE_URL.split("/leagues")[0],
    }

    if include_raw_json:
        row["raw_stats_json"] = json.dumps({str(k): v for k, v in raw_stats.items()})
    else:
        row["raw_stats_json"] = None

    # Warn about stat IDs in raw that have no mapping
    unmapped = [k for k in raw_stats if k not in STAT_ID_MAP]
    if unmapped and warnings is not None:
        warnings.append({
            "scoringPeriodId": scoring_period,
            "issue": f"Player {full_name!r} has unmapped stat IDs: {unmapped}",
            "action": "Check raw_stats_json and add to STAT_ID_MAP if needed",
        })

    return row


# ─────────────────────────────────────────────────────────────────────────────
# Active/Bench validation
# ─────────────────────────────────────────────────────────────────────────────

def build_slot_validation_csv(
    rows: list[dict],
    manual_examples_path: Path | None,
) -> pd.DataFrame:
    """
    Build a slot_mapping_validation.csv DataFrame showing how each slot ID
    was classified.  If manual_examples_path is provided, compare against it.
    """
    # Distinct slot IDs / names seen across all rows
    seen: dict[tuple, dict] = {}
    for r in rows:
        key = (r["fantasy_slot_id"], r["fantasy_slot_name"])
        if key not in seen:
            seen[key] = {
                "fantasy_slot_id": r["fantasy_slot_id"],
                "fantasy_slot_name": r["fantasy_slot_name"],
                "active_status_assigned": r["active_status"],
                "example_player": r["playerName"],
                "example_scoringPeriodId": r["scoringPeriodId"],
            }

    val_rows = list(seen.values())

    if manual_examples_path and manual_examples_path.exists():
        manual = pd.read_csv(manual_examples_path)
        # manual must have: scoringPeriodId, playerName, expected_status
        row_df = pd.DataFrame(rows)
        merged = manual.merge(
            row_df[["scoringPeriodId", "playerName", "active_status"]],
            on=["scoringPeriodId", "playerName"],
            how="left",
        )
        merged["validation_result"] = merged.apply(
            lambda r: "PASS" if r["expected_status"] == r["active_status"] else "FAIL",
            axis=1,
        )
        mismatches = merged[merged["validation_result"] == "FAIL"]
        if not mismatches.empty:
            logging.error(
                "ACTIVE/BENCH VALIDATION FAILED for %d manual example(s):\n%s",
                len(mismatches),
                mismatches[["scoringPeriodId", "playerName", "expected_status", "active_status"]].to_string(),
            )
        else:
            logging.info("Manual Active/Bench validation: all %d examples PASSED.", len(manual))
        val_rows_df = pd.DataFrame(val_rows)
        val_rows_df = pd.concat(
            [val_rows_df, merged.rename(columns={"active_status": "active_status_assigned"})],
            sort=False,
        )
        return val_rows_df

    return pd.DataFrame(val_rows)


# ─────────────────────────────────────────────────────────────────────────────
# Main export loop
# ─────────────────────────────────────────────────────────────────────────────

def run_export(
    config: dict,
    start_sp: int,
    end_sp: int | str,
    active_only: bool,
    include_raw_json: bool,
    manual_validation_path: Path | None,
) -> None:
    """Main export loop — fetches, parses, validates, and saves all data."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    logging.info("Output directory: %s", OUTPUT_DIR.resolve())

    session = build_session(config["ESPN_SWID"], config["ESPN_S2"])
    base_url = BASE_URL.format(
        season=config["ESPN_SEASON_ID"],
        league_id=config["ESPN_LEAGUE_ID"],
    )
    team_id = int(config["ESPN_TEAM_ID"])
    season = config["ESPN_SEASON_ID"]

    # Never print the full espn_s2
    logging.info(
        "Authenticated: league=%s, season=%s, teamId=%d, SWID=%.8s…",
        config["ESPN_LEAGUE_ID"], season, team_id, config["ESPN_SWID"],
    )

    # Load settings
    league = load_league_settings(session, base_url)
    slot_map = league["slot_map"]
    sp_to_mp = league["scoring_period_to_matchup"]

    # Resolve end_sp
    if end_sp == "auto":
        end_sp = league["current_scoring_period"] or league["final_scoring_period"]
        if end_sp is None:
            logging.error(
                "Could not determine current scoring period from ESPN. "
                "Please pass --end-scoring-period explicitly."
            )
            sys.exit(1)
        end_sp = int(end_sp)
        logging.info("Auto-detected end scoring period: %d", end_sp)
    else:
        end_sp = int(end_sp)

    logging.info("Exporting scoring periods %d → %d", start_sp, end_sp)

    all_rows: list[dict] = []
    warnings: list[dict] = []
    failed_periods: list[int] = []

    for sp in range(start_sp, end_sp + 1):
        logging.info("Fetching scoringPeriodId=%d / %d…", sp, end_sp)

        data = fetch_boxscore(session, base_url, sp)
        if not data:
            failed_periods.append(sp)
            warnings.append({
                "scoringPeriodId": sp,
                "issue": "fetch_boxscore returned None",
                "action": "Check authentication and network. ESPN may not have data for this period.",
            })
            continue

        schedule = data.get("schedule", [])
        if not schedule:
            logging.warning("  scoringPeriodId=%d: empty schedule. Skipping.", sp)
            warnings.append({
                "scoringPeriodId": sp,
                "issue": "ESPN returned empty schedule",
                "action": "This scoring period may be before the season started or in a bye week.",
            })
            continue

        entries, mp_from_sched = find_team_roster(schedule, team_id, sp)
        # Prefer map from settings schedule; fall back to embedded matchup period
        mp = sp_to_mp.get(sp) or mp_from_sched

        if not entries:
            logging.warning(
                "  scoringPeriodId=%d: teamId=%d not found in schedule. "
                "Dumping teamIds present: %s",
                sp, team_id,
                [(m.get("matchupPeriodId"),
                  m.get("home", {}).get("teamId"),
                  m.get("away", {}).get("teamId")) for m in schedule[:5]],
            )
            warnings.append({
                "scoringPeriodId": sp,
                "issue": f"teamId={team_id} not found in this period's schedule",
                "action": "Verify ESPN_TEAM_ID. Run inspect_endpoint.py --scoring-period %d" % sp,
            })
            failed_periods.append(sp)
            continue

        # Collect player IDs for the kona stats fetch
        player_ids = []
        for entry in entries:
            ppe = entry.get("playerPoolEntry", {})
            pid = ppe.get("id") or ppe.get("playerId") or entry.get("playerId")
            if pid:
                player_ids.append(int(pid))

        # Fetch per-player stats via kona_player_info.
        # mBoxscore returns lineup slots but not stats; kona fills the gap.
        # If kona returns nothing (common for historical periods), fall back to
        # teams[] in the same mBoxscore response.
        kona_stats_by_player: dict[int, list[dict]] = {}
        if player_ids:
            kona_stats_by_player = fetch_player_stats_kona(session, base_url, sp, player_ids)
            if kona_stats_by_player:
                logging.info("  kona fetched stats for %d/%d players.",
                             len(kona_stats_by_player), len(player_ids))
            else:
                logging.warning(
                    "  kona returned no stats for scoringPeriodId=%d; "
                    "trying teams[] from mBoxscore as fallback.", sp,
                )
                kona_stats_by_player = extract_team_stats_from_boxscore(data, team_id)
                if kona_stats_by_player:
                    logging.info(
                        "  teams[] fallback: found stats for %d players.", len(kona_stats_by_player),
                    )
                else:
                    logging.warning(
                        "  teams[] fallback also returned no stats for scoringPeriodId=%d "
                        "(no games played this period, or ESPN doesn't provide per-player stats here).", sp,
                    )

        period_rows = 0
        for entry in entries:
            ppe = entry.get("playerPoolEntry", {})
            pid = ppe.get("id") or ppe.get("playerId") or entry.get("playerId")
            kona = kona_stats_by_player.get(int(pid)) if pid else None

            try:
                row = build_row(
                    scoring_period=sp,
                    matchup_period=mp,
                    team_id=team_id,
                    team_name="La Flama Blancos",
                    entry=entry,
                    slot_map=slot_map,
                    kona_stats=kona,
                    include_raw_json=include_raw_json,
                    warnings=warnings,
                )
            except Exception as exc:
                warnings.append({
                    "scoringPeriodId": sp,
                    "issue": f"Exception parsing entry: {exc}",
                    "action": "Enable --include-raw-json and inspect raw_stats_json",
                })
                logging.exception("  Entry parse error sp=%d: %s", sp, exc)
                continue

            if active_only and row.get("active_status") != "Active":
                continue
            all_rows.append(row)
            period_rows += 1

        logging.info("  scoringPeriodId=%d: parsed %d player rows.", sp, period_rows)

        # Small delay to be polite to ESPN's servers
        time.sleep(0.5)

    if not all_rows:
        logging.error("No rows collected. Check warnings in outputs/parse_warnings.csv.")
        _save_warnings(warnings)
        sys.exit(1)

    df = pd.DataFrame(all_rows)

    # ── Save main outputs ─────────────────────────────────────────────────────
    csv_path = OUTPUT_DIR / f"la_flama_blancos_daily_player_logs_{season}.csv"
    xlsx_path = OUTPUT_DIR / f"la_flama_blancos_daily_player_logs_{season}.xlsx"

    df.to_csv(csv_path, index=False)
    logging.info("Saved CSV: %s  (%d rows)", csv_path, len(df))

    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logging.info("Saved XLSX: %s", xlsx_path)

    # ── Save slot mapping validation ──────────────────────────────────────────
    val_df = build_slot_validation_csv(all_rows, manual_validation_path)
    val_path = OUTPUT_DIR / "slot_mapping_validation.csv"
    val_df.to_csv(val_path, index=False)
    logging.info("Saved slot mapping validation: %s", val_path)

    # ── Save warnings ─────────────────────────────────────────────────────────
    _save_warnings(warnings)

    # ── Summary ──────────────────────────────────────────────────────────────
    n_active = (df["active_status"] == "Active").sum()
    n_bench = (df["active_status"] == "Bench").sum()
    n_il = (df["active_status"] == "IL").sum()
    n_unknown = (df["active_status"] == "Unknown").sum()

    logging.info(
        "Export complete: %d total rows | %d Active | %d Bench | %d IL | %d Unknown",
        len(df), n_active, n_bench, n_il, n_unknown,
    )
    if failed_periods:
        logging.warning("Failed scoring periods (no data): %s", failed_periods)
    if n_unknown > 0:
        logging.warning(
            "%d rows have active_status=Unknown. See slot_mapping_validation.csv "
            "and update DEFAULT_SLOT_MAP.",
            n_unknown,
        )
    logging.info("Output files:\n  %s\n  %s\n  %s", csv_path, xlsx_path, val_path)


def _save_warnings(warnings: list[dict]) -> None:
    warn_path = OUTPUT_DIR / "parse_warnings.csv"
    if warnings:
        pd.DataFrame(warnings).to_csv(warn_path, index=False)
        logging.warning("Wrote %d warnings to %s", len(warnings), warn_path)
    else:
        logging.info("No parse warnings.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(OUTPUT_DIR / "export_run.log", mode="a"),
        ],
    )

    parser = argparse.ArgumentParser(
        description="Export ESPN Fantasy Baseball daily player logs for La Flama Blancos."
    )
    parser.add_argument(
        "--start-scoring-period", type=int, default=1,
        help="First scoringPeriodId to fetch (default: 1)",
    )
    parser.add_argument(
        "--end-scoring-period", default="auto",
        help='Last scoringPeriodId to fetch, or "auto" to use current period (default: auto)',
    )
    parser.add_argument(
        "--active-only", action="store_true",
        help="Export only rows where active_status == Active",
    )
    parser.add_argument(
        "--include-raw-json", action="store_true",
        help="Include raw ESPN stats JSON blob in output (useful for debugging stat IDs)",
    )
    parser.add_argument(
        "--validate-manual",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to manual_validation_examples.csv with columns: "
             "scoringPeriodId, playerName, expected_status",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    config = load_config()

    run_export(
        config=config,
        start_sp=args.start_scoring_period,
        end_sp=args.end_scoring_period,
        active_only=args.active_only,
        include_raw_json=args.include_raw_json,
        manual_validation_path=args.validate_manual,
    )


if __name__ == "__main__":
    main()
