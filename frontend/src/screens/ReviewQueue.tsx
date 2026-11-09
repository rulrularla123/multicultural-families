import { useEffect, useState } from 'react'
import { errorMessage } from '../api/cases'
import { listReviewQueue } from '../api/mockReviewQueue'
import type { ReviewQueueItem } from '../types'

const dateFormat = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  dateStyle: 'medium',
  timeStyle: 'short',
})

type Listing = { revision: number; items: ReviewQueueItem[]; error?: string }

type Props = {
  disabled: boolean
  onOpen: (caseId: number) => void
}

// DESIGN.md 검토 대기 목록 (F-09). 담당자 부재 중 점검이 끝난 건도 여기에 보인다.
export function ReviewQueue({ disabled, onOpen }: Props) {
  const [listing, setListing] = useState<Listing | null>(null)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    listReviewQueue(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setListing({ revision, items })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setListing({ revision, items: [], error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [revision])

  const current = listing?.revision === revision ? listing : null
  const items = current && !current.error ? current.items : null

  return (
    <section className="review-queue" aria-labelledby="review-queue-title">
      <h2 id="review-queue-title">검토 대기 목록</h2>
      {!current && <p role="status">목록을 불러오는 중</p>}
      {current?.error && (
        <div className="error" role="alert">
          <p>검토 대기 목록을 불러오지 못했습니다. {current.error}</p>
          <button type="button" onClick={() => setRevision((value) => value + 1)}>다시 불러오기</button>
        </div>
      )}
      {items !== null && items.length === 0 && <p>검토할 준비 건이 없습니다.</p>}
      {items !== null && items.length > 0 && (
        <table className="case-list">
          <thead>
            <tr>
              <th scope="col">준비 건 ID</th>
              <th scope="col">생성 일시</th>
              <th scope="col">현재 상태</th>
              <th scope="col">자동 점검</th>
              <th scope="col"><span className="visually-hidden">상세</span></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{dateFormat.format(new Date(item.created_at))}</td>
                <td>{item.status}</td>
                <td>{item.failure_reason ? <span className="error">자동 점검 실패</span> : '-'}</td>
                <td>
                  <button type="button" disabled={disabled} onClick={() => onOpen(item.id)}>상세 열기</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
