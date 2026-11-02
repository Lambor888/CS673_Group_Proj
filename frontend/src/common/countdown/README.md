# Countdown

A button-sized countdown display. It does not start until `settimer(seconds)` is called.
It is independent of game rounds and backend timers.

```tsx
import { useRef, useState } from 'react'
import { Countdown } from '../../common/countdown/Countdown'
import type { CountdownHandle } from '../../common/countdown/Countdown'

export function TimerDemo() {
  const timer = useRef<CountdownHandle>(null)
  const [message, setMessage] = useState('')

  return (
    <div>
      <Countdown ref={timer} onComplete={() => setMessage('Time is up!')} />
      <button type="button" onClick={() => {
        setMessage('')
        timer.current?.settimer(10)
      }}>Start / reset 10 seconds</button>
      <p role="status">{message}</p>
    </div>
  )
}
```

- `ref.current.settimer(seconds)` starts a countdown or replaces the current one.
- `onComplete` fires once when that countdown reaches zero. Replacing an unfinished
  countdown or unmounting the component does not fire it.
- `settimer(0)` immediately displays `00:00` and fires `onComplete`.
- Fractional seconds round up. Negative values, `NaN`, and infinity throw `RangeError`.
- The initial display is `00:00`, without a completion event.
- `className` allows custom styling. The display uses `MM:SS`.
- Elapsed time is measured against a deadline. Background tabs can delay the callback;
  it runs when the browser resumes executing timers. Game rules should use backend time.
