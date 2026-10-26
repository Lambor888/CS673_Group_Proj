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

The map starts at a global view independent of the street-view location. Players
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

## Loading libraries for a new component

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
