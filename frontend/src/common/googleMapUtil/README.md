# Using the Google Maps components

## Before using a component

Enable Maps JavaScript API in the Google Cloud project associated with your browser
key. Set the key in `frontend/.env.local` and restart Vite:

```dotenv
VITE_GOOGLE_MAPS_API_KEY=your_browser_api_key
```

Restrict the browser key to Maps JavaScript API and your website origins. For local
development, allow both `http://localhost:5173/*` and `http://127.0.0.1:5173/*`.
The key is visible to the browser; do not use a server key here.

Both components load the SDK and import their own CSS automatically. You do not
need to call the loader yourself or add a Google Maps script to `index.html`.

## StreetViewPanel: display a street view

Import from a feature folder directly under `src/features/`:

```tsx
import { StreetViewPanel } from '../../common/googleMapUtil/StreetViewPanel'

export function StreetViewExample() {
  return (
    <div style={{ height: 600 }}>
      <StreetViewPanel position={{ lat: 40.7580, lng: -73.9855 }} />
    </div>
  )
}
```

Pass exactly one of these props:

| Prop | Type | Meaning |
| --- | --- | --- |
| `panoId` | `string` | Display an exact backend-selected panorama. **Game rounds use this**, so the answer's coordinates are never sent to the browser before the guess. |
| `position` | `{ lat: number; lng: number }` | Latitude and longitude in degrees used to search for nearby imagery. |

When `panoId` is absent, the component searches within 150 meters for the nearest official Google outdoor
panorama. It supports looking around, zooming, and moving along available street
links. Changing either coordinate starts a new lookup and recreates the viewer.

Give its parent an explicit height: the viewer fills 100% of its parent's width
and height. It displays a message if the lookup or SDK loading fails.

When searching by coordinates, the displayed panorama may be offset from the
supplied coordinates. The component does not report its actual coordinates to the
parent. For scoring, supply the backend-selected `panoId` and use the actual
starting coordinates saved by the game service. Heading and movement options are
not currently exposed as props.

## GuessMap: let the player select a location

Optional props `blank` and `fill` default to `false`:

```tsx
<GuessMap blank fill onGuessChange={setGuess} disabled={submitted} />
```

Without a `mapId`, `blank` hides geographic labels, administrative boundaries, roads, transit and
POIs, retaining land/water shapes and pan/zoom/click interaction. Google attribution
and required controls remain visible. `fill` fills an explicitly sized parent and
hides the expand/collapse button. Existing street-view minimaps keep their defaults.
Use the round ID as the React `key` to clear the pin and reset the viewport each round.

```tsx
import { useState } from 'react'
import { GuessMap } from '../../common/googleMapUtil/GuessMap'

export function GuessExample() {
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)

  return (
    <div>
      <GuessMap onGuessChange={setGuess} />
      <button type="button" disabled={!guess} onClick={() => {
        if (guess) console.log('Selected coordinates:', guess)
      }}>
        Use selected location
      </button>
    </div>
  )
}
```

| Required prop | Type | Meaning |
| --- | --- | --- |
| `onGuessChange` | `(position: google.maps.LatLngLiteral) => void` | Called after every map click with `{ lat, lng }`. |

By default the map starts at a global view independent of the street-view location. Players
can drag, zoom, expand/collapse, and click to place or move a single pin. The
component manages its pin and displays the selected coordinates internally.

The parent should save the callback value for later submission. The component does
not submit guesses, calculate scores, or enforce game rules. Set `disabled` to
prevent new selections while submitting or after completion. Use `initialGuess`
to restore a pin on mount; it is not a controlled value prop. To clear the map for a new round, remount it
using a different React key and clear the parent's guess as part of that round
transition:

```tsx
<GuessMap key={roundId} onGuessChange={setGuess} />
```

Remounting creates a new Google map instance, so do not change the key on every
render or countdown tick.

## Position the map (Feature 12)

Pass `center` and/or `zoom` to position the view. These do not place a guess pin,
submit a guess, or restrict dragging/selection. No Map ID is needed for positioning.

```tsx
<GuessMap
  center={{ lat: 40.742, lng: -74.179 }}
  zoom={16}
  onGuessChange={setGuess}
/>
```

