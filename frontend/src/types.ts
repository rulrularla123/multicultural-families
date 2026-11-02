// 필드 이름은 임시다. DATA-MODEL.md와 API.md가 확정되면 맞춘다.
export type CaseSummary = {
  id: number
  support_type: string
  status: string
  created_at: string
}

export type CaseInput = {
  support_type: string
  situation: string
  files: File[]
}

export type FieldError = {
  field: 'support_type' | 'situation' | 'files'
  reason: string
}

export type CreateCaseResult =
  | { ok: true; case: CaseSummary }
  | { ok: false; errors: FieldError[] }
