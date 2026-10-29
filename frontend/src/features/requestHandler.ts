

function handleStatus(response: Response, endpointType: string){
    switch (endpointType){
        case 'authpage': 
            if (response.status === 409) throw new Error('This username is already taken. Please choose another.')
            if (response.status === 401) throw new Error('Invalid username or password. Please try again.')
            if (response.status === 422) throw new Error('Invalid input. Please check your username and password.')
            throw new Error('Request failed. Check that the backend is running and try again.')
    
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
    handleStatus(response, pointType)
  }
  // 204 No Content (e.g. leaving a lobby) has no body to parse.
  if (response.status === 204) return undefined as T
  try { return await response.json() as T }
  catch { throw new Error('The server returned an invalid response. Please try again.') }
}

