// Google Identity Services ("Sign in with Google"): https://developers.google.com/identity/gsi/web
// The button hands us an ID token ("credential"); the backend verifies it and logs us in.

export const GOOGLE_CLIENT_ID: string = (import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '').trim()

export const googleSignInEnabled = GOOGLE_CLIENT_ID !== ''

export interface GoogleButtonOptions {
  type?: 'standard' | 'icon'
  theme?: 'outline' | 'filled_blue' | 'filled_black'
  size?: 'large' | 'medium' | 'small'
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
  shape?: 'rectangular' | 'pill'
  width?: number
}

interface GoogleIdentity {
  initialize(config: { client_id: string; callback: (response: { credential?: string }) => void }): void
  renderButton(parent: HTMLElement, options: GoogleButtonOptions): void
}

// Typed locally: @types/google.maps already owns the global `google` namespace.
function identityApi(): GoogleIdentity | undefined {
  return (window as unknown as { google?: { accounts?: { id?: GoogleIdentity } } }).google?.accounts?.id
}

let loading: Promise<GoogleIdentity> | null = null

export function loadGoogleIdentity(): Promise<GoogleIdentity> {
  const ready = identityApi()
  if (ready) return Promise.resolve(ready)
  loading ??= new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = () => {
      const api = identityApi()
      if (api) resolve(api)
      else reject(new Error('Google sign-in failed to load.'))
    }
    script.onerror = () => {
      loading = null // allow a retry on the next mount
      script.remove()
      reject(new Error("Couldn't load Google sign-in. Check your connection or ad blocker."))
    }
    document.head.appendChild(script)
  })
  return loading
}
