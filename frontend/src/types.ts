// US-01 서버 응답과 같은 필드 이름을 사용한다.
export type DemoAccount = 'demo-user-1' | 'demo-user-2'

export type CaseSummary = {
  id: number
  support_type: string
  owner_id: string
  status: string
  created_at: string
}

export type CaseInput = {
  support_type: string
  situation: string
  files: File[]
}

export type FieldError = {
  field: string
  reason: string
}

export type CreateCaseResult =
  | { ok: true; case: CaseSummary }
  | { ok: false; errors: FieldError[] }
