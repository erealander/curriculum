#!/usr/bin/env python3
"""
inspect_endpoint.py

Diagnostic tool that probes ESPN Fantasy Baseball API endpoints for a single
scoring period, prints the response structure, maps lineup slot IDs, and saves
a sample JSON for offline inspection.

Run BEFORE pull_espn_daily_logs.py to validate that the API shape is what
the main script expects. Especially important for verifying Active vs Bench
slot mapping.

Usage:
    python inspect_endpoint.py
    python inspect_endpoint.py --scoring-period 5
    python inspect_endpoint.py --scoring-period 1 --show-raw
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

OUTPUT_DIR = Path(__file__).parent / "outputs"

# ESPN moved their Fantasy Baseball API to lm-api-reads in 2024.
# The old fantasy.espn.com/apis/v3/... URL now returns HTML instead of JSON.
BASE_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb"
    "/seasons/{season}/segments/0/leagues/{league_id}"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────── helpers ──────────────────────────────────────────

def load_config() -> dict:
    """Load ESPN credentials and league info from .env or environment."""
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
        log.error("Missing required environment variables: %s", missing)
        log.error("Copy .env.example to .env and fill in your ESPN credentials.")
        sys.exit(1)
    return config


def build_session(swid: str, espn_s2: str) -> requests.Session:
    """Build an authenticated requests session."""
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


def fetch(session: requests.Session, url: str, params: dict) -> dict | None:
    """GET the ESPN API. Returns parsed JSON or None on error."""
    try:
        resp = session.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        log.error("Request failed: %s", exc)
        return None

    if resp.status_code == 401:
        log.error("ESPN returned 401 Unauthorized. Your SWID/espn_s2 cookies are expired "
                  "or incorrect. Re-copy them from your browser.")
        return None
    if resp.status_code == 403:
        log.error("ESPN returned 403 Forbidden. This may be a private league — make sure "
                  "you are authenticated and have access to league %s.", params.get("leagueId", "?"))
        return None
    if resp.status_code != 200:
        log.error("ESPN returned HTTP %d: %s", resp.status_code, resp.text[:200])
        return None

    try:
        return resp.json()
    except ValueError:
        log.error("ESPN did not return valid JSON. First 500 chars: %s", resp.text[:500])
        return None


# ─────────────────────────── structure helpers ────────────────────────────────

def _keys_preview(obj: Any, depth: int = 0, max_depth: int = 5, indent: int = 2) -> str:
    """Return a compact tree-view of an object's keys (no values)."""
    pad = " " * (indent * depth)
    if isinstance(obj, dict):
        lines = []
        for k, v in list(obj.items())[:30]:
            if isinstance(v, (dict, list)) and depth < max_depth:
                child = _keys_preview(v, depth + 1, max_depth, indent)
                lines.append(f"{pad}{k}:\n{child}")
            else:
                type_str = type(v).__name__
                if isinstance(v, list):
                    type_str = f"list[{len(v)}]"
                lines.append(f"{pad}{k}: <{type_str}>")
        return "\n".join(lines)
    elif isinstance(obj, list):
        if not obj:
            return f"{pad}(empty list)"
        return _keys_preview(obj[0], depth, max_depth, indent) + (
            f"\n{pad}... ({len(obj)} items total)" if len(obj) > 1 else ""
        )
    else:
        return f"{pad}<{type(obj).__name__}>"


def collect_leaf_paths(obj: Any, path: str = "", results: list | None = None) -> list[str]:
    """Recursively collect all key paths in the JSON (to max depth 6)."""
    if results is None:
        results = []
    if len(path.split(".")) > 8:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            collect_leaf_paths(v, new_path, results)
    elif isinstance(obj, list) and obj:
        collect_leaf_paths(obj[0], f"{path}[0]", results)
    else:
        results.append(path)
    return results


# ─────────────────────────── core inspection ──────────────────────────────────

