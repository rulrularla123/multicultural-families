import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { listCriteria, saveCriterion } from '../api/criteria'
import type { Criterion, CriterionInput } from '../api/criteria'
import { ApiError } from '../api/cases'
import './CriteriaScreen.css'

const emptyInput = (): CriterionInput => ({
  office: null, body: '', source: '', checked_on: '', is_verified: false, is_active: true,
})

export function CriteriaScreen() {
  const [criteria, setCriteria] = useState<Criterion[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [current, setCurrent] = useState<Criterion | null>(null)
  const [input, setInput] = useState<CriterionInput>(emptyInput)
  const [saving, setSaving] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    listCriteria(controller.signal)
      .then((rows) => { if (!controller.signal.aborted) setCriteria(rows) })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setLoadError(cause instanceof Error ? cause.message : '기준을 불러오지 못했습니다.')
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [revision])

  const refresh = () => {
    setLoading(true)
    setLoadError(null)
    setRevision((value) => value + 1)
  }

  const reset = () => {
    setCurrent(null)
    setInput(emptyInput())
    setError(null)
    setConflict(false)
  }

  const edit = (criterion: Criterion) => {
    setCurrent(criterion)
    setInput({ office: criterion.office, body: criterion.body,
      source: criterion.source, checked_on: criterion.checked_on,
      is_verified: criterion.is_verified, is_active: criterion.is_active })
    setError(null)
    setNotice(null)
    setConflict(false)
    document.getElementById('criterion-body')?.focus()
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (saving || conflict) return
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const result = await saveCriterion(input, current)
      reset()
      setNotice(`기준을 저장했습니다. ${result.recheck_case_ids.length > 0
        ? `진행 중인 준비 건 ${result.recheck_case_ids.length}건의 이전 결과를 무효화하고 재점검을 요청했습니다.`
        : '기존 준비 건의 점검 결과에는 변경이 없습니다.'}`)
      refresh()
    } catch (cause: unknown) {
      if (cause instanceof ApiError && cause.status === 409) {
        setConflict(true)
        refresh()
      }
      setError(cause instanceof Error ? cause.message : '저장하지 못했습니다.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="criteria-screen">
      <h1>기준 관리</h1>
      <p>F-6-1 체류기간 연장 준비에 적용할 기준을 관리합니다. 공식 원문과 확인일을 대조해 주세요.</p>
      {notice && <p role="status">{notice}</p>}
      <section aria-labelledby="criteria-list-heading">
        <h2 id="criteria-list-heading">등록된 기준</h2>
        {loading && <p role="status">기준을 불러오는 중입니다.</p>}
        {loadError && <div role="alert"><p>{loadError}</p><button onClick={refresh}>다시 불러오기</button></div>}
        {!loading && !loadError && criteria.length === 0 && <p>등록된 기준이 없습니다. 공통 기준부터 등록해 주세요.</p>}
        {!loading && !loadError && criteria.length > 0 && <ul className="criteria-list">
          {criteria.map((criterion) => <li key={criterion.id}>
            <h3>{criterion.office ? `${criterion.office} 기준` : '공통 기준'} · 버전 {criterion.version}</h3>
            <p className="criteria-body">{criterion.body}</p>
            <p>{/^https?:\/\//i.test(criterion.source)
              ? <a href={criterion.source} target="_blank" rel="noreferrer">공식 원문 열기</a>
              : criterion.source} · 확인일 {criterion.checked_on}</p>
            <p>{criterion.is_active ? '사용 중' : '사용 중지'} · {criterion.is_verified ? '담당자 확인 완료' : '담당자 확인 필요'}</p>
            <button disabled={saving} onClick={() => edit(criterion)} aria-label={`${criterion.office ?? '공통'} 기준 ${criterion.id} 수정`}>수정</button>
          </li>)}
        </ul>}
      </section>

      <form onSubmit={(event) => void submit(event)} aria-labelledby="criterion-form-heading">
        <h2 id="criterion-form-heading">{current ? `기준 수정 · 현재 버전 ${current.version}` : '새 기준 등록'}</h2>
        <fieldset disabled={saving}>
          <legend className="visually-hidden">기준 정보</legend>
          <div className="field"><label htmlFor="criterion-scope">적용 범위</label>
            <select id="criterion-scope" value={input.office === null ? 'common' : 'office'} onChange={(event) => setInput({ ...input, office: event.target.value === 'common' ? null : '', is_verified: false })}>
              <option value="common">공통 기준</option><option value="office">관서별 기준</option>
            </select>
          </div>
          {input.office !== null && <div className="field"><label htmlFor="criterion-office">관서명</label>
            <input id="criterion-office" required maxLength={128} value={input.office} onChange={(event) => setInput({ ...input, office: event.target.value, is_verified: false })} />
          </div>}
          <div className="field"><label htmlFor="criterion-body">기준 본문</label>
            <textarea id="criterion-body" required maxLength={10000} rows={5} value={input.body} onChange={(event) => setInput({ ...input, body: event.target.value, is_verified: false })} />
          </div>
          <div className="field"><label htmlFor="criterion-source">공식 원문·출처</label>
            <input id="criterion-source" required maxLength={2048} value={input.source} onChange={(event) => setInput({ ...input, source: event.target.value, is_verified: false })} />
          </div>
          <div className="field"><label htmlFor="criterion-date">원문 확인일</label>
            <input id="criterion-date" type="date" required value={input.checked_on} onChange={(event) => setInput({ ...input, checked_on: event.target.value, is_verified: false })} />
          </div>
          <label className="criterion-choice"><input type="checkbox" checked={input.is_verified} onChange={(event) => setInput({ ...input, is_verified: event.target.checked })} /> 공식 원문과 현재 적용 여부를 담당자가 확인했습니다.</label>
          <p>미확인 기준은 자동 점검에 적용되지 않습니다. 해당 관서의 기준이 미확인이면 관서 확인이 필요하다고 안내합니다.</p>
          <label className="criterion-choice"><input type="checkbox" checked={input.is_active} onChange={(event) => setInput({ ...input, is_active: event.target.checked })} /> 이 기준을 사용합니다.</label>
          {current && <p>변경하면 적용 중인 준비 건의 이전 분석·승인·확인 요청이 무효화되고 재점검됩니다. 완료·취소 건의 당시 결과는 보존됩니다.</p>}
          {error && <p role="alert">{error}</p>}
          {conflict && <p>등록된 기준 목록에서 최신 기준의 ‘수정’을 다시 선택해 주세요.</p>}
          <div className="criteria-actions"><button type="submit" disabled={conflict}>{saving ? '저장 중…' : current ? '변경 저장' : '기준 등록'}</button>
            {current && <button type="button" onClick={reset}>수정 취소</button>}
          </div>
        </fieldset>
      </form>
    </main>
  )
}
