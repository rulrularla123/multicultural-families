import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, errorMessage } from '../api/cases'
import { getApprovedResult, requestConfirmation, savePreparationChoices } from '../api/workflow'
import type { ApprovedResult } from '../api/workflow'
import type { UserAccount } from '../types'
import './MyCasesScreen.css'
import './PreparationCheckScreen.css'

type Props = {
  caseId: number
  account: UserAccount
  onChanged: () => void
}

type Choices = Record<number, boolean | null>

// DESIGN.md "준비 항목 체크 (이용자)", F-06 / US-05. API.md 항목 10·11·12.
export function PreparationCheckScreen({ caseId, account, onChanged }: Props) {
  const [data, setData] = useState<ApprovedResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [choices, setChoices] = useState<Choices>({})
  const [unselected, setUnselected] = useState<number[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [requestedNotice, setRequestedNotice] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getApprovedResult(caseId, account, controller.signal)
      .then((loaded) => {
        if (controller.signal.aborted) return
        setData(loaded)
        setLoadError(null)
        setChoices(Object.fromEntries(loaded.preparation_items.map((item) => [item.id, item.prepared])))
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(error))
      })
    return () => controller.abort()
  }, [caseId, account, revision])

  if (loadError) return <p className="error" role="alert">준비 항목을 불러오지 못했습니다. {loadError}</p>
  if (!data) return <p role="status">준비 항목을 불러오는 중</p>

  const editable = data.status === '서류 준비중'

  const choose = (itemId: number, value: boolean) => {
    setChoices((previous) => ({ ...previous, [itemId]: value }))
    setUnselected((previous) => previous.filter((id) => id !== itemId))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitError(null)
    setRequestedNotice(false)
    const missing = data.preparation_items.filter((item) => typeof choices[item.id] !== 'boolean').map((item) => item.id)
    if (missing.length > 0) {
      // US-05 실패·거절 1번: 미선택 항목을 표시하고 요청하지 않는다. 서버도 같은 이유로 거절한다.
      setUnselected(missing)
      setSubmitError(`준비 여부를 고르지 않은 항목이 ${missing.length}개 있습니다.`)
      return
    }
    setSubmitting(true)
    try {
      await savePreparationChoices(caseId, account, data.preparation_items.map((item) => ({
        id: item.id, prepared: choices[item.id] === true,
      })))
      await requestConfirmation(caseId, account)
      setRequestedNotice(true)
      setRevision((value) => value + 1)
      onChanged()
    } catch (error) {
      if (error instanceof ApiError && error.detail && typeof error.detail === 'object' && 'unselected_item_ids' in error.detail) {
        setUnselected((error.detail as { unselected_item_ids: number[] }).unselected_item_ids)
      }
      // 거절된 요청은 화면의 상태 표시와 선택값을 그대로 둔다 (DESIGN.md).
      setSubmitError(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="readiness" aria-labelledby={`readiness-${caseId}`}>
      <h3 id={`readiness-${caseId}`}>준비 항목 체크</h3>
      {requestedNotice && <p role="status">확인 요청했습니다. 담당자가 확인합니다.</p>}
      {!editable && data.status !== '준비 확인 완료' && (
        <p>지금 상태({data.status})에서는 준비 여부를 바꾸거나 확인 요청할 수 없습니다.</p>
      )}

      <form onSubmit={handleSubmit}>
        <ul className="readiness-items">
          {data.preparation_items.map((item) => {
            const missing = unselected.includes(item.id)
            const name = `ready-${item.id}`
            return (
              <li key={item.id} className={missing ? 'readiness-item unselected' : 'readiness-item'}>
                <fieldset disabled={!editable || submitting} aria-describedby={missing ? `${name}-error` : undefined}>
                  <legend>
                    {item.text}
                    {item.translated_text && <span lang="vi"> / {item.translated_text}</span>}
                  </legend>
                  {item.supplement_reason && !item.supplement_resolved && (
                    <p className="error">보완 요청: {item.supplement_reason}</p>
                  )}
                  <label>
                    <input type="radio" name={name} checked={choices[item.id] === true} onChange={() => choose(item.id, true)} />
                    준비함
                  </label>
                  <label>
                    <input type="radio" name={name} checked={choices[item.id] === false} onChange={() => choose(item.id, false)} />
                    아직
                  </label>
                  {missing && <p id={`${name}-error`} className="error">준비 여부를 고르세요.</p>}
                </fieldset>
              </li>
            )
          })}
        </ul>
        {submitError && <p className="error" role="alert">{submitError}</p>}
        {editable && (
          <button type="submit" disabled={submitting}>
            {submitting ? '요청하는 중' : '확인 요청'}
          </button>
        )}
      </form>
    </section>
  )
}