def inspect_settings(session: requests.Session, base: str) -> dict:
    """
    Fetch league settings to discover lineup slot definitions.
    Returns a slot_id -> slot_name mapping, starting from DEFAULT_SLOT_MAP
    and updating with any names ESPN provides.
    """
    log.info("Fetching mSettings to discover lineup slot definitions…")
    data = fetch(session, base, {"view": "mSettings"})
    if not data:
        log.warning("mSettings fetch failed — returning DEFAULT_SLOT_MAP only.")
        from pull_espn_daily_logs import DEFAULT_SLOT_MAP
        return dict(DEFAULT_SLOT_MAP)

    # Start from the hardcoded default; ESPN settings rarely include slot names
    # for baseball leagues but may add new/custom slot IDs.
    try:
        from pull_espn_daily_logs import DEFAULT_SLOT_MAP
        slot_map: dict[int, str] = dict(DEFAULT_SLOT_MAP)
    except ImportError:
        slot_map = {}

    settings = data.get("settings", {})

    # Try positionSlots — only update if ESPN provides a real name (not blank/None)
    pos_slots = settings.get("positionSlots") or settings.get("rosterSettings", {}).get("positionSlots", [])
    if pos_slots:
        for slot in pos_slots:
            sid = slot.get("slotCategoryId") or slot.get("id")
            name = slot.get("defaultDisplay") or slot.get("abbrev") or slot.get("name")
            if sid is not None and name:
                slot_map[int(sid)] = name

    # Add any new slot IDs from lineupSlotCounts not already known
    slot_counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {})
    for sid_str in slot_counts:
        sid = int(sid_str)
        if sid not in slot_map:
            slot_map[sid] = f"slot_{sid}"  # genuinely unknown slot

    log.info("Slot map (%d slots): %s", len(slot_map), slot_map)

    # Save settings for inspection
    (OUTPUT_DIR / "settings_sample.json").write_text(
        json.dumps(data, indent=2, default=str)
    )
    log.info("Saved raw settings to outputs/settings_sample.json")
    return slot_map


def find_team_entry(schedule: list, team_id: int, scoring_period: int) -> tuple[dict | None, str]:
    """
    Locate the matchup containing team_id and return the team-side dict plus side label.
    Tries rosterForCurrentScoringPeriod first, then rosterForScoringPeriod dict.
    """
    for matchup in schedule:
        for side in ("home", "away"):
            team = matchup.get(side, {})
            if team.get("teamId") == team_id:
                # Prefer scoringPeriod-specific roster
                roster = (
                    team.get("rosterForCurrentScoringPeriod")
                    or team.get("rosterForScoringPeriod", {}).get(str(scoring_period))
                    or team.get("rosterForScoringPeriod", {}).get(scoring_period)
                    or team.get("rosterForMatchupPeriod")
                )
                if roster:
                    return roster, side
    return None, ""


