// 서버 응답과 같은 필드 이름을 사용한다 (docs/API.md 항목 1~4).
export type DemoAccount = 'demo-user-1' | 'demo-user-2' | 'demo-officer'
export type UserAccount = Exclude<DemoAccount, 'demo-officer'>

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
  display_language: string
  files: File[]
}

export type FieldError = {
  field: string
  reason: string
}

export type CreateCaseResult =
  | { ok: true; case: CaseSummary }
  | { ok: false; errors: FieldError[] }

// API.md 항목 3. analysis_items는 담당자가 `담당자 승인 대기` 건을 볼 때만 온다.
export type CaseDetail = {
  id: number
  situation: string
  display_language: string | null
  support_type: string
  status: string
  rejection_reason: string | null
  analysis_items?: unknown[]
}

// 검토 대기 목록(F-09). GET /review-queue 응답 한 줄.
// failure_reason은 DATA-MODEL CheckResult.failure_reason에서 이름을 가져왔다.
export type ReviewQueueItem = {
  id: number
  support_type: string
  status: string
  created_at: string
  failure_reason: string | null
}

// API.md 항목 4
export type RejectResult = {
  case_id: number
  status: string
  reason: string
  rejected_at: string
}

// API.md 항목 5
export type CancelResult = {
  case_id: number
  status: string
  previous_status: string
  canceled_at: string
}
