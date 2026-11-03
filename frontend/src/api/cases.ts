import type { CaseInput, CaseSummary, CreateCaseResult, DemoAccount } from '../types'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

async function serverError(response: Response): Promise<Error> {
  let message = '서버 요청을 처리하지 못했습니다.'
  try {
    const body: { detail?: unknown } = await response.json()
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    // JSON이 아닌 서버 오류도 사용자에게 오류로 표시한다.
  }
  return new Error(message)
}

export async function listCases(account: DemoAccount, signal?: AbortSignal): Promise<CaseSummary[]> {
  const response = await fetch(`${apiBase}/cases`, {
    headers: { 'X-Demo-Account': account }, signal,
  })
  if (!response.ok) throw await serverError(response)
  const body: unknown = await response.json()
  if (!Array.isArray(body)) throw new Error('준비 건 목록 응답을 확인하지 못했습니다.')
  return body as CaseSummary[]
}

export async function createCase(input: CaseInput, account: DemoAccount): Promise<CreateCaseResult> {
  const form = new FormData()
  form.append('support_type', input.support_type)
  form.append('situation', input.situation)
  for (const file of input.files) form.append('files', file)
  const response = await fetch(`${apiBase}/cases`, {
    method: 'POST', headers: { 'X-Demo-Account': account }, body: form,
  })
  // boundary를 브라우저가 붙이도록 Content-Type을 직접 지정하지 않는다.
  if (response.status === 422) {
    const body: CreateCaseResult = await response.json()
    if (!body.ok && Array.isArray(body.errors)) return body
    throw new Error('입력 오류 응답을 확인하지 못했습니다.')
  }
  if (!response.ok) throw await serverError(response)
  const body: CreateCaseResult = await response.json()
  if (!body.ok || !body.case) throw new Error('생성 결과를 확인하지 못했습니다.')
  return body
}
