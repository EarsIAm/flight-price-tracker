# London → Alicante / Murcia daily flight price tracker

A self-running daily price logger for **2 adults, London → Alicante (ALC) or
Murcia (RMU), return flights 2–16 July 2026, 5–7 nights**. Runs on GitHub Actions
(no PC required) and commits a versioned CSV log back to the repo. Packages are
handled separately — see `PACKAGE_CHECKLIST.md` and the honest note below.

## What's automated vs. what isn't

| | Channel | Automated? | Where logged |
|---|---|---|---|
| ✅ | DIY return flights (incl. Ryanair/easyJet/Jet2) | Yes, daily | `flights_log.csv` |
| ✋ | AI packages (Jet2holidays/TUI/loveholidays/On the Beach) | No — no public API, anti-bot | `packages_log.csv` (manual, 2×/week) |

**Read this honestly:** for All-Inclusive on the Costa Blanca, the *package* is
usually the cheaper product. The automated flight log is your **DIY ceiling and
trend line**, not the likely winner. Don't let the part that was easy to automate
fool you into thinking it's finding the best deal.

## One-time setup (~15 min)

You'll create two accounts yourself — I can't and shouldn't do that for you.

1. **Apify account + token**
   - Sign up at apify.com (free; the actor used here is ~$0.0003/search with a $5 trial).
   - **Settings** (gear, bottom of left sidebar) → **API & Integrations** tab → click the
     **copy** icon next to your token. (Not the Actors → Integrations page — that's
     Actor-to-Actor workflows.) Treat the token like a password.
   - The actor's input/output schema has already been matched in `search.py`
     (verified Apr 2026). You only need to touch `build_actor_input()` /
     `normalise_item()` if a future actor version changes its fields.

2. **GitHub repo**
   - Create a **new repository**. **Recommend making it PUBLIC** — the price log
     isn't sensitive, and public repos get **unlimited** Actions minutes. (Private
     repos have a 2,000 min/month free quota; the default grid uses ~80 min/day, so
     on a private repo trim `TRIP_NIGHTS = [7]` in `search.py` to stay well under it.)
   - Upload all files from this folder (keep the `.github/workflows/` path intact).
   - Repo → **Settings → Secrets and variables → Actions → New repository secret**:
     name `APIFY_TOKEN`, value = your Apify token.
   - Repo → **Settings → Actions → General → Workflow permissions** → enable
     **Read and write permissions** (so the job can commit the log back).

3. **First run**
   - Repo → **Actions** tab → **daily-flight-search** → **Run workflow** (manual).
   - Check the run log. Success → `flights_log.csv` gets rows and is committed.
   - No rows? It writes `debug_last_raw.json` — that's the actor's real output shape.
     Match `normalise_item()` to it and re-run.

After that it runs itself at 06:17 UTC daily. *Caveat:* GitHub auto-disables
scheduled workflows after 60 days of **no repo activity** — but each daily commit
counts as activity, so a working tracker keeps itself alive.

## Tuning cost & runtime (`search.py` CONFIG block)

| Lever | Effect |
|---|---|
| `TRIP_NIGHTS = [7]` | ~3× fewer searches; fits a private repo's free quota |
| Fewer `ORIGINS` | Linear cut in searches; drop LTN if STN/LGW suffice |
| `cron` schedule | One snapshot/day is the design; add a second time if you want AM/PM |
| `MAX_SEARCHES` | Hard guard so a config slip can't run up cost or time |

Default grid = 3 origins × 2 dests × 27 date pairs = **162 searches/day ≈ £0.04/day**.

## Reading the log

`flights_log.csv` is one row per search, append-only, pivot-ready:

- Filter `is_cheapest_this_run = YES` for the single best fare each day → chart
  `best_price` against `search_date` to see the trend.
- Pivot by `origin` / `destination` to see which airport-pair wins.
- `booking_link` takes you to the source to verify the live price before paying
  (always re-check baggage/seat fees — the logged price is base fare).

**Settle these two from your first real run (the actor docs don't state them):**
1. Is `best_price` the **round-trip total** or one-way? Compare a logged value
   against the same search done by hand on Google Flights.
2. Is it **per-person** or for both passengers? The `adults` column is logged
   alongside so you can tell. Once known, add a derived per-person/total column
   in Excel — I deliberately did not compute one, to avoid baking in a wrong `/2`.

## When it breaks

A community scraper *will* occasionally break when sites change. Symptoms and fixes:
- **No rows + `debug_last_raw.json` written** → output schema changed; update `normalise_item()`.
- **HTTP errors in the run log** → check the actor still exists / your token is valid.
- **Want a different source** → replace `call_actor()` + `build_actor_input()` only;
  the rest of the pipeline is source-agnostic. SerpApi's Google Flights API is a
  more stable (paid) swap, but note it still won't carry Ryanair.
