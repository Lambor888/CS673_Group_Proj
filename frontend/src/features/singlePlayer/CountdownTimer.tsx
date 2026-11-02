import { useEffect, useState } from 'react'
import './CountdownTimer.css'

interface Props {
  // When the round ends, as milliseconds since the epoch. null = no round is running.
  deadline: number | null
}

const WARNING_SECONDS = 10

function format(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

// Display only: the server decides when a round really ends. Give this component a `key` that
// changes with the deadline so the clock restarts cleanly for each round.
export function CountdownTimer({ deadline }: Props) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (deadline === null) return
    const id = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(id)
  }, [deadline])

  if (deadline === null) {
    return <div className="countdown countdown--idle" role="timer" aria-label="No round running">--:--</div>
  }
  const seconds = Math.max(0, Math.ceil((deadline - now) / 1000))
  const state = seconds === 0 ? ' countdown--done' : seconds <= WARNING_SECONDS ? ' countdown--warn' : ''
  return (
    <div className={`countdown${state}`} role="timer" aria-label={`${seconds} seconds left`}>
      {format(seconds)}
    </div>
  )
}
