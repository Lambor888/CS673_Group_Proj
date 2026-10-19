import { useEffect, useRef, useState } from 'react'
import { loadMaps } from './googleMapsLoader'
import './GuessMap.css'

interface Props {
  onGuessChange: (position: google.maps.LatLngLiteral) => void
  disabled?: boolean
  initialGuess?: google.maps.LatLngLiteral | null
}

export function GuessMap({ onGuessChange, disabled = false, initialGuess = null }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const callback = useRef(onGuessChange)
  const [expanded, setExpanded] = useState(false)
  const [status, setStatus] = useState('Loading map…')
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(initialGuess)
  const initial = useRef(initialGuess)
  const disabledRef = useRef(disabled)
  useEffect(() => { disabledRef.current = disabled }, [disabled])
  useEffect(() => { callback.current = onGuessChange }, [onGuessChange])

  useEffect(() => {
    let cancelled = false
    let listener: google.maps.MapsEventListener | undefined
    let resizeObserver: ResizeObserver | undefined
    let pin: google.maps.OverlayView | undefined
    async function initialize() {
      try {
        const { Map, OverlayView } = await loadMaps()
        if (cancelled || !container.current) return
        const map = new Map(container.current, {
          center: { lat: 20, lng: 0 }, zoom: 1, minZoom: 1,
          streetViewControl: false, mapTypeControl: false,
          fullscreenControl: false, zoomControl: true,
          gestureHandling: 'greedy', clickableIcons: false,
        })
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
        if (initial.current) {
          marker.point = new google.maps.LatLng(initial.current)
          marker.setMap(map)
        }
        listener = map.addListener('click', (event: google.maps.MapMouseEvent) => {
          if (disabledRef.current || !event.latLng) return
          marker.point = event.latLng
          if (!marker.getMap()) marker.setMap(map)
          else marker.draw()
          const selected = event.latLng.toJSON()
          setGuess(selected)
          callback.current(selected)
        })
        resizeObserver = new ResizeObserver(() => {
          const center = map.getCenter()
          google.maps.event.trigger(map, 'resize')
          if (center) map.setCenter(center)
        })
        resizeObserver.observe(container.current)
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
    }
  }, [])

  return <section className={`guess-map${expanded ? ' guess-map--expanded' : ''}`} aria-label="Choose a location on the world map">
    <div className="guess-map__toolbar">
      <span>World map</span>
      <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {expanded ? 'Collapse map' : 'Expand map'}
      </button>
    </div>
    <div className="guess-map__body">
      <div ref={container} className="guess-map__canvas" />
      {status && <p className="guess-map__status" role="status">{status}</p>}
    </div>
    <p className="guess-map__selection" aria-live="polite">
      {guess ? `${guess.lat.toFixed(5)}, ${guess.lng.toFixed(5)}` : 'Click the map to place your pin'}
    </p>
  </section>
}
