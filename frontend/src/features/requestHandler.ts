

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
    console.log(optionObj)
    response = await fetch(`${path}`, optionObj)
    
  } catch {
    throw new Error('Unable to connect to the server. Check that the backend is running and try again.')
  }
  if (!response.ok) {
    console.log(response)
    handleStatus(response, pointType)
  }
  try { return await response.json() as T }
  catch { throw new Error('The server returned an invalid response. Please try again.') }
}

