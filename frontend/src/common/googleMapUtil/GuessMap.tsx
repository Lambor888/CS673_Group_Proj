import { useEffect, useRef, useState } from 'react'
import { loadGeometry, loadMaps } from './googleMapsLoader'
import { getRegionBounds, validateRegion } from './MapRegion'
import type { MapRegion } from './MapRegion'
import { highlightCountry } from './countryHighlight'
import './GuessMap.css'

interface Props {
  onGuessChange: (position: google.maps.LatLngLiteral) => void
  disabled?: boolean
  initialGuess?: google.maps.LatLngLiteral | null
  blank?: boolean
  fill?: boolean
  region?: MapRegion
  highlightRegion?: boolean
  restrictPan?: boolean
  restrictSelection?: boolean
  mapId?: string
  countryPlaceId?: string
  center?: google.maps.LatLngLiteral
  zoom?: number
  bounds?: google.maps.LatLngBoundsLiteral
  showSelection?: boolean
}

const blankStyles: google.maps.MapTypeStyle[] = [
  { featureType: 'all', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  ...['administrative', 'road', 'poi', 'transit'].map(featureType => ({
    featureType, stylers: [{ visibility: 'off' }],
  })),
  { featureType: 'landscape', elementType: 'geometry', stylers: [{ color: '#e8eddf' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#a9d7eb' }] },
]

export function GuessMap({ onGuessChange, disabled = false, initialGuess = null, blank = false, fill = false,
  region, highlightRegion = true, restrictPan = false, restrictSelection = false,
  mapId, countryPlaceId, center, zoom, bounds, showSelection = true }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<google.maps.Map | null>(null)
  const [countryStatus, setCountryStatus] = useState('')
  const cloudMapId = mapId?.trim() || undefined
  const countryId = countryPlaceId?.trim() || undefined
  const centerLat = center?.lat
  const centerLng = center?.lng
  const north = bounds?.north
  const south = bounds?.south
  const east = bounds?.east
  const west = bounds?.west
  const callback = useRef(onGuessChange)
  const [expanded, setExpanded] = useState(false)
  const [status, setStatus] = useState('Loading map…')
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(initialGuess)
  const [selectionMessage, setSelectionMessage] = useState('')
  // Equal inline region objects must not reload the map on every parent render.
  const regionJson = JSON.stringify(region ?? null)
  const initial = useRef(initialGuess)
  const disabledRef = useRef(disabled)
  useEffect(() => { disabledRef.current = disabled }, [disabled])
  useEffect(() => { callback.current = onGuessChange }, [onGuessChange])

  useEffect(() => {
    let cancelled = false
    let listener: google.maps.MapsEventListener | undefined
    let resizeObserver: ResizeObserver | undefined
    let pin: google.maps.OverlayView | undefined
    let regionLayer: google.maps.Data | undefined
    async function initialize() {
      try {
        setMap(null)
        setStatus('Loading map…')
        setSelectionMessage('')
        const currentRegion: MapRegion | null = JSON.parse(regionJson)
        if (currentRegion) validateRegion(currentRegion)
        const { Map, OverlayView, Data, Polygon } = await loadMaps()
        const geometry = currentRegion && restrictSelection ? await loadGeometry() : null
        if (cancelled || !container.current) return
        const bounds = currentRegion && restrictPan ? getRegionBounds(currentRegion) : null
        const map = new Map(container.current, {
          center: { lat: 20, lng: 0 }, zoom: 1, minZoom: 1,
          streetViewControl: false, mapTypeControl: false,
          fullscreenControl: false, zoomControl: true,
          gestureHandling: 'greedy', clickableIcons: false,
          // Cloud styling and inline styles cannot be used on the same map.
          ...(cloudMapId ? { mapId: cloudMapId } : { styles: blank ? blankStyles : undefined }),
          restriction: bounds ? { latLngBounds: bounds, strictBounds: true } : undefined,
        })
        if (bounds) map.fitBounds(bounds, 0)
        if (currentRegion && highlightRegion) {
          regionLayer = new Data({ map })
          for (const polygon of currentRegion.polygons) {
            regionLayer.add({ geometry: new Data.Polygon([polygon.outer, ...(polygon.holes ?? [])]) })
          }
          // Let clicks reach the map so highlighted areas remain selectable.
          regionLayer.setStyle({ fillColor: '#4f46e5', fillOpacity: 0.16,
            strokeColor: '#4f46e5', strokeWeight: 2, clickable: false })
        }
        const selectionPolygons = geometry && currentRegion ? currentRegion.polygons.map(p => ({
          outer: new Polygon({ paths: p.outer }),
          holes: (p.holes ?? []).map(hole => new Polygon({ paths: hole })),
        })) : []
        const allowed = (point: google.maps.LatLngLiteral) => !geometry || selectionPolygons.some(p =>
          (geometry.poly.containsLocation(point, p.outer) || geometry.poly.isLocationOnEdge(point, p.outer))
          && !p.holes.some(hole => geometry.poly.containsLocation(point, hole)
            || geometry.poly.isLocationOnEdge(point, hole)))
        // A lightweight overlay avoids requiring a separate map ID for a pin.
        class GuessPin extends OverlayView {
          point: google.maps.LatLng | null = null
          element = document.createElement('div')
          onAdd() {
            this.element.className = 'guess-map__pin'
            this.element.setAttribute('aria-label', 'Selected location')
            this.getPanes()?.overlayMouseTarget.append(this.element)
          }
          draw() {
            if (!this.point) return
            const pixel = this.getProjection().fromLatLngToDivPixel(this.point)
            if (pixel) {
              this.element.style.left = `${pixel.x}px`
              this.element.style.top = `${pixel.y}px`
            }
          }
          onRemove() { this.element.remove() }
        }
        const marker = new GuessPin()
        pin = marker
        if (initial.current && allowed(initial.current)) {
          marker.point = new google.maps.LatLng(initial.current)
          marker.setMap(map)
        } else {
          initial.current = null
          setGuess(null)
        }
        listener = map.addListener('click', (event: google.maps.MapMouseEvent) => {
          if (disabledRef.current || !event.latLng) return
          const selected = event.latLng.toJSON()
          if (!allowed(selected)) {
            setSelectionMessage(`Choose a location inside ${currentRegion?.name}.`)
            return
          }
          setSelectionMessage('')
          marker.point = event.latLng
          if (!marker.getMap()) marker.setMap(map)
          else marker.draw()
          initial.current = selected
          setGuess(selected)
          callback.current(selected)
        })
        resizeObserver = new ResizeObserver(() => {
          const center = map.getCenter()
          google.maps.event.trigger(map, 'resize')
          if (center) map.setCenter(center)
        })
        resizeObserver.observe(container.current)
        setMap(map)
        setStatus('')
      } catch {
        if (!cancelled) setStatus('Unable to load map. Please reload to try again.')
      }
    }
    void initialize()
    return () => {
      cancelled = true
      listener?.remove()
      resizeObserver?.disconnect()
      pin?.setMap(null)
      regionLayer?.setMap(null)
    }
  }, [blank, regionJson, highlightRegion, restrictPan, restrictSelection, cloudMapId])

  // Primitive dependencies prevent inline coordinates from resetting player panning
  // on unrelated parent renders (for example, a countdown tick).
  useEffect(() => {
    if (map && north !== undefined && south !== undefined && east !== undefined && west !== undefined
      && [north, south, east, west].every(Number.isFinite)
      && north > south && north <= 90 && south >= -90
      && east !== west && Math.abs(east) <= 180 && Math.abs(west) <= 180) {
      map.fitBounds({ north, south, east, west }, 32)
    }
  }, [map, north, south, east, west])

  useEffect(() => {
    if (map && centerLat !== undefined && centerLng !== undefined
      && Number.isFinite(centerLat) && Math.abs(centerLat) <= 90
      && Number.isFinite(centerLng) && Math.abs(centerLng) <= 180) {
      map.setCenter({ lat: centerLat, lng: centerLng })
    }
  }, [map, centerLat, centerLng])

  useEffect(() => {
    if (map && zoom !== undefined && Number.isFinite(zoom) && zoom >= 1) map.setZoom(zoom)
  }, [map, zoom])

  useEffect(() => {
    if (!map || !cloudMapId || !countryId) return
    return highlightCountry(map, countryId, setCountryStatus)
  }, [map, cloudMapId, countryId])

  const countryMessage = countryId
    ? (!cloudMapId ? 'Country highlighting requires a mapId.' : countryStatus)
    : ''

  return <section className={`guess-map${expanded ? ' guess-map--expanded' : ''}${fill ? ' guess-map--fill' : ''}`} aria-label="Choose a location on the world map">
    <div className="guess-map__toolbar">
      <span>{region?.name ?? 'World map'}</span>
      {!fill && <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Collapse map' : 'Expand map'}
      </button>}
    </div>
    <div className="guess-map__body">
      <div ref={container} className="guess-map__canvas" />
      {status && <p className="guess-map__status" role="status">{status}</p>}
    </div>
    {(showSelection || countryMessage) && <p className="guess-map__selection" aria-live="polite">
      {countryMessage && <span>{countryMessage} </span>}
      {showSelection && <>
        {selectionMessage && <span>{selectionMessage} </span>}
        {guess ? `${guess.lat.toFixed(5)}, ${guess.lng.toFixed(5)}` : 'Click the map to place your pin'}
      </>}
    </p>}
  </section>
}
