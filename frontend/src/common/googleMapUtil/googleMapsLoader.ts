import { importLibrary, setOptions } from '@googlemaps/js-api-loader'

let configured = false

function configureLoader(): void {
  if (configured) return

  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim()
  if (!key) {
    throw new Error('Missing VITE_GOOGLE_MAPS_API_KEY. Set it in frontend/.env.local and restart Vite.')
  }

  setOptions({ key, v: 'weekly' })
  configured = true
}

// The official loader shares the SDK script across concurrent library requests.
// Importing this module alone does not load Google Maps or create a map.
export async function loadMaps(): Promise<google.maps.MapsLibrary> {
  configureLoader()
  return importLibrary('maps')
}

export async function loadStreetView(): Promise<google.maps.StreetViewLibrary> {
  configureLoader()
  return importLibrary('streetView')
}

export async function loadMaps3D(): Promise<google.maps.Maps3DLibrary> {
  configureLoader()
  return importLibrary('maps3d')
}
