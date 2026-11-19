# Capital Finder

Open `/capitalfinder`. One in-memory game per user contains both round types.
For every new round, the backend randomly selects map or text mode with equal
probability (50% each). Consecutive rounds may have the same mode.

- Map round: select the capital's location on a blank world map.
- Text round: view a highlighted country and type its capital.

The frontend renders the server's `mode` and has no mode selector or URL-based
mode override. Refresh/resume/poll preserves the existing round and its mode.
Both round types share the round counter, used-country set, and total score.

Both modes have unlimited rounds and the existing server-side `ROUND_SECONDS`
deadline (currently 60 seconds). Scores are not written to profile/history tables.
Sessions are lost on server restart and require a single server worker.

## Country pool

`location/capitals.json` contains a curated set of 100 relatively familiar
countries, reduced from the original 195. This is a gameplay selection, not an
official ranking by population, area, or popularity. Familiar smaller countries
such as New Zealand, Norway, Switzerland, Singapore, and Iceland are retained.
The retained capital names, coordinates, multiple-capital answers, and country
ordering are unchanged. Both round types use this same pool; a new cycle begins
after all 100 countries have been used. Restart the backend to load dataset edits.

## Google setup for name mode

1. In the backend key's Google Cloud project, enable **Geocoding API** and allow
   that API in the key's API restrictions. Keep Street View Static API enabled
   for existing street-view games. Use the server key in `backend/.env` as
   `GOOGLE_MAPS_API_KEY`; never send it to the frontend.
2. The browser key continues to use Maps JavaScript API. Its project must contain
   a JavaScript Vector Map ID associated with a light blank style and an enabled
   **Country** feature layer.
3. The frontend defaults to the configured public Map ID
   `8a4f58eaf6594d8cc0cd3856`. Another deployment can override it with
   `VITE_GOOGLE_MAPS_BOUNDARY_MAP_ID` in `frontend/.env.local`, then restart Vite.

The location module queries Google Geocoding with `components=country:XX`,
verifies the result is the requested country, and returns its Place ID and display
viewport. It caches successful results in memory for 24 hours. Only name mode
uses this API; requests to poll/submit/resume reuse the current round's data.
No capital names or capital coordinates are sent before the player submits.
Google boundary coverage varies; a country Place ID does not guarantee its
Country-layer polygon is supported. The common map shows unavailable-layer errors.

## Endpoints

All endpoints require the existing Bearer token.

| Method | Path | Body / purpose |
| --- | --- | --- |
| POST | `/capfinder/round` | `{ "previous_round_id": null }` starts/resumes; pass the finished round ID to advance. The server selects the new mode. |
| GET | `/capfinder` | Current round state; also applies server timeout. |
| POST | `/capfinder/round/{id}/guess` | `{ "lat": ..., "lng": ... }`, accepted only for a map round. |
| POST | `/capfinder/round/{id}/answer` | `{ "answer": "Paris" }`, accepted only for a text round. |

Requests cannot supply a `mode` field. The old `/capfinder/text` routes have been
removed; neither endpoint choice nor query parameters can change a round's mode.

State includes `mode`, `country`, `country_place_id`, `country_bounds`, `round_id`,
`number`, `seconds_left`, `finished`, `total_score`, `score`, `distance_km`,
`guess`, `submitted_answer`, and `correct`. Name mode never uses `guess`.
The Place ID and bounds are null in map mode. `correct` is null before answering
or on timeout, false for an incorrect answer, and true for a correct answer.

## Name comparison and scoring

- Strip leading/trailing whitespace and compare with `casefold()` against every
  capital name stored for the country in `location/capitals.json`.
- Case does not matter. Spelling, accents and punctuation still matter; there is
  no translation, fuzzy matching, or extra alias list.
- A match calls `haversine_distance(lat, lng, lat, lng)`, then
  `single_player_round_score(0)` for the current full score of 5000.
- A wrong answer ends the round with 0 points. Timeout also gives 0 points.
- Empty/oversized answers are rejected. Completed submissions are idempotent;
  retrying cannot change the result or award points again. Stale/wrong-user round
  IDs and cross-mode submissions are rejected.

Country lookup failures while creating a text round return 503 with a safe
setup/network message. They do not advance the round counter or change accumulated
score. Map rounds do not perform the lookup. The browser allows retrying.

Tests (from `backend`):
`python -m pytest tests/test_capfinder.py tests/test_country_lookup.py tests/test_locations.py tests/test_scoring.py -q`
