import { useEffect, useRef, useState } from 'react'
import { GOOGLE_CLIENT_ID, googleSignInEnabled, loadGoogleIdentity } from './google'
import type { GoogleButtonOptions } from './google'

// Google's own button. Renders nothing when VITE_GOOGLE_CLIENT_ID isn't set.
export function GoogleSignInButton({ onCredential, text = 'continue_with', disabled = false }: {
  onCredential: (credential: string) => void
  text?: GoogleButtonOptions['text']
  disabled?: boolean
}) {
  const container = useRef<HTMLDivElement>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  // Latest handler without re-rendering Google's button every render.
  const handler = useRef(onCredential)
  useEffect(() => {
    handler.current = onCredential
  })

  useEffect(() => {
    if (!googleSignInEnabled) return
    let cancelled = false
    loadGoogleIdentity().then((api) => {
      if (cancelled || !container.current) return
      api.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => {
          if (response.credential) handler.current(response.credential)
        },
      })
      api.renderButton(container.current, {
        type: 'standard', theme: 'outline', size: 'large', shape: 'rectangular', text,
        width: Math.min(360, container.current.clientWidth || 360),
      })
    }).catch((err: Error) => {
      if (!cancelled) setLoadError(err.message)
    })
    return () => {
      cancelled = true
    }
  }, [text])

  if (!googleSignInEnabled) return null
  return (
    <div className="google-sign-in" aria-disabled={disabled}>
      <div ref={container} style={disabled ? { pointerEvents: 'none', opacity: 0.6 } : undefined} />
      {loadError && <p className="form-error" role="alert">{loadError}</p>}
    </div>
  )
}
