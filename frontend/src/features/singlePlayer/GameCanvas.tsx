import { StreetViewPanel } from '../../common/googleMapUtil/StreetViewPanel'
import { GuessMap } from '../../common/googleMapUtil/GuessMap'
import './GameCanvas.css'

interface Props {
  panoId: string
  onGuessChange: (position: google.maps.LatLngLiteral) => void
  disabled?: boolean
  initialGuess?: google.maps.LatLngLiteral | null
}

// Maps SDK views require DOM containers, rather than an HTML canvas element.
export function GameCanvas({ panoId, onGuessChange, disabled, initialGuess }: Props) {
  return (
    <div className="game-canvas" role="region" aria-label="Single-player game area">
      <StreetViewPanel panoId={panoId} />
      <div className="game-canvas__guess-map">
        <GuessMap onGuessChange={onGuessChange} disabled={disabled} initialGuess={initialGuess} />
      </div>
    </div>
  )
}
