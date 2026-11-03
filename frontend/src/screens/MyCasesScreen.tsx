import { useEffect, useState } from 'react'
import { errorMessage, listCases } from '../api/cases'
import type { CaseSummary, UserAccount } from '../types'
import { CaseDetailPanel } from './CaseDetailPanel'
import { CaseForm } from './CaseForm'
import { CaseList } from './CaseList'
import './MyCasesScreen.css'

type Listing = {
  account: UserAccount
  revision: number
  cases: CaseSummary[]
  error?: string
}

type Props = {
  account: UserAccount
}

export function MyCasesScreen({ account }: Props) {
  const [listing, setListing] = useState<Listing | null>(null)
  const [revision, setRevision] = useState(0)
  const [formOpen, setFormOpen] = useState(false)
  const [openedId, setOpenedId] = useState<number | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    listCases(account, controller.signal)
      .then((cases) => {
        if (!controller.signal.aborted) setListing({ account, revision, cases })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setListing({ account, revision, cases: [], error: errorMessage(error) })
        }
      })
    return () => controller.abort()
  }, [account, revision])

  // 계정을 바꾸는 순간 이전 계정의 목록을 숨기고 늦은 응답도 무시한다.
  const current = listing?.account === account && listing.revision === revision ? listing : null
  const cases = current && !current.error ? current.cases : null
  const handleCreated = () => {
    setFormOpen(false)
    setRevision((value) => value + 1)
  }

  return (
    <main className="my-cases">
      <h1>내 준비 건</h1>
      {current?.error && (
        <div className="error" role="alert">
          <p>준비 건 목록을 불러오지 못했습니다. {current.error}</p>
          <button type="button" onClick={() => setRevision((value) => value + 1)}>다시 불러오기</button>
        </div>
      )}
      {!current && <p role="status">불러오는 중</p>}
      {cases !== null && cases.length === 0 && <p>아직 준비 건이 없습니다.</p>}
      {cases !== null && cases.length > 0 && <CaseList cases={cases} onOpen={setOpenedId} />}
      {openedId !== null && (
        <CaseDetailPanel caseId={openedId} account={account} onClose={() => setOpenedId(null)} />
      )}
      {cases !== null && !formOpen && (
        <button type="button" onClick={() => setFormOpen(true)}>새 준비 건 만들기</button>
      )}
      {formOpen && <CaseForm account={account} onCreated={handleCreated} onCancel={() => setFormOpen(false)} />}
    </main>
  )
}
