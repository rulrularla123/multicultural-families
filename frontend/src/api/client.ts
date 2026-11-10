// API.md 공통 규칙: 서버 주소 http://127.0.0.1:8000, 모든 요청에 X-Client-Id 헤더.
import type { AnswerPayload, ChatMessage, Lang, StageEvent } from './types'

const BASE = 'http://127.0.0.1:8000/api/v1'

function clientId(): string {
  try {
    let id = localStorage.getItem('client_id')
    if (!id || id.length < 8) {
      id = crypto.randomUUID()
      localStorage.setItem('client_id', id)
    }
    return id
  } catch {
    // 개인정보 보호 모드 등에서 localStorage를 못 쓰면 요청마다 새 ID(매번 다른 분석 목록)
    return crypto.randomUUID()
  }
}

export class ApiError extends Error {
  status: number
  detail: unknown
  missingQuestionIds?: string[]

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : 'request_failed')
    this.status = status
    this.detail = detail
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      /* no body */
    }
    const detail = (body as { detail?: unknown } | null)?.detail ?? body ?? res.statusText
    const err = new ApiError(res.status, detail)
    const missing = (body as { missing_question_ids?: string[] } | null)?.missing_question_ids
    if (missing) err.missingQuestionIds = missing
    throw err
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { 'X-Client-Id': clientId() } })
  return handle<T>(res)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': clientId() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return handle<T>(res)
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE', headers: { 'X-Client-Id': clientId() } })
  await handle<void>(res)
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'X-Client-Id': clientId() },
    body: form,
  })
  return handle<T>(res)
}

export interface ChatStreamBody {
  message: string
  lang: Lang
  history: ChatMessage[]
  session_id?: string
  analysis_id?: string | null
}

export interface ChatStreamHandlers {
  onStage: (ev: StageEvent) => void
  onDelta: (text: string) => void
  onReset: () => void
  onAnswer: (answer: AnswerPayload) => void
  onError: (message: string) => void
}

/** SSE를 fetch+ReadableStream으로 직접 파싱한다 (POST라 EventSource를 쓸 수 없다). */
export async function streamChat(body: ChatStreamBody, handlers: ChatStreamHandlers, signal?: AbortSignal) {
  let res: Response
  try {
    res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Client-Id': clientId() },
      body: JSON.stringify(body),
      signal,
    })
  } catch {
    handlers.onError('network_error')
    return
  }

  if (!res.ok || !res.body) {
    let detail: unknown = res.statusText
    try {
      const j = await res.json()
      detail = j?.detail ?? detail
    } catch {
      /* no body */
    }
    handlers.onError(typeof detail === 'string' ? detail : 'request_failed')
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (eventName: string, data: string) => {
    if (!data) return
    let payload: unknown
    try {
      payload = JSON.parse(data)
    } catch {
      return
    }
    switch (eventName) {
      case 'stage':
        handlers.onStage(payload as StageEvent)
        break
      case 'delta':
        handlers.onDelta((payload as { text: string }).text)
        break
      case 'reset':
        handlers.onReset()
        break
      case 'answer':
        handlers.onAnswer(payload as AnswerPayload)
        break
      case 'error': {
        const p = payload as { message?: string; detail?: string }
        handlers.onError(p.message ?? p.detail ?? 'error')
        break
      }
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        let eventName = 'message'
        let data = ''
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        dispatch(eventName, data)
      }
    }
  } catch (e) {
    if ((e as DOMException)?.name !== 'AbortError') handlers.onError('stream_interrupted')
  }
}

export { clientId }
