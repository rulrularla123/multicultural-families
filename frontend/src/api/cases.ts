import type {
  CaseDetail, CaseInput, CaseSummary, CreateCaseResult, DemoAccount, RejectResult, UserAccount,
} from '../types'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

// 화면이 401·403·404·409·422를 구분해 안내할 수 있도록 HTTP 상태를 함께 싣는다.
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// 오류 응답 형식은 API.md에서 아직 합의 전이다. 지금 서버의 FastAPI `detail`
// (문자열, 또는 422 검증 오류의 목록)만 읽는다.
async function serverError(response: Response): Promise<ApiError> {
  let message = '서버 요청을 처리하지 못했습니다.'
  try {
    const body: { detail?: unknown } = await response.json()
    if (typeof body.detail === 'string') {
      message = body.detail
    } else if (Array.isArray(body.detail)) {
      const messages = body.detail
        .map((item: unknown) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : ''))
        .filter(Boolean)
      if (messages.length > 0) message = messages.join(' ')
    }
  } catch {
    // JSON이 아닌 서버 오류도 사용자에게 오류로 표시한다.
  }
  return new ApiError(response.status, message)
}

export async function listCases(account: UserAccount, signal?: AbortSignal): Promise<CaseSummary[]> {
  const response = await fetch(`${apiBase}/cases`, {
    headers: { 'X-Demo-Account': account }, signal,
  })
  if (!response.ok) throw await serverError(response)
  const body: unknown = await response.json()
  if (!Array.isArray(body)) throw new Error('준비 건 목록 응답을 확인하지 못했습니다.')
  return body as CaseSummary[]
}

export async function createCase(input: CaseInput, account: UserAccount): Promise<CreateCaseResult> {
  const form = new FormData()
  form.append('support_type', input.support_type)
  form.append('situation', input.situation)
  form.append('display_language', input.display_language)
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

// API.md 항목 3: GET /cases/{case_id}
export async function getCase(caseId: number, account: DemoAccount, signal?: AbortSignal): Promise<CaseDetail> {
  const response = await fetch(`${apiBase}/cases/${caseId}`, {
    headers: { 'X-Demo-Account': account }, signal,
  })
  if (!response.ok) throw await serverError(response)
  return (await response.json()) as CaseDetail
}

// API.md 항목 4: POST /cases/{case_id}/reject
export async function rejectCase(caseId: number, reason: string, account: DemoAccount): Promise<RejectResult> {
  const response = await fetch(`${apiBase}/cases/${caseId}/reject`, {
    method: 'POST',
    headers: { 'X-Demo-Account': account, 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!response.ok) throw await serverError(response)
  return (await response.json()) as RejectResult
}

// DESIGN.md 오류 상태: 401은 모의 계정 선택 안내, 403은 권한 없음만 보여 준다.
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return '모의 계정을 다시 선택해 주세요.'
    if (error.status === 403) return '이 준비 건을 볼 권한이 없습니다.'
    if (error.status === 404) return '준비 건을 찾을 수 없습니다.'
    return error.message
  }
  if (error instanceof Error) return error.message
  return '요청을 처리하지 못했습니다.'
}
