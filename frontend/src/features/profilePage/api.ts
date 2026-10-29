import { request } from '../requestHandler'
import { getToken } from '../userAuth/api'

export interface Stats {
  rounds_played: number
  total_score: number
  best_score: number | null
  average_score: number | null
  best_distance_km: number | null
  average_distance_km: number | null
}

export function getStats() {
  return request<Stats>('/api/profile/stats', 'account', { method: 'GET' }, getToken())
}
