import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api/cases'
import { approveCase, getCheckResult, KIND_LABELS, saveReview } from '../api/workflow'
import type { AnalysisItem, CheckResult, ItemKind, ReviewItemInput } from '../api/workflow'

type Props = {
  caseId: number
  onApproved: () => void
}

type Row = ReviewItemInput & { removed: boolean }

const KINDS = Object.keys(KIND_LABELS) as ItemKind[]

function toRows(result: CheckResult): Row[] {
  // 검토를 저장한 적이 있으면 그 내용을, 없으면 자동 점검 초안을 고칠 출발점으로 쓴다.
  const source: AnalysisItem[] = result.reviewed_items ?? result.analysis_items
  return source.map((item) => ({
    id: item.id,
    kind: item.kind,
    text: item.text,
    criterion_id: item.criterion_id ?? '',
    translated_text: item.translated_text ?? '',
    removed: false,
  }))
}

// US-03: 담당자가 초안을 확인·수정하고 베트남어 번역문을 확인한 뒤에만 승인한다.
export function OfficerCheckReview({ caseId, onApproved }: Props) {
  const [result, setResult] = useState<CheckResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [rows, setRows] = useState<Row[]>([])
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState<'review' | 'approve' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [savedNotice, setSavedNotice] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getCheckResult(caseId, controller.signal)
      .then((loaded) => {
        if (controller.signal.aborted) return
        setResult(loaded)
        setRows(toRows(loaded))
        setReason(loaded.review_reason ?? '')
        setConfirmed(loaded.can_approve)
        setDirty(false)
        setLoadError(null)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(error))
      })
    return () => controller.abort()
  }, [caseId, revision])

  if (loadError) return <p className="error" role="alert">점검 결과를 불러오지 못했습니다. {loadError}</p>
  if (!result) return <p role="status">점검 결과를 불러오는 중</p>

  const criterionIds = result.criterion_versions.map((item) => item.criterion_id)
  const kept = rows.filter((row) => !row.removed)
  const update = (index: number, patch: Partial<Row>) => {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)))
    setSavedNotice(false)
    setDirty(true)
  }
  const addRow = () => {
    setRows((current) => [...current, {
      id: crypto.randomUUID(), kind: 'additional_documents', text: '', criterion_id: criterionIds[0] ?? '',
      translated_text: '', removed: false,
    }])
    setSavedNotice(false)
    setDirty(true)
  }

  const handleReview = async (event: FormEvent) => {
    event.preventDefault()
    setBusy('review')
    setActionError(null)
    try {
      await saveReview(caseId, {
        result_id: result.result_id,
        reason,
        translation_confirmed: confirmed,
        items: kept.map((row) => ({
          id: row.id, kind: row.kind, text: row.text, criterion_id: row.criterion_id, translated_text: row.translated_text,
        })),
      })
      setSavedNotice(true)
      setConfirmed(false)
      setRevision((value) => value + 1)
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  const handleApprove = async () => {
    if (dirty || !result.can_approve) return
    setBusy('approve')
    setActionError(null)
    try {
      await approveCase(caseId, result.result_id)
      onApproved()
    } catch (error) {
      setActionError(errorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  const incomplete = kept.length === 0 || reason.trim() === '' || !confirmed
    || kept.some((row) => !row.text.trim() || !row.translated_text.trim() || !row.criterion_id)

  return (
    <div className="draft">
      <h3>자동 점검 결과 <span className="draft-label">담당자 확인 전 초안</span></h3>
      {result.failure_reason && (
        <p className="error">자동 점검 실패 ({result.failure_reason}). 문서와 기준을 직접 확인해 항목과 처리 사유를 남겨야 승인할 수 있습니다.</p>
      )}
      {result.analysis_items.length === 0 && <p>분석 항목이 없습니다. 항목을 직접 추가하세요.</p>}

      <form onSubmit={handleReview}>
        {rows.map((row, index) => (
          <fieldset key={row.id} className="review-item" disabled={busy !== null}>
            <legend>
              항목 {index + 1}
              {result.analysis_items.find((item) => item.id === row.id)?.needs_confirmation && !result.reviewed_items && (
                <span className="error"> 확인 필요</span>
              )}
            </legend>
            <div className="field">
              <label htmlFor={`kind-${row.id}`}>분류</label>
              <select id={`kind-${row.id}`} disabled={row.removed} value={row.kind} onChange={(e) => update(index, { kind: e.target.value as ItemKind })}>
                {KINDS.map((kind) => <option key={kind} value={kind}>{KIND_LABELS[kind]}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor={`text-${row.id}`}>한국어</label>
              <textarea id={`text-${row.id}`} disabled={row.removed} rows={2} value={row.text} onChange={(e) => update(index, { text: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor={`vi-${row.id}`}>베트남어 번역문</label>
              <textarea
                id={`vi-${row.id}`} disabled={row.removed} rows={2} lang="vi" value={row.translated_text}
                onChange={(e) => update(index, { translated_text: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor={`criterion-${row.id}`}>근거 기준 ID</label>
              <select id={`criterion-${row.id}`} disabled={row.removed} value={row.criterion_id} onChange={(e) => update(index, { criterion_id: e.target.value })}>
                <option value="">선택하세요</option>
                {criterionIds.map((id) => <option key={id} value={id}>기준 {id}</option>)}
              </select>
            </div>
            <label className="remove-toggle">
              <input type="checkbox" checked={row.removed} onChange={(e) => update(index, { removed: e.target.checked })} />
              이 항목 삭제 (삭제한 항목도 이력에 남습니다)
            </label>
          </fieldset>
        ))}
        <button type="button" onClick={addRow} disabled={busy !== null || criterionIds.length === 0}>항목 추가</button>

        <div className="field">
          <label htmlFor="review-reason">처리 사유 (근거와 수정·삭제·실패 해소 사유)</label>
          <textarea id="review-reason" rows={3} value={reason} disabled={busy !== null} onChange={(e) => { setReason(e.target.value); setDirty(true); setSavedNotice(false) }} />
        </div>
        <label className="confirm-toggle">
          <input type="checkbox" checked={confirmed} disabled={busy !== null} onChange={(e) => { setConfirmed(e.target.checked); setDirty(true); setSavedNotice(false) }} />
          베트남어 번역문을 확인했습니다
        </label>
        <button type="submit" disabled={busy !== null || incomplete}>
          {busy === 'review' ? '저장하는 중' : '검토 저장'}
        </button>
      </form>

      {savedNotice && <p role="status">검토를 저장했습니다.</p>}
      {actionError && <p className="error" role="alert">{actionError}</p>}
      {dirty && <p role="status">변경한 검토 내용을 먼저 저장한 뒤 승인하세요.</p>}
      {!result.can_approve && <p>검토를 저장하고 확인 필요·자동 점검 실패가 모두 해소되어야 승인할 수 있습니다.</p>}
      <button type="button" onClick={handleApprove} disabled={busy !== null || !result.can_approve || dirty}>
        {busy === 'approve' ? '승인하는 중' : '승인'}
      </button>
    </div>
  )
}