| Optional prop | Default | Behavior |
| --- | --- | --- |
| `center` | Initial `{ lat: 20, lng: 0 }` | Recenter when the latitude/longitude values change. Valid finite ranges: latitude -90 to 90, longitude -180 to 180. |
| `zoom` | Initial `1` | Update zoom when its value changes. Must be finite and at least 1; Google limits the available maximum. |
| `bounds` | Absent | Fit a `{ north, south, east, west }` rectangle with 32px padding when its values change. Useful for displaying a whole country, including small countries. |
| `showSelection` | `true` | Set false for a display-only map to hide the pin instructions/coordinates. Configuration warnings remain visible. Use `disabled` too to prevent selections. |

Updates reuse the map and preserve its selected pin. Passing an equal inline
`center` object on a parent rerender does not reset the user's pan or zoom.
Invalid values are ignored. Removing either prop leaves the current view alone.
If using `region` + `restrictPan`, explicit center/zoom are applied after the
initial region fit, and Google's region restriction still constrains the view.
Prefer either `bounds` or `center`/`zoom`. On initialization explicit center/zoom
are applied after bounds; later changes update only the values that changed.

## Highlight one country using Google boundaries (Feature 13)

This is separate from positioning. Pass both `mapId` and `countryPlaceId`:

```tsx
<GuessMap
  mapId="8a4f58eaf6594d8cc0cd3856"
  countryPlaceId={country.placeId}
  center={country.center}
  zoom={country.zoom}
  fill
  onGuessChange={setGuess}
/>
```

`country` above is caller-supplied data. `placeId` must identify the **country** in
Google Maps, not its capital, country name, ISO code, Map ID, or Style ID. The
component does not look up Place IDs or call Places/Geocoding. Capital finder's
name mode gets `country_place_id` and `country_bounds` from its backend; map mode
does not perform that lookup.

| Optional prop | Default | Behavior |
| --- | --- | --- |
| `mapId` | Absent | Opt this map into the associated Google Cloud style. Must belong to the browser key's project and use JavaScript Vector with the Country feature layer enabled. |
| `countryPlaceId` | Absent | Draw a purple outline for only this country, with transparent fill. Changing it replaces the old outline; removing it clears the highlight. Requires `mapId`. |

Use the `capital-finder-blank` cloud style associated with the Map ID above to hide
all ordinary labels and administrative borders. With `mapId`, the cloud style
controls the base map and the inline `blank` style is not applied (Google does
not support both together). Without `mapId`, existing `blank` behavior is unchanged.
The API key and SDK loader are unchanged; no extra key or package is needed.

The Country layer is optional: if unavailable, a message appears beside the
selection text while the map remains usable. The component retries styling when
Google reports capability changes after loading. An invalid/unsupported country's
Place ID simply produces no outline; layer availability does not verify an ID.

Changing country, center or zoom does not recreate the map. Changing `mapId` does,
because Google does not allow replacing a map's ID after initialization.
Country highlighting does not automatically center/zoom, restrict movement, or
check whether a guess is inside a country. For display-only capital questions,
use `disabled` to prevent pin placement. Existing single/multiplayer and capital
finder map-mode callers continue using their previous configurations.

