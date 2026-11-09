import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { getSupplement, requestSupplementConfirmation, resolveSupplements, saveSupplementChoices, sendSupplement, startRevision } from '../api/supplementation'
import type { SupplementCase } from '../api/supplementation'
import type { DemoAccount } from '../types'
import './SupplementScreen.css'

type Props = {caseId: number; account: DemoAccount; onChanged?: () => void}
type Loaded = {caseId: number; account: DemoAccount; revision: number; data?: SupplementCase; error?: string}

export function SupplementScreen({caseId, account, onChanged}: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [revision, setRevision] = useState(0)
  const [reasons, setReasons] = useState<Record<number, string>>({})
  const [choices, setChoices] = useState<Record<number, boolean>>({})
  const [resolveIds, setResolveIds] = useState<number[]>([])
  const [resolutionReason, setResolutionReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const alive = useRef(true)
  useEffect(() => {alive.current = true; return () => {alive.current = false}}, [])
  useEffect(() => {
    const controller = new AbortController()
    getSupplement(caseId, account, controller.signal)
      .then((data) => {if (!controller.signal.aborted) setLoaded({caseId, account, revision, data})})
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setLoaded({caseId, account, revision, error: cause instanceof Error ? cause.message : '보완 내역을 불러오지 못했습니다.'})
      })
    return () => controller.abort()
  }, [caseId, account, revision])
  const current = loaded?.caseId === caseId && loaded.account === account && loaded.revision === revision ? loaded : null
  const data = current?.data
  const outstanding = data?.items.filter((item) => !item.supplement_resolved) ?? []
  const unsavedChoices = outstanding.some((item) => choices[item.id] !== undefined && choices[item.id] !== item.prepared)
  const selected = Object.entries(reasons).map(([id, reason]) => ({id: Number(id), reason}))
  const act = async (run: () => Promise<unknown>, message: string) => {
    if (busy) return
    setBusy(true); setError(null); setNotice(null)
    try {
      await run()
      if (!alive.current) return
      setReasons({}); setChoices({}); setResolveIds([]); setResolutionReason('')
      setNotice(message); setRevision((value) => value + 1)
      onChanged?.()
    } catch (cause: unknown) {
      if (alive.current) setError(cause instanceof Error ? cause.message : '요청을 처리하지 못했습니다.')
    } finally {if (alive.current) setBusy(false)}
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (data) void act(() => sendSupplement(caseId, data.approval_id, selected, account), '보완을 요청했습니다.')
  }
  return <section className="supplement-screen" aria-labelledby={`supplement-title-${caseId}`}>
    <h3 id={`supplement-title-${caseId}`}>보완 요청·처리</h3>
    {!current && <p role="status">보완 내역을 불러오는 중입니다.</p>}
    {current?.error && <div role="alert"><p>{current.error}</p><button onClick={() => setRevision((v) => v + 1)}>다시 불러오기</button></div>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {data && <>
      <p>현재 상태: <strong>{data.status}</strong></p>
      <form onSubmit={submit}><fieldset disabled={busy}>
        <legend>승인된 준비 항목</legend>
        {data.items.map((item) => <div key={item.id} className="supplement-item">
          <p><strong>{item.text}</strong></p>
          {item.translated_text && <p lang="vi">{item.translated_text}</p>}
          <p>준비 상태: {item.prepared === null ? '미선택' : item.prepared ? '준비함' : '아직'}</p>
          {item.supplement_reason && <p className="supplement-reason">보완 사유: {item.supplement_reason} · {item.supplement_resolved ? '담당자 확인 완료' : '미해결'}</p>}
          {data.can_request && <>
            <label><input type="checkbox" checked={item.id in reasons} onChange={(event) => setReasons((previous) => {
              const next = {...previous}
              if (event.target.checked) next[item.id] = ''
              else delete next[item.id]
              return next
            })} /> {item.text} 보완 요청</label>
            {item.id in reasons && <div className="field"><label htmlFor={`supplement-reason-${item.id}`}>보완 사유 · {item.text}</label>
              <textarea id={`supplement-reason-${item.id}`} required maxLength={10000} rows={2} value={reasons[item.id]} onChange={(event) => setReasons({...reasons, [item.id]: event.target.value})} />
            </div>}
          </>}
          {account !== 'demo-officer' && data.status === '서류 준비중' && !item.supplement_resolved && <div className="supplement-choices" role="group" aria-label={`${item.text} 준비 여부`}>
            <label><input type="radio" name={`supplement-choice-${item.id}`} checked={(choices[item.id] ?? item.prepared) === true} onChange={() => setChoices({...choices, [item.id]: true})} /> 준비함</label>
            <label><input type="radio" name={`supplement-choice-${item.id}`} checked={(choices[item.id] ?? item.prepared) === false} onChange={() => setChoices({...choices, [item.id]: false})} /> 아직</label>
          </div>}
        </div>)}
        {data.can_request && <button type="submit" disabled={selected.length === 0 || selected.some((item) => !item.reason.trim())}>보완 요청 보내기</button>}
      </fieldset></form>
      {data.can_restart && <button disabled={busy} onClick={() => void act(() => startRevision(caseId, data.approval_id, account), '수정을 시작했습니다. 보완 항목이 아직으로 바뀌었습니다.')}>수정 시작</button>}
      {account !== 'demo-officer' && data.status === '서류 준비중' && outstanding.length > 0 && <div className="supplement-actions">
        <button disabled={busy} onClick={() => void act(() => saveSupplementChoices(caseId, outstanding.map((item) => ({id: item.id, prepared: choices[item.id] ?? item.prepared ?? false})), account), '보완 항목의 준비 상태를 저장했습니다.')}>보완 준비 상태 저장</button>
        <button disabled={busy || unsavedChoices} onClick={() => void act(() => requestSupplementConfirmation(caseId, account), '담당자에게 준비 확인을 다시 요청했습니다.')}>확인 다시 요청</button>
        <p>준비 상태를 저장한 뒤 확인을 다시 요청해 주세요. 준비함 표시만으로 보완이 해소되지는 않습니다.</p>
      </div>}
      {data.can_resolve && <form onSubmit={(event) => {event.preventDefault(); void act(() => resolveSupplements(caseId, data.approval_id, resolveIds, resolutionReason, account), '선택한 보완 항목의 처리를 확인했습니다.')}}>
        <fieldset disabled={busy}>
          <legend>재요청된 보완 항목 확인</legend>
          {outstanding.map((item) => <label className="supplement-resolve-choice" key={item.id}><input type="checkbox" checked={resolveIds.includes(item.id)} disabled={item.prepared !== true} onChange={(event) => setResolveIds(event.target.checked ? [...resolveIds, item.id] : resolveIds.filter((id) => id !== item.id))} /> {item.text} · {item.prepared ? '준비함' : '아직'}</label>)}
          <div className="field"><label htmlFor={`resolve-reason-${caseId}`}>보완 처리 확인 사유</label><textarea id={`resolve-reason-${caseId}`} required maxLength={10000} value={resolutionReason} onChange={(event) => setResolutionReason(event.target.value)} /></div>
          <button disabled={resolveIds.length === 0 || !resolutionReason.trim()}>보완 처리 확인</button>
        </fieldset>
      </form>}
      <p lang="ko">준비 확인 완료는 민원 접수나 체류기간 연장 허가가 아닙니다.</p>
      <p lang="vi">Đây không phải là xác nhận tiếp nhận hồ sơ hoặc cấp phép gia hạn lưu trú.</p>
    </>}
  </section>
}
