import { useEffect, useRef, useState } from 'react'
import { loadStreetView } from './googleMapsLoader'
import './StreetViewPanel.css'

// Pass panoId to show an exact panorama (a game round), or position to search
// for the nearest one. Game rounds pass only panoId so the answer's coordinates
// never reach the browser before the guess.
interface Props {
  position?: google.maps.LatLngLiteral
  panoId?: string
}

export function StreetViewPanel({ position, panoId }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState('Loading street view…')
  const lat = position?.lat
  const lng = position?.lng

  useEffect(() => {
    let cancelled = false
    let panorama: google.maps.StreetViewPanorama | undefined
    let listener: google.maps.MapsEventListener | undefined

    async function initialize() {
      try {
        const { StreetViewPanorama, StreetViewService, StreetViewSource, StreetViewPreference } = await loadStreetView()
        if (cancelled) return
        let pano = panoId
        if (!pano) {
          if (lat === undefined || lng === undefined) throw new Error('Pass panoId or position')
          const { data } = await new StreetViewService().getPanorama({
          location: { lat, lng }, radius: 150,
          sources: [StreetViewSource.GOOGLE, StreetViewSource.OUTDOOR],
          preference: StreetViewPreference.NEAREST,
          })
          pano = data.location?.pano
        }
        if (cancelled || !container.current) return
        if (!pano) throw new Error('No panorama found')
        panorama = new StreetViewPanorama(container.current, {
          pano,
          pov: { heading: 0, pitch: 0 },
          addressControl: false,
          showRoadLabels: false,
          fullscreenControl: false,
          motionTracking: false,
          motionTrackingControl: false,
          linksControl: true,
          clickToGo: true,
        })
        listener = panorama.addListener('status_changed', () => {
          if (!cancelled && panorama) {
            setStatus(panorama.getStatus() === 'OK' ? '' : 'Street view is unavailable. Please reload to try again.')
          }
        })
        setStatus('')
      } catch {
        if (!cancelled) setStatus('Unable to load street view. Please reload to try again.')
      }
    }
    void initialize()
    return () => {
      cancelled = true
      listener?.remove()
      panorama?.setVisible(false)
    }
  }, [lat, lng, panoId])

  return <section className="street-view-panel" aria-label="Street view">
    <div ref={container} className="street-view-panel__canvas" />
    {status && <p className="street-view-panel__status" role="status">{status}</p>}
  </section>
}
