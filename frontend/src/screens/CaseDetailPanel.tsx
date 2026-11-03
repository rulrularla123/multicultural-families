import { useEffect, useState } from 'react'
import { errorMessage, getCase } from '../api/cases'
import type { CaseDetail, UserAccount } from '../types'

type Props = {
  caseId: number
  account: UserAccount
  onClose: () => void
}

type Loaded = { caseId: number; account: UserAccount; detail?: CaseDetail; error?: string }

// 승인 전 상태에서는 "담당자 검토 중"만 보여 준다 (DESIGN.md, US-02 권한).
const REVIEW_STATES = ['자동 점검중', '담당자 승인 대기']

export function CaseDetailPanel({ caseId, account, onClose }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getCase(caseId, account, controller.signal)
      .then((detail) => {
        if (!controller.signal.aborted) setLoaded({ caseId, account, detail })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoaded({ caseId, account, error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [caseId, account])

  // 다른 건·계정으로 바뀐 직후에는 이전 응답을 보여 주지 않는다.
  const current = loaded?.caseId === caseId && loaded.account === account ? loaded : null
  const detail = current?.detail

  return (
    <section className="case-detail" aria-labelledby="case-detail-title">
      <h2 id="case-detail-title">준비 건 상태</h2>
      {!current && <p role="status">불러오는 중</p>}
      {current?.error && <p className="error" role="alert">{current.error}</p>}
      {detail && (
        <dl>
          <dt>지원 유형</dt>
          <dd>{detail.support_type}</dd>
          <dt>현재 상태</dt>
          <dd>{detail.status}</dd>
          {REVIEW_STATES.includes(detail.status) && (
            <>
              <dt>안내</dt>
              <dd>담당자 검토 중</dd>
            </>
          )}
          <dt>상황 설명</dt>
          <dd className="pre-wrap">{detail.situation}</dd>
          {detail.rejection_reason && (
            <>
              <dt>반려 사유</dt>
              <dd className="pre-wrap rejection-reason">{detail.rejection_reason}</dd>
            </>
          )}
        </dl>
      )}
      <button type="button" onClick={onClose}>닫기</button>
    </section>
  )
}
