import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage, getCase, rejectCase } from '../api/cases'
import type { CaseDetail } from '../types'
import { ReviewQueue } from './ReviewQueue'
import './MyCasesScreen.css'

const ACCOUNT = 'demo-officer'

// 검토 대기 목록은 임시 응답(mockReviewQueue.ts)이다. 목록에 없는 건은 준비 건 ID로 상세를 연다.
export function OfficerReviewScreen() {
  const [idInput, setIdInput] = useState('')
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [rejectError, setRejectError] = useState<string | null>(null)
  const [rejectedNotice, setRejectedNotice] = useState(false)

  const load = async (caseId: number) => {
    setLoading(true)
    setLoadError(null)
    try {
      setDetail(await getCase(caseId, ACCOUNT))
    } catch (error) {
      setDetail(null)
      setLoadError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  const openCase = (caseId: number) => {
    setReason('')
    setRejectError(null)
    setRejectedNotice(false)
    void load(caseId)
  }

  const handleOpen = (event: FormEvent) => {
    event.preventDefault()
    const caseId = Number(idInput.trim())
    if (!Number.isInteger(caseId) || caseId <= 0) {
      setDetail(null)
      setLoadError('준비 건 ID는 1 이상의 정수로 입력하세요.')
      return
    }
    openCase(caseId)
  }

  const handleOpenFromQueue = (caseId: number) => {
    setIdInput(String(caseId))
    openCase(caseId)
  }

  const handleReject = async (event: FormEvent) => {
    event.preventDefault()
    if (!detail || reason.trim() === '') return
    setRejecting(true)
    setRejectError(null)
    try {
      await rejectCase(detail.id, reason, ACCOUNT)
      setReason('')
      setRejectedNotice(true)
      // 화면 상태는 서버가 준 값으로만 바꾼다.
      await load(detail.id)
    } catch (error) {
      // 거절된 요청은 화면의 상태 표시와 입력값을 그대로 둔다 (DESIGN.md).
      setRejectError(errorMessage(error))
    } finally {
      setRejecting(false)
    }
  }

  const canReject = detail?.status === '담당자 승인 대기'
  const reasonEmpty = reason.trim() === ''

  return (
    <main className="my-cases">
      <h1>검토·승인</h1>
      <ReviewQueue disabled={loading || rejecting} onOpen={handleOpenFromQueue} />
      <form className="case-open" onSubmit={handleOpen}>
        <div className="field">
          <label htmlFor="case-id">준비 건 ID</label>
          <input
            id="case-id"
            inputMode="numeric"
            value={idInput}
            disabled={loading || rejecting}
            onChange={(event) => setIdInput(event.target.value)}
          />
        </div>
        <button type="submit" disabled={loading || rejecting}>
          {loading ? '불러오는 중' : '상세 열기'}
        </button>
      </form>

      {loadError && <p className="error" role="alert">{loadError}</p>}
      {!detail && !loadError && !loading && <p>목록에서 상세를 열거나 준비 건 ID를 입력하세요.</p>}
      {loading && <p role="status">불러오는 중</p>}

      {detail && (
        <section className="case-detail" aria-labelledby="officer-detail-title">
          <h2 id="officer-detail-title">준비 건 {detail.id}</h2>
          {rejectedNotice && <p role="status">반려했습니다.</p>}
          <dl>
            <dt>지원 유형</dt>
            <dd>{detail.support_type}</dd>
            <dt>현재 상태</dt>
            <dd>{detail.status}</dd>
            <dt>상황 설명</dt>
            <dd className="pre-wrap">{detail.situation}</dd>
            {detail.rejection_reason && (
              <>
                <dt>반려 사유</dt>
                <dd className="pre-wrap rejection-reason">{detail.rejection_reason}</dd>
              </>
            )}
          </dl>

          {detail.analysis_items && (
            <div className="draft">
              <h3>자동 점검 결과 <span className="draft-label">담당자 확인 전 초안</span></h3>
              {detail.analysis_items.length === 0 ? (
                <p>분석 항목이 없습니다.</p>
              ) : (
                <ul>
                  {detail.analysis_items.map((item, index) => (
                    <li key={index} className="pre-wrap">{describeItem(item)}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {canReject ? (
            <form className="reject-form" onSubmit={handleReject}>
              <div className="field">
                <label htmlFor="reject-reason">반려 사유</label>
                <textarea
                  id="reject-reason"
                  rows={4}
                  value={reason}
                  disabled={rejecting}
                  onChange={(event) => setReason(event.target.value)}
                  aria-describedby={rejectError ? 'reject-error' : 'reject-hint'}
                />
                <p id="reject-hint">사유를 입력해야 반려할 수 있습니다.</p>
                {rejectError && <p id="reject-error" className="error" role="alert">{rejectError}</p>}
              </div>
              <button type="submit" disabled={reasonEmpty || rejecting}>
                {rejecting ? '반려하는 중' : '반려'}
              </button>
            </form>
          ) : (
            <p>담당자 승인 대기 상태가 아니라 반려할 수 없습니다.</p>
          )}
        </section>
      )}
    </main>
  )
}

function describeItem(item: unknown): string {
  if (item && typeof item === 'object' && 'text' in item) {
    const kind = 'kind' in item ? `${String(item.kind)}: ` : ''
    return `${kind}${String(item.text)}`
  }
  return JSON.stringify(item)
}
