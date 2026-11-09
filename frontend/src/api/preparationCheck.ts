import { ApiError } from './cases'
import type { DemoAccount } from '../types'

// US-05 준비 체크·확인 요청의 타입과 임시 응답. US-07 완료(completion.ts)도 같은 모의 건을 쓴다.
// 서버 API와 PreparationItem(준비 항목) 모델이 아직 없고 API.md에도 항목이 없다.
// 아래 필드 이름은 PRD 6절(준비 여부 NULL·FALSE·TRUE, 보완 사유·보완 처리 여부)을 따른 **합의 전 임시 이름**이다.
// API가 합의되면 이 파일의 함수를 실제 서버 요청으로 바꾼다.
// 메모리에만 저장하므로 새로고침하면 처음 값으로 돌아간다.

export type ReadinessItem = {
  id: number
  content: string
  // null = 미선택, false = 아직, true = 준비함
  is_ready: boolean | null
  supplement_reason: string | null
  supplement_resolved: boolean | null
}

export type ReadinessCase = {
  case_id: number
  owner_id: string
  status: string
  // 승인 결과의 상황·서류·기준 버전이 현재 버전과 같은지 (서버가 계산할 값)
  versions_match: boolean
  needs_review_count: number
  items: ReadinessItem[]
  requested_at: string | null
  completed_at: string | null
}

export type RequestResult =
  | { ok: true; case_id: number; status: string; requested_at: string }
  | { ok: false; unselected_item_ids: number[] }

// ID 2001~2003은 화면 확인용 모의 건이다. DATA-MODEL 시드(1001~1005)와 겹치지 않게 했고 서버에는 없다.
const MOCK_CASES: ReadinessCase[] = [
  {
    case_id: 2001,
    owner_id: 'demo-user-1',
    status: '서류 준비중',
    versions_match: true,
    needs_review_count: 0,
    items: [
      { id: 1, content: '모의 혼인관계 증명 서류', is_ready: null, supplement_reason: null, supplement_resolved: null },
      { id: 2, content: '모의 체류지 입증 서류', is_ready: null, supplement_reason: null, supplement_resolved: null },
      { id: 3, content: '모의 소득 관련 서류', is_ready: null, supplement_reason: null, supplement_resolved: null },
    ],
    requested_at: null,
    completed_at: null,
  },
  {
    // 상황·PDF가 바뀐 뒤 재승인 전인 건: 확인 요청이 거절돼야 한다 (US-05 실패·거절 3번)
    case_id: 2002,
    owner_id: 'demo-user-1',
    status: '서류 준비중',
    versions_match: false,
    needs_review_count: 0,
    items: [
      { id: 4, content: '모의 혼인관계 증명 서류', is_ready: true, supplement_reason: null, supplement_resolved: null },
    ],
    requested_at: null,
    completed_at: null,
  },
  {
    // 모든 조건을 채운 확인 요청 건: 담당자가 완료할 수 있다 (US-07 정상)
    case_id: 2003,
    owner_id: 'demo-user-1',
    status: '준비 확인 요청',
    versions_match: true,
    needs_review_count: 0,
    items: [
      { id: 5, content: '모의 혼인관계 증명 서류', is_ready: true, supplement_reason: null, supplement_resolved: null },
      { id: 6, content: '모의 체류지 입증 서류', is_ready: true, supplement_reason: null, supplement_resolved: null },
    ],
    requested_at: '2026-11-09T01:00:00+00:00',
    completed_at: null,
  },
]

export const MOCK_READINESS_CASE_IDS = MOCK_CASES.map((item) => item.case_id)

export const OFFICER = 'demo-officer'

export function delay<T>(make: () => T, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    // 불러오는 중·버튼 비활성 상태를 화면에서 확인할 수 있게 짧게 지연한다.
    const timer = setTimeout(() => {
      try {
        resolve(make())
      } catch (error) {
        reject(error)
      }
    }, 300)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('요청이 취소되었습니다.', 'AbortError'))
    })
  })
}

export function findCase(caseId: number): ReadinessCase {
  const found = MOCK_CASES.find((item) => item.case_id === caseId)
  if (!found) throw new ApiError(404, '준비 건을 찾을 수 없습니다.')
  return found
}

function copy(value: ReadinessCase): ReadinessCase {
  return { ...value, items: value.items.map((item) => ({ ...item })) }
}

// 보완 사유가 있고 아직 처리되지 않은 항목 (US-06이 만들 값. 지금 모의 건에는 없다)
export function unresolvedSupplementCount(value: ReadinessCase): number {
  return value.items.filter((item) => item.supplement_reason !== null && item.supplement_resolved !== true).length
}

export function notReadyCount(value: ReadinessCase): number {
  return value.items.filter((item) => item.is_ready !== true).length
}

// 준비 건 소유자와 담당자만 본다 (US-01 권한과 같은 기준).
export function getReadiness(caseId: number, account: DemoAccount, signal?: AbortSignal): Promise<ReadinessCase> {
  return delay(() => {
    const found = findCase(caseId)
    if (account !== OFFICER && account !== found.owner_id) throw new ApiError(403, '권한이 없습니다.')
    return copy(found)
  }, signal)
}

// US-05: 모든 항목에 준비함/아직을 골라야 접수한다. "아직"이 있어도 접수한다.
export function requestConfirmation(
  caseId: number,
  choices: Record<number, boolean | null>,
  account: DemoAccount,
): Promise<RequestResult> {
  return delay(() => {
    const found = findCase(caseId)
    if (account !== found.owner_id) throw new ApiError(403, '이 준비 건의 이용자만 확인 요청할 수 있습니다.')
    if (found.status !== '서류 준비중') {
      throw new ApiError(409, `지금 상태(${found.status})에서는 확인 요청할 수 없습니다.`)
    }
    if (!found.versions_match) {
      throw new ApiError(409, '승인 결과가 현재 상황·서류·기준 버전과 다릅니다. 재점검·재승인 뒤에 확인 요청할 수 있습니다.')
    }
    const unselected = found.items.filter((item) => typeof choices[item.id] !== 'boolean').map((item) => item.id)
    if (unselected.length > 0) return { ok: false, unselected_item_ids: unselected }

    const requestedAt = new Date().toISOString()
    for (const item of found.items) item.is_ready = choices[item.id]
    found.status = '준비 확인 요청'
    found.requested_at = requestedAt
    return { ok: true, case_id: found.case_id, status: found.status, requested_at: requestedAt }
  })
}

// 서버 시간(UTC 오프셋 포함 ISO 8601)을 한국 시각으로 표시한다 (API.md 공통 규칙).
const dateFormat = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatDate(value: string): string {
  return dateFormat.format(new Date(value))
}
