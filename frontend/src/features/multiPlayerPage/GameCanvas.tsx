import { StreetViewPanel } from '../../common/googleMapUtil/StreetViewPanel'
import { GuessMap } from '../../common/googleMapUtil/GuessMap'
import './GameCanvas.css'

interface Props {
  position?: google.maps.LatLngLiteral
  panoId?: string
  disabled?: boolean
  onGuessChange: (position: google.maps.LatLngLiteral) => void
}

export function GameCanvas({ position, panoId, onGuessChange, disabled }: Props) {
  return (
    <div className="multiplayer-canvas" role="region" aria-label="Multiplayer game area">
      <StreetViewPanel position={position} panoId={panoId} />
      <div className="multiplayer-canvas__guess-map">
        <GuessMap onGuessChange={onGuessChange} disabled={disabled} />
      </div>
    </div>
  )
}
