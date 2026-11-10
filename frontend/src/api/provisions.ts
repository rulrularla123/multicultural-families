import { apiGet } from './client'
import type { ProvisionDetail, RelatedProvision } from './types'

export function getProvision(id: string): Promise<ProvisionDetail> {
  return apiGet<ProvisionDetail>(`/provisions?id=${encodeURIComponent(id)}`)
}

export function getRelatedProvisions(id: string): Promise<RelatedProvision[]> {
  return apiGet<RelatedProvision[]>(`/provisions/related?id=${encodeURIComponent(id)}`)
}