Setup references: [Google boundary setup](https://developers.google.com/maps/documentation/javascript/dds-boundaries/start)
and [styling a boundary](https://developers.google.com/maps/documentation/javascript/dds-boundaries/style-polygon).

## Put both components in one game area

Use a positioned DOM container, not an HTML `<canvas>` element. The street view
fills the container and the guess map is positioned above it in the bottom-right
corner. Keep top and bottom page slots outside this container.

```tsx
import { useState } from 'react'
import { StreetViewPanel } from '../../common/googleMapUtil/StreetViewPanel'
import { GuessMap } from '../../common/googleMapUtil/GuessMap'
import './MapExample.css'

export function MapExample() {
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)

  return (
    <main>
      <header style={{ height: 80 }} />
      <div className="map-example" data-has-guess={guess !== null}>
        <StreetViewPanel position={{ lat: 40.7580, lng: -73.9855 }} />
        <div className="map-example__guess">
          <GuessMap onGuessChange={setGuess} />
        </div>
      </div>
      <footer style={{ height: 80 }} />
    </main>
  )
}
```

Create `MapExample.css` beside the example component:

```css
.map-example {
  position: relative;
  isolation: isolate;
  container-type: size;
  height: max(440px, calc(100dvh - 160px));
  overflow: hidden;
}

.map-example__guess {
  position: absolute;
  z-index: 2;
  right: 16px;
  bottom: 40px;
}

.map-example .guess-map {
  width: min(340px, calc(100cqw - 32px));
}

.map-example .guess-map--expanded {
  width: min(640px, calc(100cqw - 32px));
}

.map-example .guess-map__body {
  height: min(220px, calc(100cqh - 140px));
}

.map-example .guess-map--expanded .guess-map__body {
  height: min(420px, calc(100cqh - 140px));
}
```

The explicit overlay layer keeps the guess map above Google's internal layers.
The bottom gap leaves the Street View attribution visible. Container-relative
sizes keep the expanded map within the game area on smaller screens.

The project already implements this composition in
`src/features/singlePlayer/GameCanvas.tsx`. Its parent, `SinglePlayerPage.tsx`,
provides the panorama id, stores the guess, and reserves the top/bottom space.

## Region boundaries and interaction limits

Import the shared `MapRegion` type from `./MapRegion` (relative to this folder).
Each region has an `id`, a display `name`, and one or more polygons. Each polygon
has an ordered `outer` coordinate array and optional `holes` arrays. Coordinates
use `{ lat, lng }`, not GeoJSON's `[longitude, latitude]` order. Rings must be
simple and non-self-intersecting; holes must lie inside their outer ring.
You can repeat the first coordinate at the end, but it is not required.

```tsx
import { GuessMap } from '../../common/googleMapUtil/GuessMap'
import type { MapRegion } from '../../common/googleMapUtil/MapRegion'

// Illustrative rectangle only; replace with your actual campus/country boundary.
const region: MapRegion = {
  id: 'example-area',
  name: 'Example area',
  polygons: [{ outer: [
    { lat: 40.740, lng: -74.183 },
    { lat: 40.744, lng: -74.183 },
    { lat: 40.744, lng: -74.176 },
    { lat: 40.740, lng: -74.176 },
  ] }],
}

<GuessMap
  key={region.id}
  region={region}
  highlightRegion
  restrictPan
  restrictSelection
  onGuessChange={setGuess}
/>
```

| Prop | Default | Behavior |
| --- | --- | --- |
| `region` | absent | Region geometry supplied by the caller; no boundary lookup is performed. |
| `highlightRegion` | `true` | When a region is provided, draw purple borders and translucent fill. Set false to hide the drawing while keeping limits. |
| `restrictPan` | `false` | Fit and restrict the map to the region's enclosing **rectangle**, including zoom-out restrictions. It does not constrain the viewport to the exact polygon. |
| `restrictSelection` | `false` | Only accept clicks in an outer polygon and outside every hole of that polygon. Outer edges are accepted; hole edges are excluded. Rejected clicks preserve the previous pin and do not call `onGuessChange`. |

All three options are independent. Without `region`, none has any effect.
`blank` and `fill` still work with regions. Highlighting does not intercept clicks.
The toolbar displays the region name. The geometry library is loaded only when
region-restricted selection is enabled; it needs no extra API key or map ID.

When changing the playable region, use `key={region.id}` and clear the parent's
stored guess too. Invalid initial pins are not drawn when selection is restricted.
Use normal local/country polygons (split global shapes if needed); enclosing
bounds support islands and crossings of the 180-degree meridian. Validation checks
coordinates and ring lengths, not self-intersections or hole topology.

These are UI restrictions. Any game that requires authoritative geographic checks
must also validate submitted coordinates on its backend.

Run the bounds/validation tests from `frontend`:
`node --experimental-strip-types --test tests/mapRegion.test.ts`.

## SDK library helpers

Only call these utilities directly when writing another Google Maps component:

| Function | Returned library | Use |
| --- | --- | --- |
| `loadMaps()` | `google.maps.MapsLibrary` | Maps and overlays |
| `loadStreetView()` | `google.maps.StreetViewLibrary` | Street View lookup and display |
| `loadMaps3D()` | `google.maps.Maps3DLibrary` | A future 3D map component |

```ts
import { loadMaps3D } from '../../common/googleMapUtil/googleMapsLoader'

const { Map3DElement } = await loadMaps3D()
```

These async functions load libraries; they do not create a visible view. Catch
rejections in the calling component, create the view after its DOM container
mounts, and clean up listeners on unmount. No 3D React component exists yet.
