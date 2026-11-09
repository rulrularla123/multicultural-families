// API.md 항목 6~10: 자동 점검, 점검 결과, 검토·번역 확인, 승인, 승인 결과.
import { serverError } from './cases'
import type { DemoAccount, UserAccount } from '../types'

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
const OFFICER = 'demo-officer'

export type ItemKind = 'cautions' | 'possible_omissions' | 'additional_documents'

export const KIND_LABELS: Record<ItemKind, string> = {
  cautions: '주의점',
  possible_omissions: '누락 가능성',
  additional_documents: '추가 준비 서류 후보',
}

export type AnalysisItem = {
  id: string
  kind: ItemKind
  text: string
  criterion_id: string | null
  source?: string | null
  checked_on?: string | null
  needs_confirmation?: boolean
  translated_text?: string | null
}

export type CheckResult = {
  case_id: number
  result_id: number
  status: string
  can_approve: boolean
  analysis_items: AnalysisItem[]
  reviewed_items: AnalysisItem[] | null
  failure_reason: string | null
  review_reason: string | null
  criterion_versions: { criterion_id: string; version: number }[]
}

export type ReviewItemInput = {
  id: string
  kind: ItemKind
  text: string
  criterion_id: string
  translated_text: string
}

export type ApprovedItem = {
  id: string
  kind: ItemKind
  text: string
  translated_text: string
  source: string
  checked_on: string
}

export type PreparationItem = {
  id: number
  item_key: string
  text: string
  translated_text: string | null
  criterion_id: string
  prepared: boolean | null
  needs_confirmation: boolean
  supplement_reason: string | null
  supplement_resolved: boolean | null
}

export type ApprovedResult = {
  case_id: number
  approval_id: number
  status: string
  display_language: string
  bilingual_ready: boolean
  items: ApprovedItem[]
  preparation_items: PreparationItem[]
  not_prepared_count: number
  approved_at: string
  completion_notice: { notice_ko: string; notice_translation: string } | null
}

export type CheckStarted = { case_id: number; status: string; discarded: boolean; message?: string }

async function call<T>(path: string, account: DemoAccount, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-Demo-Account': account }
  if (init.body) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${apiBase}${path}`, { ...init, headers })
  if (!response.ok) throw await serverError(response)
  return (await response.json()) as T
}

// 항목 6. 생성 뒤 이용자가 점검을 시작한다.
export function startCheck(caseId: number, account: UserAccount): Promise<CheckStarted> {
  return call(`/cases/${caseId}/check`, account, { method: 'POST' })
}

// 항목 7. 담당자만.
export function getCheckResult(caseId: number, signal?: AbortSignal): Promise<CheckResult> {
  return call(`/cases/${caseId}/check-result`, OFFICER, { signal })
}

// 항목 8. 최종 항목 전체를 보낸다.
export function saveReview(
  caseId: number,
  body: { result_id: number; reason: string; translation_confirmed: boolean; items: ReviewItemInput[] },
): Promise<unknown> {
  return call(`/cases/${caseId}/review`, OFFICER, { method: 'POST', body: JSON.stringify(body) })
}

// 항목 9.
export function approveCase(caseId: number, resultId: number): Promise<unknown> {
  return call(`/cases/${caseId}/approve`, OFFICER, { method: 'POST', body: JSON.stringify({ result_id: resultId }) })
}

// 항목 10. 소유자·담당자.
export function getApprovedResult(caseId: number, account: DemoAccount, signal?: AbortSignal): Promise<ApprovedResult> {
  return call(`/cases/${caseId}/approved-result`, account, { signal })
}

// 항목 11. true=준비함, false=아직. 일부 항목만 보내도 된다.
export function savePreparationChoices(
  caseId: number,
  account: UserAccount,
  items: { id: number; prepared: boolean }[],
): Promise<unknown> {
  return call(`/cases/${caseId}/preparation-items`, account, { method: 'POST', body: JSON.stringify({ items }) })
}

export type ConfirmationRequested = { case_id: number; status: string; requested_at: string; not_prepared_count: number }

// 항목 12. 미선택 항목이 있으면 409 detail {message, unselected_item_ids}.
export function requestConfirmation(caseId: number, account: UserAccount): Promise<ConfirmationRequested> {
  return call(`/cases/${caseId}/request-confirmation`, account, { method: 'POST' })
}

export type Completed = {
  case_id: number
  status: string
  completed_at: string
  notice_ko: string
  notice_translation: string
}

// 항목 13. 조건을 채우지 못하면 409 detail {reasons: [...]}.
export function completeCase(caseId: number, noticeTranslation: string, confirmed: boolean): Promise<Completed> {
  return call(`/cases/${caseId}/complete`, OFFICER, {
    method: 'POST',
    body: JSON.stringify({ notice_translation: noticeTranslation, translation_confirmed: confirmed }),
  })
}
