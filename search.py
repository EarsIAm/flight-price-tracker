#!/usr/bin/env python3
"""
Daily flight price logger: London -> Alicante (ALC) / Murcia (RMU)

WHAT THIS DOES
--------------
For a configurable grid of (origin airport x destination x outbound date x trip
length), it asks a multi-source flight-price scraper for the cheapest return fare
for 2 adults and appends one row per search to flights_log.csv. The cheapest
result of each daily run is flagged so you can chart the trend without filtering.

WHY A SCRAPER AND NOT AMADEUS
-----------------------------
The cheapest London->Alicante fares are Ryanair / easyJet / Jet2. GDS-based APIs
(Amadeus) do not carry Ryanair inventory, so they would produce a biased log that
looks authoritative but omits the likely-cheapest carrier. The scraper below pulls
Google Flights + Ryanair + easyJet + Wizz + Norwegian + Kiwi in one call.

WHAT THIS DOES *NOT* DO
-----------------------
It does NOT see tour-operator packages (Jet2holidays, TUI, loveholidays, On the
Beach). For an All-Inclusive Costa Blanca holiday those are usually CHEAPER than
DIY flight+hotel. Treat this log as your DIY *ceiling*. The real bargain hunting
happens in PACKAGE_CHECKLIST.md, logged manually into packages_log.csv.

DATA SOURCE
-----------
Apify actor "makework36/flight-price-scraper" called via the run-sync endpoint.
The actor's exact input/output field names are NOT guaranteed stable. If a run
produces no parsed rows, check debug_last_raw.json (written on parse failure) and
adjust normalise_item() / build_actor_input() to match the live schema. This is
the ONE place coupled to the third-party source.
"""

from __future__ import annotations
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
# CONFIG  -- edit these; everything below is mechanism, not policy
# --------------------------------------------------------------------------- #
ORIGINS = ["LGW", "STN", "LTN"]      # London airports that realistically serve ALC/RMU cheaply.
                                     # Add "SEN" (Southend) if you want; each origin multiplies cost.
DESTINATIONS = ["ALC", "RMU"]        # Alicante, Murcia (Corvera)

WINDOW_START = date(2026, 7, 2)      # earliest outbound
WINDOW_END   = date(2026, 7, 16)     # latest acceptable return ("approx" -> nudge if you like)
TRIP_NIGHTS  = [5, 6, 7]             # acceptable trip lengths. Drop to [7] to cut cost/runtime ~3x.

ADULTS = 2
CURRENCY = "GBP"

# Cost / runtime guard. Each search is ~1 actor run (~20-60s) at ~$0.0003.
# Default grid below is ~ (3 origins x 2 dests x ~27 date pairs) = ~162 searches/day.
# That is ~5 cents/day but ~80 min of Actions time. See README for the public-repo note.
MAX_SEARCHES = 200                   # hard stop so a config slip cannot run up cost/time

APIFY_ACTOR_ID = "makework36~flight-price-scraper"   # NB: API uses '~' where the URL shows '/'
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")      # set as a GitHub Actions secret

LOG_PATH = Path(__file__).with_name("flights_log.csv")
DEBUG_RAW_PATH = Path(__file__).with_name("debug_last_raw.json")

CSV_FIELDS = [
    "run_timestamp_utc", "search_date", "origin", "destination",
    "outbound_date", "return_date", "nights",
    "best_price", "currency", "adults",
    "airline", "stops", "depart_time", "route",
    "source", "booking_link", "is_cheapest_this_run",
]


# --------------------------------------------------------------------------- #
# DATE GRID
# --------------------------------------------------------------------------- #
def date_pairs() -> list[tuple[date, date]]:
    """All (outbound, return) pairs where both legs fall inside the window
    and the trip length is one of TRIP_NIGHTS."""
    pairs: list[tuple[date, date]] = []
    out = WINDOW_START
    while out <= WINDOW_END:
        for n in TRIP_NIGHTS:
            ret = out + timedelta(days=n)
            if ret <= WINDOW_END:
                pairs.append((out, ret))
        out += timedelta(days=1)
    return pairs


# --------------------------------------------------------------------------- #
# DATA SOURCE ADAPTER  -- the only code coupled to the third-party scraper
# --------------------------------------------------------------------------- #
def build_actor_input(origin: str, dest: str, out_d: date, ret_d: date) -> dict:
    """Translate one search into the actor's input JSON.
    Field names verified against the actor's documented input schema (Apr 2026)."""
    return {
        "origin": origin,
        "destination": dest,
        "departDate": out_d.isoformat(),       # actor field is departDate, NOT departureDate
        "returnDate": ret_d.isoformat(),
        "adults": ADULTS,
        "cabinClass": "ECONOMY",
        "currency": CURRENCY,
        "maxFlights": 10,                      # results arrive sorted cheapest-first; 10 is ample
    }


