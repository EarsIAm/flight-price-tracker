# Package check protocol (the channel that usually wins)

The automated flight log is your **DIY ceiling**. For All-Inclusive on the Costa
Blanca, tour-operator packages are usually **cheaper** than DIY flight + AI hotel,
because operators buy AI board basis in bulk. None of them expose a public API and
all run anti-bot protection, so this stays a manual job. Do it **twice a week**
(Tuesday and Friday are reasonable; midweek listings often read cheaper) and log
each run into `packages_log.csv` so it sits alongside the automated flight data.

## The four to check

| Operator | Site | Why it's on the list |
|---|---|---|
| Jet2holidays | jet2holidays.com | Strong Costa Blanca AI, flies from multiple London-ish bases |
| loveholidays | loveholidays.com | Aggressive AI pricing, wide hotel range |
| On the Beach | onthebeach.co.uk | Good for splitting flight/hotel, ABTA-style protection |
| TUI | tui.co.uk | Own hotels, sometimes undercuts on AI |

## Fixed search parameters (use the same every time)

- **From:** London (select all London airports if the site allows; otherwise check Gatwick + Stansted + Luton)
- **To:** Alicante / Costa Blanca region (resorts from Alicante down to Torrevieja: Benidorm, La Marina, Guardamar, Torrevieja, La Mata)
- **Board:** All Inclusive
- **Guests:** 2 adults
- **Nights:** 7 (then re-run for 5 if you want the shorter option)
- **Departure window:** flexible, 2–16 July 2026 (use the site's "flexible dates / cheapest month" view if offered)
- **Star rating:** filter to 3★+

## What to record (one row per genuinely competitive result)

Log the **cheapest** result per operator each run, plus any standout (e.g. a 4★ only
slightly above the cheapest 3★). Columns mirror `packages_log.csv`:

`search_date, operator, hotel_name, star_rating, resort, nights, outbound_date, return_date, board, price_total_gbp, price_pp_gbp, booking_link, notes`

## The comparison that actually matters

Each time you log, compare:

```
cheapest_package_total   (from packages_log.csv, this run)
vs.
cheapest_flight_total    (from flights_log.csv, is_cheapest_this_run = YES)
                         + an AI hotel estimate for the same dates
```

If the package beats flight + hotel — which it usually will for AI — the package is
your answer and the flight log is just confirming you're not overpaying. If DIY ever
undercuts the package, that's the signal worth acting on. Either way you now have a
dated, side-by-side record instead of a gut feeling.

## Booking-time reminders (from your earlier travel work)

- Pay by **credit card** (Section 75 cover over £100).
- A package booked through an ATOL/ABTA operator carries protection a DIY flight does not.
- Hold off on non-refundable add-ons (seats, golf/sports baggage) until dates are locked.
