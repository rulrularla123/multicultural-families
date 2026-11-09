import { useEffect, useState } from 'react'
import { errorMessage } from '../api/cases'
import { getApprovedResult, KIND_LABELS } from '../api/workflow'
import type { ApprovedResult } from '../api/workflow'
import type { DemoAccount } from '../types'
import { CompletionNotice } from './CompletionScreen'

type Props = {
  caseId: number
  account: DemoAccount
}

// US-03 (정상) 2: 승인된 항목을 한국어와 베트남어로 나란히, 항목마다 근거 출처·기준일과 함께 보여 준다.
export function ApprovedResultView({ caseId, account }: Props) {
  const [result, setResult] = useState<ApprovedResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getApprovedResult(caseId, account, controller.signal)
      .then((loaded) => { if (!controller.signal.aborted) setResult(loaded) })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(errorMessage(reason)) })
    return () => controller.abort()
  }, [caseId, account])

  if (error) return <p className="error" role="alert">승인 결과를 불러오지 못했습니다. {error}</p>
  if (!result) return <p role="status">승인 결과를 불러오는 중</p>

  return (
    <section className="approved-result" aria-labelledby={`approved-${caseId}`}>
      <h3 id={`approved-${caseId}`}>담당자가 승인한 안내</h3>
      <table className="case-list bilingual">
        <thead>
          <tr>
            <th scope="col">분류</th>
            <th scope="col">한국어</th>
            <th scope="col" lang="vi">Tiếng Việt</th>
            <th scope="col">근거 출처·기준일</th>
          </tr>
        </thead>
        <tbody>
          {result.items.map((item) => (
            <tr key={item.id}>
              <td>{KIND_LABELS[item.kind] ?? item.kind}</td>
              <td className="pre-wrap">{item.text}</td>
              <td className="pre-wrap" lang="vi">{item.translated_text}</td>
              <td>{item.source} · {item.checked_on}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.completion_notice && <CompletionNotice notice={result.completion_notice} />}
    </section>
  )
}
