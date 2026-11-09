import { useEffect, useState } from 'react'
import { errorMessage } from '../api/cases'
import { completeCase, getApprovedResult } from '../api/workflow'
import type { ApprovedResult, PreparationItem } from '../api/workflow'
import './MyCasesScreen.css'
import './PreparationCheckScreen.css'

type Props = {
  caseId: number
  onChanged: () => void
}

// 완료 결과는 실제 민원 접수·허가가 아니다 (US-07 정상 2). 한국어 문구는 서버가 고정해서 돌려준다.
export const NOTICE_KO = '민원 접수나 체류기간 연장 허가가 아닙니다'

// DESIGN.md "보완·완료 확인 (담당자)" 중 완료 부분, F-07 / US-07. API.md 항목 10·13.
// 보완 요청 입력(US-06)은 별도 작업이라 여기에 넣지 않았다.
export function CompletionScreen({ caseId, onChanged }: Props) {
  const [data, setData] = useState<ApprovedResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [noticeVi, setNoticeVi] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getApprovedResult(caseId, 'demo-officer', controller.signal)
      .then((loaded) => {
        if (!controller.signal.aborted) { setData(loaded); setLoadError(null) }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(error))
      })
    return () => controller.abort()
  }, [caseId, revision])

  if (loadError) return <p className="error" role="alert">준비 확인 정보를 불러오지 못했습니다. {loadError}</p>
  if (!data) return <p role="status">준비 확인 정보를 불러오는 중</p>

  const items = data.preparation_items
  const notReady = items.filter((item) => item.prepared !== true).length
  const supplements = items.filter((item) => item.supplement_reason && !item.supplement_resolved).length
  const needsReview = items.filter((item) => item.needs_confirmation).length
  const completed = data.status === '준비 확인 완료'
  // 화면에서 알 수 있는 사유만 미리 보여 준다. 버전 일치 여부는 완료 요청 때 서버가 확인한다.
  const blockers = [
    data.status !== '준비 확인 요청' && `지금 상태(${data.status})에서는 완료할 수 없습니다.`,
    notReady > 0 && `"아직"이거나 고르지 않은 항목이 ${notReady}개 있습니다.`,
    supplements > 0 && `미해결 보완 항목이 ${supplements}개 있습니다.`,
    needsReview > 0 && `확인 필요 항목이 ${needsReview}개 있습니다.`,
  ].filter((reason): reason is string => Boolean(reason))

  const handleComplete = async () => {
    setCompleting(true)
    setRequestError(null)
    try {
      await completeCase(caseId, noticeVi, confirmed)
      setRevision((value) => value + 1)
      onChanged()
    } catch (error) {
      // US-07 실패·거절: 서버가 준 사유를 보여 주고 상태는 바꾸지 않는다.
      setRequestError(errorMessage(error))
    } finally {
      setCompleting(false)
    }
  }

  return (
    <section className="completion" aria-labelledby={`completion-${caseId}`}>
      <h3 id={`completion-${caseId}`}>준비 확인</h3>
      <dl>
        <dt>"아직"인 항목</dt>
        <dd>{data.not_prepared_count}개</dd>
        <dt>미해결 보완 항목</dt>
        <dd>{supplements}개</dd>
      </dl>
      <ul className="readiness-items">
        {items.map((item) => (
          <li key={item.id} className="readiness-item">
            {item.text}: <strong>{readinessLabel(item)}</strong>
          </li>
        ))}
      </ul>

      {completed ? (
        <>
          {/* 완료 안내 두 언어는 위 승인 결과(ApprovedResultView)에 표시된다. */}
          <p>완료된 준비 건은 바꿀 수 없습니다.</p>
        </>
      ) : (
        <>
          {blockers.length > 0 && (
            <div className="error" role="alert">
              <p>완료할 수 없는 이유</p>
              <ul>{blockers.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            </div>
          )}
          <p>완료 안내 (한국어): {NOTICE_KO}</p>
          <div className="field">
            <label htmlFor={`notice-vi-${caseId}`}>완료 안내 베트남어 번역문</label>
            <textarea
              id={`notice-vi-${caseId}`} lang="vi" rows={2} value={noticeVi} disabled={completing}
              onChange={(event) => setNoticeVi(event.target.value)}
            />
          </div>
          <label className="confirm-toggle">
            <input type="checkbox" checked={confirmed} disabled={completing} onChange={(event) => setConfirmed(event.target.checked)} />
            베트남어 완료 안내를 확인했습니다
          </label>
          {requestError && <p className="error" role="alert">{requestError}</p>}
          <button
            type="button" onClick={handleComplete}
            disabled={blockers.length > 0 || completing || !confirmed || noticeVi.trim() === ''}
          >
            {completing ? '완료 처리하는 중' : '준비 확인 완료'}
          </button>
        </>
      )}
    </section>
  )
}

function readinessLabel(item: PreparationItem): string {
  if (item.prepared === true) return '준비함'
  if (item.prepared === false) return '아직'
  return '미선택'
}

// US-07 (정상) 2: 완료 안내를 한국어와 이용자 모국어(베트남어)로 같이 보여 준다.
export function CompletionNotice({ notice }: { notice: { notice_ko: string; notice_translation: string } }) {
  return (
    <div className="completion-notice" role="note">
      <p lang="ko">준비 확인 완료는 {notice.notice_ko}.</p>
      <p lang="vi">{notice.notice_translation}</p>
    </div>
  )
}