def inspect_scoring_period(
    session: requests.Session,
    base: str,
    team_id: int,
    scoring_period: int,
    slot_map: dict,
    dump_first_entry: bool = False,
) -> None:
    """
    Fetch box-score data for one scoring period and print a detailed analysis.
    """
    log.info("Fetching mBoxscore for scoringPeriodId=%d…", scoring_period)
    data = fetch(session, base, {
        "view": "mBoxscore",
        "scoringPeriodId": scoring_period,
    })
    if not data:
        return

    # Save raw JSON
    sample_path = OUTPUT_DIR / "endpoint_sample.json"
    sample_path.write_text(json.dumps(data, indent=2, default=str))
    log.info("Saved raw endpoint response to outputs/endpoint_sample.json (%d bytes)",
             sample_path.stat().st_size)

    schedule = data.get("schedule", [])
    log.info("Schedule contains %d matchup(s) for scoringPeriodId=%d", len(schedule), scoring_period)

    # Show schedule-level structure
    if schedule:
        print("\n─── Schedule[0] key structure ───")
        print(_keys_preview(schedule[0], max_depth=4))

    # Find our team's matchup
    roster, side = find_team_entry(schedule, team_id, scoring_period)
    if not roster:
        log.warning(
            "Could not find teamId=%d in schedule for scoringPeriodId=%d. "
            "The matchup period might differ. Showing full schedule teamIds:",
            team_id, scoring_period,
        )
        for m in schedule:
            h = m.get("home", {}).get("teamId", "?")
            a = m.get("away", {}).get("teamId", "?")
            mp = m.get("matchupPeriodId", "?")
            print(f"  matchupPeriodId={mp}: home={h} vs away={a}")
        return

    entries = roster.get("entries", [])
    log.info("Found team on %s side. Roster has %d entries.", side, len(entries))

    # ─── Raw first entry dump (--dump-first-entry) ────────────────────────────
    if dump_first_entry and entries:
        print("\n─── Full playerPoolEntry of first roster entry (raw JSON) ───")
        first_ppe = entries[0].get("playerPoolEntry", {})
        print(json.dumps(first_ppe, indent=2, default=str))
        print("─── End of first entry dump ───\n")

    # ─── Slot analysis ────────────────────────────────────────────────────────
    print("\n─── Lineup Slot Analysis ───")
    print(f"{'slotId':>8}  {'slotName':>8}  {'active_status':>14}  {'playerName'}")
    print("-" * 60)

    all_slot_ids = set()
    stat_ids_seen = set()

    for entry in entries:
        slot_id = entry.get("lineupSlotId")
        all_slot_ids.add(slot_id)

        slot_name = slot_map.get(slot_id, f"slot_{slot_id}")
        active_status = classify_slot(slot_name, slot_id)

        ppe = entry.get("playerPoolEntry", {})
        player = ppe.get("player", {})
        player_name = player.get("fullName") or player.get("firstName", "") + " " + player.get("lastName", "")
        player_name = player_name.strip() or "(no name)"

        print(f"{slot_id:>8}  {slot_name:>8}  {active_status:>14}  {player_name}")

        # Collect stat IDs
        for stat_entry in ppe.get("stats", []):
            if stat_entry.get("statSourceId", -1) == 0:  # actual stats only
                for stat_id in stat_entry.get("stats", {}).keys():
                    stat_ids_seen.add(int(stat_id))

    # ─── Slot mapping validation note ─────────────────────────────────────────
    print("\n─── Slot IDs found this period ───")
    print(f"  Slot IDs: {sorted(all_slot_ids)}")
    print("\nIMPORTANT: Validate these slot IDs against the ESPN box-score UI.")
    print("  Open: https://fantasy.espn.com/baseball/boxscore?"
          f"leagueId=1600541809&seasonId=2026&teamId={team_id}&scoringPeriodId={scoring_period}")
    print("  Compare each player's row in the UI to their slotId above.")

    # ─── Stat ID analysis ─────────────────────────────────────────────────────
    if stat_ids_seen:
        print(f"\n─── Stat IDs found in actual stats (statSourceId=0): ───")
        print(f"  IDs: {sorted(stat_ids_seen)}")
        print("\n  Mapping against known ESPN Fantasy Baseball stat IDs:")
        from pull_espn_daily_logs import STAT_ID_MAP  # type: ignore
        for sid in sorted(stat_ids_seen):
            info = STAT_ID_MAP.get(sid)
            if info:
                print(f"    {sid:>5}: {info[0]:>12}  ({info[2]}) — {info[1]}")
            else:
                print(f"    {sid:>5}: ??? UNKNOWN — check raw JSON for context")

    # ─── Stat split type IDs found in mBoxscore playerPoolEntry ──────────────
    print("\n─── Stat split type IDs found in mBoxscore playerPoolEntry.stats ───")
    split_ids = set()
    for entry in entries:
        ppe = entry.get("playerPoolEntry", {})
        for stat_entry in ppe.get("stats", []):
            split_ids.add((
                stat_entry.get("statSourceId"),
                stat_entry.get("statSplitTypeId"),
                stat_entry.get("scoringPeriodId"),
            ))
    if split_ids:
        for source, split, sp in sorted(split_ids):
            label = {0: "actual", 1: "projected"}.get(source, f"source={source}")
            print(f"  statSourceId={source} ({label}), statSplitTypeId={split}, scoringPeriodId={sp}")
    else:
        print("  (none — mBoxscore does not include per-player stats for this period)")
        print("  → Will probe kona_player_info below…")

    # ─── Probe: kona_player_info (per-player per-period stats) ───────────────
    print("\n─── Probe: kona_player_info (per-player stats endpoint) ───")
    player_ids = []
    for entry in entries:
        ppe = entry.get("playerPoolEntry", {})
        pid = ppe.get("id") or ppe.get("playerId") or entry.get("playerId")
        if pid:
            player_ids.append(int(pid))

    if player_ids:
        # Test with up to 5 players so the request is small.
        # No limit/offset — filterIds already constrains the result set.
        # sortAppliedStatTotal is required by ESPN when any sort/limit is present.
        test_ids = player_ids[:5]
        filters = {
            "players": {
                "filterStatsForCurrentSeasonScoringPeriodId": {"value": [scoring_period]},
                "filterIds": {"value": test_ids},
                "sortAppliedStatTotal": {
                    "sortAway": False,
                    "sortPriority": 1,
                    "value": f"002026{scoring_period:03d}",
                },
            }
        }
        old_filter = session.headers.pop("x-fantasy-filter", None)
        session.headers["x-fantasy-filter"] = json.dumps(filters, separators=(",", ":"))

        kona_data = fetch(session, base, {
            "view": "kona_player_info",
            "scoringPeriodId": scoring_period,
        })

        del session.headers["x-fantasy-filter"]
        if old_filter is not None:
            session.headers["x-fantasy-filter"] = old_filter

        if kona_data:
            kona_players = kona_data.get("players", [])
            print(f"  kona_player_info returned {len(kona_players)} player record(s) for test IDs {test_ids}")
            kona_has_stats = False
            for kp in kona_players:
                ppe_k = kp.get("playerPoolEntry", {})
                kona_stats = ppe_k.get("stats", [])
                pname = ppe_k.get("player", {}).get("fullName", kp.get("id", "?"))
                actual = [s for s in kona_stats if s.get("statSourceId") == 0
                          and s.get("scoringPeriodId") == scoring_period]
                if actual:
                    kona_has_stats = True
                    non_zero = {k: v for k, v in actual[0].get("stats", {}).items() if v != 0}
                    print(f"  ✓ {pname}: {len(actual)} actual stat block(s), "
                          f"non-zero stat IDs: {list(non_zero.keys())[:15]}")
                else:
                    print(f"  ✗ {pname}: kona returned stats but none matched "
                          f"scoringPeriodId={scoring_period} with statSourceId=0")

            if kona_has_stats:
                print("\n  → kona_player_info WORKS for per-player stats.")
                print("    pull_espn_daily_logs.py will use this approach automatically.")
            else:
                print(f"\n  → kona_player_info returned data but no actual stats for period {scoring_period}.")
                print("    Try a later scoring period: python3 inspect_endpoint.py --scoring-period 50")

            # Save kona sample
            kona_path = OUTPUT_DIR / "kona_sample.json"
            kona_path.write_text(json.dumps(kona_data, indent=2, default=str))
            log.info("Saved kona_player_info sample to outputs/kona_sample.json")
        else:
            print("  → kona_player_info returned no data.")
            print("    This may mean: (a) credentials expired, (b) no games this period, "
                  "or (c) kona is not available for this league.")
    else:
        print("  → No player IDs found — cannot probe kona.")

    # ─── IP format detection ───────────────────────────────────────────────────
    print("\n─── IP (Innings Pitched) format check ───")
    ip_values = []
    for entry in entries:
        ppe = entry.get("playerPoolEntry", {})
        for stat_entry in ppe.get("stats", []):
            stats_dict = stat_entry.get("stats", {})
            for ip_key in ("26",):  # stat ID 26 = IP
                if ip_key in stats_dict and stats_dict[ip_key] != 0:
                    ip_values.append(stats_dict[ip_key])
    if ip_values:
        print(f"  IP values found: {ip_values[:10]}")
        examples_with_fractional = [v for v in ip_values if v != int(v)]
        if examples_with_fractional:
            sample = examples_with_fractional[0]
            frac = round(sample - int(sample), 4)
            if frac in (0.1, 0.2):
                print(f"  → Looks like baseball notation (e.g. {sample} = {int(sample)} + {int(frac*10)}/3 innings)")
            else:
                print(f"  → Looks like decimal notation (e.g. {sample} ≈ {sample:.4f} innings)")
        else:
            print("  → All whole innings this period; cannot determine format from sample.")
    else:
        print("  → No IP > 0 found for scoringPeriodId=%d" % scoring_period)

    print("\n─── Inspection complete. See outputs/endpoint_sample.json for full raw response. ───\n")


