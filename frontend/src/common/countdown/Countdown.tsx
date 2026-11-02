import { useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { Ref } from 'react'
import './Countdown.css'

export interface CountdownHandle {
  /** Start or replace a countdown. Zero completes immediately. */
  settimer: (seconds: number) => void
}

interface Props {
  ref?: Ref<CountdownHandle>
  onComplete?: () => void
  className?: string
}

export function Countdown({ ref, onComplete, className = '' }: Props) {
  const [remaining, setRemaining] = useState(0)
  const interval = useRef<ReturnType<typeof setInterval> | null>(null)
  const completion = useRef(onComplete)

  useEffect(() => { completion.current = onComplete }, [onComplete])
  useEffect(() => () => {
    if (interval.current !== null) clearInterval(interval.current)
  }, [])

  useImperativeHandle(ref, () => ({
    settimer(seconds: number) {
      if (!Number.isFinite(seconds) || seconds < 0) {
        throw new RangeError('Countdown seconds must be a finite, non-negative number.')
      }
      if (interval.current !== null) {
        clearInterval(interval.current)
        interval.current = null
      }
      const duration = Math.ceil(seconds)
      setRemaining(duration)
      if (duration === 0) {
        completion.current?.()
        return
      }

      // Measure elapsed time instead of counting ticks: background tabs throttle timers.
      const deadline = performance.now() + duration * 1000
      interval.current = setInterval(() => {
        const left = Math.max(0, Math.ceil((deadline - performance.now()) / 1000))
        setRemaining(left)
        if (left === 0) {
          if (interval.current !== null) clearInterval(interval.current)
          interval.current = null
          completion.current?.()
        }
      }, 100)
    },
  }), [])

  const minutes = Math.floor(remaining / 60).toString().padStart(2, '0')
  const seconds = (remaining % 60).toString().padStart(2, '0')

  return (
    <span className={`countdown ${className}`.trim()} role="timer" aria-label="Countdown" aria-live="off">
      {minutes}:{seconds}
    </span>
  )
}
