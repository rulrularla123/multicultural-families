import { ApiError } from './cases'
import { delay, findCase, notReadyCount, OFFICER, unresolvedSupplementCount } from './preparationCheck'
import type { ReadinessCase } from './preparationCheck'
import type { DemoAccount } from '../types'

// US-07 준비 확인 완료의 임시 응답. preparationCheck.ts의 모의 건을 같이 쓴다.
// 서버 API·API.md 항목이 없어 응답 형식은 합의 전 임시 형식이다.

export type CompleteResult =
  | { ok: true; case_id: number; status: string; completed_at: string }
  | { ok: false; reasons: string[] }

// US-07 완료 조건 중 채우지 못한 것. 화면과 모의 서버가 같은 판단을 쓴다.
export function completionBlockers(value: ReadinessCase): string[] {
  const reasons: string[] = []
  if (value.status !== '준비 확인 요청') reasons.push(`지금 상태(${value.status})에서는 완료할 수 없습니다.`)
  if (!value.versions_match) reasons.push('승인 결과가 현재 상황·서류·기준 버전과 다릅니다.')
  const supplements = unresolvedSupplementCount(value)
  if (supplements > 0) reasons.push(`미해결 보완 항목이 ${supplements}개 있습니다.`)
  if (value.needs_review_count > 0) reasons.push(`확인 필요 항목이 ${value.needs_review_count}개 있습니다.`)
  const notReady = notReadyCount(value)
  if (notReady > 0) reasons.push(`"아직"인 항목이 ${notReady}개 있습니다.`)
  return reasons
}

// 담당자만, 조건을 모두 채운 `준비 확인 요청` 건만 완료한다. 거절되면 상태를 바꾸지 않는다.
export function completeCase(caseId: number, account: DemoAccount): Promise<CompleteResult> {
  return delay(() => {
    const found = findCase(caseId)
    if (account !== OFFICER) throw new ApiError(403, '담당자만 완료할 수 있습니다.')
    const reasons = completionBlockers(found)
    if (reasons.length > 0) return { ok: false, reasons }

    const completedAt = new Date().toISOString()
    found.status = '준비 확인 완료'
    found.completed_at = completedAt
    return { ok: true, case_id: found.case_id, status: found.status, completed_at: completedAt }
  })
}
