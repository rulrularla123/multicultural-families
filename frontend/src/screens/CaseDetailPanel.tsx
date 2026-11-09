import { useEffect, useState } from 'react'
import { ApiError, cancelCase, errorMessage, getCase } from '../api/cases'
import { startCheck } from '../api/workflow'
import type { CancelResult, CaseDetail, UserAccount } from '../types'
import { ApprovedResultView } from './ApprovedResultView'

type Props = {
  caseId: number
  account: UserAccount
  onClose: () => void
  onChanged: () => void
}

type Loaded = { caseId: number; account: UserAccount; revision: number; detail?: CaseDetail; error?: string }

// 승인 전 상태에서는 "담당자 검토 중"만 보여 준다 (DESIGN.md, US-02 권한).
const REVIEW_STATES = ['자동 점검중', '담당자 승인 대기']
// US-08: 진행 중 6개 상태만 취소할 수 있고, 끝 상태는 읽기 전용이다.
const CANCELABLE_STATES = ['준비중', '자동 점검중', '담당자 승인 대기', '서류 준비중', '준비 확인 요청', '보완 요청']
const FINISHED_STATES = ['준비 확인 완료', '취소 완료']
// US-03: 승인 뒤에만 승인 결과를 연다. 승인 전에는 "담당자 검토 중"만 보인다.
const APPROVED_STATES = ['서류 준비중', '준비 확인 요청', '보완 요청', '준비 확인 완료']

// US-02 (실패·거절): 식별정보·추출 실패는 위치와 수정 안내를 보여 준다. 값은 서버가 돌려주지 않는다.
function checkErrorMessage(error: unknown): string {
  const base = errorMessage(error)
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object' || Array.isArray(error.detail)) {
    return base
  }
  type Place = { kind?: string; source?: string; file_name?: string | null; page?: number | null }
  const detail = error.detail as Place & { locations?: Place[] }
  const describe = (place: Place) => {
    if (place.file_name) return `${place.file_name}${place.page ? ` ${place.page}쪽` : ''}`
    return '상황 설명'
  }
  const places = detail.locations
    ? detail.locations.map((place) => `${describe(place)}${place.kind ? `(${place.kind})` : ''}`)
    : detail.file_name ? [describe(detail)] : []
  return places.length > 0 ? `${base} 위치: ${places.join(', ')}` : base
}

const dateFormat = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function CaseDetailPanel({ caseId, account, onClose, onChanged }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [revision, setRevision] = useState(0)
  const [confirming, setConfirming] = useState(false)
  const [canceling, setCanceling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [canceled, setCanceled] = useState<CancelResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [checkNotice, setCheckNotice] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getCase(caseId, account, controller.signal)
      .then((detail) => {
        if (!controller.signal.aborted) setLoaded({ caseId, account, revision, detail })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoaded({ caseId, account, revision, error: errorMessage(error) })
      })
    return () => controller.abort()
  }, [caseId, account, revision])

  // 다른 건·계정으로 바뀐 직후에는 이전 응답을 보여 주지 않는다.
  const current = loaded?.caseId === caseId && loaded.account === account && loaded.revision === revision
    ? loaded
    : null
  const detail = current?.detail

  const handleCancel = async () => {
    setCanceling(true)
    setCancelError(null)
    try {
      const result = await cancelCase(caseId, account)
      setCanceled(result)
      setConfirming(false)
      setRevision((value) => value + 1)
      onChanged()
    } catch (error: unknown) {
      // 거절된 요청은 화면의 상태 표시를 바꾸지 않는다 (DESIGN.md 오류).
      setCancelError(errorMessage(error))
    } finally {
      setCanceling(false)
    }
  }

  const handleCheck = async () => {
    setChecking(true)
    setCheckError(null)
    setCheckNotice(null)
    try {
      const result = await startCheck(caseId, account)
      setCheckNotice(result.discarded ? '이전 점검 결과는 반영하지 않았습니다.' : '자동 점검을 마쳤습니다. 담당자 검토 중입니다.')
      setRevision((value) => value + 1)
      onChanged()
    } catch (error: unknown) {
      setCheckError(checkErrorMessage(error))
    } finally {
      setChecking(false)
    }
  }

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
      {detail && detail.status === '준비중' && (
        <button type="button" onClick={handleCheck} disabled={checking || canceling}>
          {checking ? '점검하는 중' : '자동 점검 시작'}
        </button>
      )}
      {checkNotice && <p role="status">{checkNotice}</p>}
      {checkError && <p className="error" role="alert">{checkError}</p>}
      {detail && APPROVED_STATES.includes(detail.status) && (
        <ApprovedResultView key={revision} caseId={caseId} account={account} />
      )}
      {canceled && (
        <p role="status">
          취소했습니다. 취소 전 상태: {canceled.previous_status}, 취소 일시: {dateFormat.format(new Date(canceled.canceled_at))}
        </p>
      )}
      {detail && FINISHED_STATES.includes(detail.status) && (
        <p>끝난 준비 건입니다. 다시 진행하려면 새 준비 건을 만드세요.</p>
      )}
      {detail && CANCELABLE_STATES.includes(detail.status) && !confirming && (
        <button type="button" onClick={() => { setConfirming(true); setCancelError(null) }}>준비 건 취소</button>
      )}
      {detail && CANCELABLE_STATES.includes(detail.status) && confirming && (
        <div className="cancel-confirm" role="group" aria-labelledby="cancel-confirm-text">
          <p id="cancel-confirm-text">취소하면 되돌릴 수 없고, 다시 진행하려면 새 준비 건을 만들어야 합니다.</p>
          <button type="button" onClick={handleCancel} disabled={canceling}>
            {canceling ? '취소하는 중' : '취소 확인'}
          </button>
          <button type="button" onClick={() => setConfirming(false)} disabled={canceling}>돌아가기</button>
        </div>
      )}
      {cancelError && <p className="error" role="alert">{cancelError}</p>}
      <button type="button" onClick={onClose}>닫기</button>
    </section>
  )
}
