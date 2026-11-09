import type { ReviewQueueItem } from '../types'

// 임시 응답: 담당자용 검토 대기 목록 API가 서버·API.md에 아직 없다.
// 서버의 GET /cases는 담당자에게 403을 돌려주므로 여기서 메모리 값만 돌려준다.
// API가 합의되면 cases.ts에 실제 요청 함수를 만들고 이 파일을 지운다.
//
// ID 1001·1002는 DATA-MODEL 시드의 `담당자 승인 대기` 건이라 "상세 열기"가 실제 서버 상세로 이어진다.
// 생성 일시는 시드에 고정값이 없어 임의로 넣은 값이다. 반려 등 서버 변경은 이 목록에 반영되지 않는다.
const MOCK_QUEUE: ReviewQueueItem[] = [
  {
    id: 1002,
    support_type: 'F-6-1',
    status: '담당자 승인 대기',
    created_at: '2026-11-03T01:10:00+00:00',
    failure_reason: null,
  },
  {
    id: 1001,
    support_type: 'F-6-1',
    status: '담당자 승인 대기',
    created_at: '2026-11-03T00:30:00+00:00',
    failure_reason: null,
  },
]

// DESIGN.md 검토 대기 목록: `담당자 승인 대기`·`준비 확인 요청` 건만 보인다.
const QUEUE_STATES = ['담당자 승인 대기', '준비 확인 요청']

export function listReviewQueue(signal?: AbortSignal): Promise<ReviewQueueItem[]> {
  return new Promise((resolve, reject) => {
    // 불러오는 중 상태를 화면에서 확인할 수 있게 짧게 지연한다.
    const timer = setTimeout(() => {
      resolve(MOCK_QUEUE.filter((item) => QUEUE_STATES.includes(item.status)).map((item) => ({ ...item })))
    }, 300)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('요청이 취소되었습니다.', 'AbortError'))
    })
  })
}