def call_actor(actor_input: dict) -> list[dict]:
    """Run the actor synchronously and return its dataset items (list of dicts)."""
    url = (
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}"
        f"/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    )
    resp = requests.post(url, json=actor_input, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    # The endpoint returns the dataset items array directly.
    return data if isinstance(data, list) else data.get("items", [])


def _first(d: dict, *keys, default=None):
    """Return the first present, non-null key from d (schema-tolerant)."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _pick_link(item: dict, source: str) -> str:
    """`links` is a dict keyed by source (googleFlights/kiwi/ryanair/...).
    Prefer the link matching the cheapest source; fall back to any link."""
    links = item.get("links")
    if isinstance(links, dict) and links:
        if source:
            for k, v in links.items():
                if source.lower() in k.lower() and v:
                    return v
        return next((v for v in links.values() if v), "")
    return _first(item, "bookingLink", "booking_link", "deepLink", "url", default="")


def normalise_item(item: dict, origin: str, dest: str,
                   out_d: date, ret_d: date, nights: int) -> dict | None:
    """Map one raw actor result to our CSV schema, using the actor's documented
    output fields (bestPrice, cheapestSource, airline, stops, departTime,
    from/to, links). Returns None if no usable price.

    NOT documented, so confirm on the FIRST real run via debug_last_raw.json:
      (1) is `bestPrice` the round-trip TOTAL or one-way?
      (2) is it PER-PERSON or for all `adults`?
    We log best_price as-is plus adults so the data settles both questions."""
    price = _first(item, "bestPrice", "price", "totalPrice")
    if price is None:
        return None
    try:
        price = round(float(str(price).replace(",", "").replace("£", "").strip()), 2)
    except ValueError:
        return None

    source = _first(item, "cheapestSource", "source", "provider", default="")
    frm = item["from"].get("airport", origin) if isinstance(item.get("from"), dict) else origin
    to = item["to"].get("airport", dest) if isinstance(item.get("to"), dict) else dest

    return {
        "origin": origin,
        "destination": dest,
        "outbound_date": out_d.isoformat(),
        "return_date": ret_d.isoformat(),
        "nights": nights,
        "best_price": price,
        "currency": _first(item, "currency", default=CURRENCY),
        "adults": ADULTS,
        "airline": _first(item, "airline", default=""),
        "stops": _first(item, "stops", default=""),
        "depart_time": _first(item, "departTime", "departDate", default=""),
        "route": f"{frm}-{to}",
        "source": source or "scraper",
        "booking_link": _pick_link(item, source),
    }


# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #
def main() -> int:
    if not APIFY_TOKEN:
        print("ERROR: APIFY_TOKEN not set. In GitHub: Settings > Secrets and "
              "variables > Actions > New repository secret.", file=sys.stderr)
        return 1

    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = date.today().isoformat()
    pairs = date_pairs()
    searches = [(o, d, od, rd) for o in ORIGINS for d in DESTINATIONS for (od, rd) in pairs]

    print(f"Planned searches: {len(searches)} "
          f"({len(ORIGINS)} origins x {len(DESTINATIONS)} dests x {len(pairs)} date pairs)")
    if len(searches) > MAX_SEARCHES:
        print(f"ERROR: {len(searches)} searches exceeds MAX_SEARCHES={MAX_SEARCHES}. "
              f"Trim ORIGINS / TRIP_NIGHTS or raise the cap deliberately.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    last_raw = None
    for i, (origin, dest, out_d, ret_d) in enumerate(searches, 1):
        nights = (ret_d - out_d).days
        try:
            items = call_actor(build_actor_input(origin, dest, out_d, ret_d))
            last_raw = items
            # Keep only the cheapest parsed result for this exact search.
            parsed = [r for it in items if (r := normalise_item(it, origin, dest, out_d, ret_d, nights))]
            if parsed:
                best = min(parsed, key=lambda r: r["best_price"])
                rows.append(best)
                print(f"[{i}/{len(searches)}] {origin}->{dest} {out_d}/{ret_d} "
                      f"({nights}n): {CURRENCY} {best['best_price']} via {best['source']}")
            else:
                print(f"[{i}/{len(searches)}] {origin}->{dest} {out_d}/{ret_d}: no parsable result")
        except Exception as e:  # noqa: BLE001 - we want one bad search not to kill the run
            print(f"[{i}/{len(searches)}] {origin}->{dest} {out_d}/{ret_d}: ERROR {e}", file=sys.stderr)
        time.sleep(1)  # gentle pacing

    if not rows:
        # Dump whatever we last saw so the schema can be inspected and the adapter fixed.
        DEBUG_RAW_PATH.write_text(json.dumps(last_raw, indent=2, default=str))
        print(f"No rows logged this run. Wrote raw sample to {DEBUG_RAW_PATH.name} "
              f"for schema inspection.", file=sys.stderr)
        return 2

    # Flag the cheapest of the whole run.
    cheapest = min(rows, key=lambda r: r["best_price"])
    for r in rows:
        r["is_cheapest_this_run"] = "YES" if r is cheapest else ""
        r["run_timestamp_utc"] = run_ts
        r["search_date"] = today

    write_header = not LOG_PATH.exists()
    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            w.writeheader()
        w.writerows(rows)

    print(f"\nLogged {len(rows)} rows. Cheapest today: {CURRENCY} {cheapest['best_price']} "
          f"({cheapest['origin']}->{cheapest['destination']} "
          f"{cheapest['outbound_date']}/{cheapest['return_date']} via {cheapest['source']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
