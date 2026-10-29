

// The server's own error message ("detail"), when it sent a plain-text one.
async function readDetail(response: Response): Promise<string | null> {
    try {
        const body = await response.json()
        return typeof body?.detail === 'string' ? body.detail : null
    } catch {
        return null
    }
}

function handleStatus(response: Response, endpointType: string, detail: string | null){
    switch (endpointType){
        case 'authpage': 
            if (response.status === 409 && detail?.toLowerCase().includes('email')) throw new Error('An account with this email already exists.')
            if (response.status === 409) throw new Error('This username is already taken. Please choose another.')
            if (response.status === 401) throw new Error('Invalid username or password. Please try again.')
            if (response.status === 422) throw new Error('Invalid input. Please check your username, email and password.')
            throw new Error('Request failed. Check that the backend is running and try again.')

        case 'google':
            // Sign in with Google: the server explains what went wrong (not set up, email in use, ...).
            throw new Error(detail ?? 'Google sign-in failed. Please try again.')

        case 'account':
            // Endpoints for the logged-in user (profile, password, connect Google).
            if (response.status === 401) throw new Error('Your session has expired. Please log in again.')
            if (response.status === 422) throw new Error('Invalid input. Please check the form and try again.')
            throw new Error(detail ?? 'Request failed. Please try again.')
    
        case 'homepage':
            if (response.status === 404) throw new Error('This lobby no longer exists.')
            if (response.status === 409) throw new Error('This lobby is full.')
            throw new Error('Request failed. Please try again.')
        case 'lobbypage':
            if (response.status === 404) throw new Error('This lobby no longer exists.')
            if (response.status === 403) throw new Error("Only the host can start the game")
            if (response.status === 409) throw new Error("Not enough players")
            throw new Error('Request failed. Please try again.')

        default:
            // Never let an error response fall through and get parsed as a success.
            throw new Error('Request failed. Please try again.')
    }
}

export async function request<T>(path: string, pointType: string, options: RequestInit, token?: string): Promise<T> {
  let response: Response
  try {
    let optionObj: RequestInit
    if (!token){
        optionObj = {
            ...options, 
            signal: AbortSignal.timeout(15000),
        
        }
    }
    else{
        optionObj = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
            }, 
            signal: AbortSignal.timeout(15000),
        }
    }
    response = await fetch(`${path}`, optionObj)
    
  } catch {
    throw new Error('Unable to connect to the server. Check that the backend is running and try again.')
  }
  if (!response.ok) {
    handleStatus(response, pointType, await readDetail(response))
  }
  // 204 No Content (e.g. leaving a lobby) has no body to parse.
  if (response.status === 204) return undefined as T
  try { return await response.json() as T }
  catch { throw new Error('The server returned an invalid response. Please try again.') }
}

