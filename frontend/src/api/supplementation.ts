import { ApiError } from './cases'
import type { DemoAccount } from '../types'

export type SupplementItem = { id: number; text: string; translated_text: string | null; prepared: boolean | null;
  supplement_reason: string | null; supplement_resolved: boolean }
export type SupplementCase = { case_id: number; approval_id: number; status: string;
  can_request: boolean; can_restart: boolean; can_resolve: boolean; items: SupplementItem[] }
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

async function request(caseId: number, action: string, account: DemoAccount, body?: unknown, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`${apiBase}/cases/${caseId}/${action}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Demo-Account': account, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  })
  const result: unknown = await response.json()
  if (!response.ok) {
    let message = '요청을 처리하지 못했습니다. 최신 상태를 다시 불러와 주세요.'
    if (result && typeof result === 'object' && 'detail' in result) {
      const detail: unknown = result.detail
      if (typeof detail === 'string') message = detail
      else if (detail && typeof detail === 'object' && 'message' in detail) message = String(detail.message)
      else if (Array.isArray(detail)) message = '선택 항목과 각 항목의 보완 사유를 확인해 주세요.'
    }
    throw new ApiError(response.status, message)
  }
  return result
}

export async function getSupplement(caseId: number, account: DemoAccount, signal?: AbortSignal): Promise<SupplementCase> {
  return await request(caseId, 'supplement', account, undefined, signal) as SupplementCase
}
export async function sendSupplement(caseId: number, approvalId: number, items: { id: number; reason: string }[], account: DemoAccount) {
  return request(caseId, 'supplement', account, { approval_id: approvalId, items })
}
export async function startRevision(caseId: number, approvalId: number, account: DemoAccount) {
  return request(caseId, 'start-revision', account, { approval_id: approvalId })
}
export async function resolveSupplements(caseId: number, approvalId: number, itemIds: number[], reason: string, account: DemoAccount) {
  return request(caseId, 'resolve-supplements', account, { approval_id: approvalId, item_ids: itemIds, reason })
}
export async function saveSupplementChoices(caseId: number, items: { id: number; prepared: boolean }[], account: DemoAccount) {
  return request(caseId, 'preparation-items', account, { items })
}
export async function requestSupplementConfirmation(caseId: number, account: DemoAccount) {
  return request(caseId, 'request-confirmation', account, {})
}
