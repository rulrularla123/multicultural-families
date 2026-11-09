import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api/cases'
import { formatDate, getReadiness, requestConfirmation } from '../api/preparationCheck'
import type { ReadinessCase } from '../api/preparationCheck'
import type { UserAccount } from '../types'
import { CompletionNotice } from './CompletionScreen'
import './MyCasesScreen.css'
import './PreparationCheckScreen.css'

type Props = {
  caseId: number
  account: UserAccount
}

type Loaded = { caseId: number; account: UserAccount; revision: number; data?: ReadinessCase; error?: string }
type Choices = Record<number, boolean | null>

// DESIGN.md "준비 항목 체크 (이용자)", F-06 / US-05. 임시 응답(api/preparationCheck.ts)을 쓴다.
export function PreparationCheckScreen({ caseId, account }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [revision, setRevision] = useState(0)
  const [choices, setChoices] = useState<Choices>({})
  const [unselected, setUnselected] = useState<number[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [requestedNotice, setRequestedNotice] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getReadiness(caseId, account, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setLoaded({ caseId, account, revision, data })
        setChoices(Object.fromEntries(data.items.map((item) => [item.id, item.is_ready])))
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
  const data = current?.data
  const editable = data?.status === '서류 준비중'

  const choose = (itemId: number, value: boolean) => {
    setChoices((previous) => ({ ...previous, [itemId]: value }))
    setUnselected((previous) => previous.filter((id) => id !== itemId))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!data) return
    setSubmitError(null)
    setRequestedNotice(false)
    setSubmitting(true)
    try {
      const result = await requestConfirmation(data.case_id, choices, account)
      if (!result.ok) {
        // US-05 실패·거절 1번: 미선택 항목을 표시하고 상태는 그대로 둔다.
        setUnselected(result.unselected_item_ids)
        setSubmitError(`준비 여부를 고르지 않은 항목이 ${result.unselected_item_ids.length}개 있습니다.`)
        return
      }
      setRequestedNotice(true)
      // 화면 상태는 서버(임시 응답)가 준 값으로만 바꾼다.
      setRevision((value) => value + 1)
    } catch (error) {
      // 거절된 요청은 화면의 상태 표시와 선택값을 그대로 둔다 (DESIGN.md).
      setSubmitError(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="my-cases">
      <h1>준비 항목 체크</h1>
      {!current && <p role="status">불러오는 중</p>}
      {current?.error && <p className="error" role="alert">{current.error}</p>}
      {data && (
        <section className="case-detail" aria-labelledby="readiness-title">
          <h2 id="readiness-title">준비 건 {data.case_id}</h2>
          {requestedNotice && <p role="status">확인 요청했습니다. 담당자가 확인합니다.</p>}
          <dl>
            <dt>현재 상태</dt>
            <dd>{data.status}</dd>
            {data.requested_at && (
              <>
                <dt>확인 요청 일시</dt>
                <dd>{formatDate(data.requested_at)}</dd>
              </>
            )}
          </dl>

          {data.status === '준비 확인 완료' && <CompletionNotice />}
          {!editable && data.status !== '준비 확인 완료' && (
            <p>지금 상태({data.status})에서는 준비 여부를 바꾸거나 확인 요청할 수 없습니다.</p>
          )}

          <form onSubmit={handleSubmit}>
            <ul className="readiness-items">
              {data.items.map((item) => {
                const missing = unselected.includes(item.id)
                const name = `ready-${item.id}`
                return (
                  <li key={item.id} className={missing ? 'readiness-item unselected' : 'readiness-item'}>
                    <fieldset disabled={!editable || submitting} aria-describedby={missing ? `${name}-error` : undefined}>
                      <legend>{item.content}</legend>
                      <label>
                        <input
                          type="radio"
                          name={name}
                          checked={choices[item.id] === true}
                          onChange={() => choose(item.id, true)}
                        />
                        준비함
                      </label>
                      <label>
                        <input
                          type="radio"
                          name={name}
                          checked={choices[item.id] === false}
                          onChange={() => choose(item.id, false)}
                        />
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
      )}
    </main>
  )
}