def classify_slot(slot_name: str, slot_id: int | None) -> str:
    """Classify a slot as Active / Bench / IL / Unknown."""
    name_upper = slot_name.upper()
    if any(n in name_upper for n in ("BE", "BENCH")):
        return "Bench"
    if any(n in name_upper for n in ("IL", " IR", "NA")):
        return "IL"
    # Known active slot name prefixes
    if any(name_upper.startswith(p) for p in ("C", "1B", "2B", "3B", "SS", "OF", "UTIL", "SP", "RP", "P")):
        return "Active"
    # Fallback by slot_id for common ESPN baseball slot IDs
    if slot_id is not None:
        if slot_id in (13, 14, 15, 16, 17, 20, 21):
            return "Bench" if slot_id not in (14,) else "IL"
    return "Unknown"


# ─────────────────────────── main ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ESPN Fantasy Baseball API endpoints.")
    parser.add_argument("--scoring-period", type=int, default=1,
                        help="Which scoringPeriodId to inspect (default: 1)")
    parser.add_argument("--show-raw", action="store_true",
                        help="Print full raw JSON to stdout (can be very long)")
    parser.add_argument("--dump-first-entry", action="store_true",
                        help="Print the full raw JSON of the first playerPoolEntry "
                             "(useful for diagnosing missing stats)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    config = load_config()
    base = BASE_URL.format(season=config["ESPN_SEASON_ID"], league_id=config["ESPN_LEAGUE_ID"])
    team_id = int(config["ESPN_TEAM_ID"])

    session = build_session(config["ESPN_SWID"], config["ESPN_S2"])

    # Never log the full espn_s2 value
    log.info("Loaded config: league=%s, season=%s, teamId=%s, SWID=%.8s…",
             config["ESPN_LEAGUE_ID"], config["ESPN_SEASON_ID"], config["ESPN_TEAM_ID"],
             config["ESPN_SWID"])

    slot_map = inspect_settings(session, base)

    inspect_scoring_period(
        session, base, team_id, args.scoring_period, slot_map,
        dump_first_entry=args.dump_first_entry,
    )

    if args.show_raw:
        sample = OUTPUT_DIR / "endpoint_sample.json"
        if sample.exists():
            print("\n─── Raw JSON ───")
            print(sample.read_text())


if __name__ == "__main__":
    main()
