import { useEffect, useState } from 'react'
import { errorMessage } from '../api/cases'
import { completeCase, completionBlockers } from '../api/completion'
import { formatDate, getReadiness, notReadyCount, unresolvedSupplementCount } from '../api/preparationCheck'
import type { ReadinessCase } from '../api/preparationCheck'
import './MyCasesScreen.css'
import './PreparationCheckScreen.css'

const ACCOUNT = 'demo-officer'

type Props = {
  caseId: number
}

type Loaded = { caseId: number; revision: number; data?: ReadinessCase; error?: string }

// DESIGN.md "보완·완료 확인 (담당자)" 중 완료 부분, F-07 / US-07. 임시 응답(api/completion.ts)을 쓴다.
// 보완 요청 입력(US-06)은 이주환 담당이라 여기에 넣지 않았다.
export function CompletionScreen({ caseId }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [revision, setRevision] = useState(0)
  const [completing, setCompleting] = useState(false)
  const [rejectReasons, setRejectReasons] = useState<string[]>([])
  const [requestError, setRequestError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getReadiness(caseId, ACCOUNT, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setLoaded({ caseId, revision, data })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoaded({ caseId, revision, error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [caseId, revision])

  const current = loaded?.caseId === caseId && loaded.revision === revision ? loaded : null
  const data = current?.data
  const blockers = data ? completionBlockers(data) : []
  const completed = data?.status === '준비 확인 완료'

  const handleComplete = async () => {
    if (!data) return
    setCompleting(true)
    setRejectReasons([])
    setRequestError(null)
    try {
      const result = await completeCase(data.case_id, ACCOUNT)
      if (!result.ok) {
        // US-07 실패·거절: 사유를 표시하고 상태는 바꾸지 않는다.
        setRejectReasons(result.reasons)
        return
      }
      setRevision((value) => value + 1)
    } catch (error) {
      setRequestError(errorMessage(error))
    } finally {
      setCompleting(false)
    }
  }

  return (
    <main className="my-cases">
      <h1>준비 확인 완료</h1>
      {!current && <p role="status">불러오는 중</p>}
      {current?.error && <p className="error" role="alert">{current.error}</p>}
      {data && (
        <section className="case-detail" aria-labelledby="completion-title">
          <h2 id="completion-title">준비 건 {data.case_id}</h2>
          <dl>
            <dt>현재 상태</dt>
            <dd>{data.status}</dd>
            <dt>승인 결과와 현재 버전</dt>
            <dd>{data.versions_match ? '일치' : '다름 (재점검·재승인 필요)'}</dd>
            <dt>"아직"인 항목</dt>
            <dd>{notReadyCount(data)}개</dd>
            <dt>미해결 보완 항목</dt>
            <dd>{unresolvedSupplementCount(data)}개</dd>
            <dt>확인 필요 항목</dt>
            <dd>{data.needs_review_count}개</dd>
            {data.completed_at && (
              <>
                <dt>완료 일시</dt>
                <dd>{formatDate(data.completed_at)}</dd>
              </>
            )}
          </dl>

          <h3>준비 항목</h3>
          <ul className="readiness-items">
            {data.items.map((item) => (
              <li key={item.id} className="readiness-item">
                {item.content}: <strong>{readinessLabel(item.is_ready)}</strong>
              </li>
            ))}
          </ul>

          {completed ? (
            <>
              <p>완료된 준비 건은 바꿀 수 없습니다.</p>
              <CompletionNotice />
            </>
          ) : (
            <>
              {blockers.length > 0 && (
                <div className="error" role="alert">
                  <p>완료할 수 없는 이유</p>
                  <ul>{blockers.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                </div>
              )}
              {rejectReasons.length > 0 && (
                <div className="error" role="alert">
                  <p>완료 요청이 거절되었습니다.</p>
                  <ul>{rejectReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                </div>
              )}
              {requestError && <p className="error" role="alert">{requestError}</p>}
              <button type="button" onClick={handleComplete} disabled={blockers.length > 0 || completing}>
                {completing ? '완료 처리하는 중' : '준비 확인 완료'}
              </button>
            </>
          )}
        </section>
      )}
    </main>
  )
}

function readinessLabel(value: boolean | null): string {
  if (value === true) return '준비함'
  if (value === false) return '아직'
  return '미선택'
}

// US-07 (정상) 2번: 완료 화면에 한국어와 이용자 모국어로 표시하는 문구.
// 첫 데모 모국어는 베트남어로 정해졌지만(PR #87) 번역 생성·검토 방식이 미정이라 모국어 줄은 자리만 둔다.
export function CompletionNotice() {
  return (
    <div className="completion-notice" role="note">
      <p lang="ko">준비 확인 완료는 민원 접수나 체류기간 연장 허가가 아닙니다.</p>
      <p className="notice-pending">(베트남어 문구: 번역 검토 후 표시)</p>
    </div>
  )
}
