import { ApiError } from './cases'

export type CriterionInput = {
  office: string | null
  body: string
  source: string
  checked_on: string
  is_verified: boolean
  is_active: boolean
}

export type Criterion = CriterionInput & { id: number; version: number; support_type: 'F-6-1'; needs_office_check: boolean }
export type CriterionChange = { criterion: Criterion; recheck_case_ids: number[] }

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

async function criteriaRequest(path: string, signal?: AbortSignal, body?: unknown): Promise<unknown> {
  const response = await fetch(`${apiBase}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Demo-Account': 'demo-officer', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  })
  const result: unknown = await response.json()
  if (!response.ok) {
    let message = '기준을 저장하지 못했습니다. 입력값을 확인하고 다시 시도하세요.'
    if (result && typeof result === 'object' && 'detail' in result) {
      const detail: unknown = result.detail
      if (typeof detail === 'string') message = detail
      else if (Array.isArray(detail)) {
        message = detail.map((item: unknown) => {
          if (!item || typeof item !== 'object') return ''
          const field = 'loc' in item && Array.isArray(item.loc) ? item.loc.filter((v) => v !== 'body').join('.') : ''
          return `${field}: ${'msg' in item ? String(item.msg) : '입력값을 확인하세요.'}`
        }).filter(Boolean).join(' ')
      }
    }
    throw new ApiError(response.status, message)
  }
  return result
}

export async function listCriteria(signal?: AbortSignal): Promise<Criterion[]> {
  const result = await criteriaRequest('/criteria', signal)
  if (!Array.isArray(result)) throw new Error('기준 목록 응답을 확인하지 못했습니다.')
  return result as Criterion[]
}

export async function saveCriterion(input: CriterionInput, current: Criterion | null): Promise<CriterionChange> {
  const result = await criteriaRequest(current ? `/criteria/${current.id}` : '/criteria', undefined,
    current ? { ...input, expected_version: current.version } : input) as Criterion & { recheck_case_ids: number[] }
  return {criterion: result, recheck_case_ids: result.recheck_case_ids}
}
