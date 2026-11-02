import { useEffect, useState } from 'react'
import { listCases } from '../api/cases'
import type { CaseSummary } from '../types'
import { CaseForm } from './CaseForm'
import { CaseList } from './CaseList'
import './MyCasesScreen.css'

export function MyCasesScreen() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [formOpen, setFormOpen] = useState(false)

  useEffect(() => {
    listCases()
      .then(setCases)
      .catch(() => setLoadFailed(true))
  }, [])

  const handleCreated = async () => {
    setFormOpen(false)
    setLoadFailed(false)
    try {
      setCases(await listCases())
    } catch {
      setLoadFailed(true)
    }
  }

  const openFormButton = !formOpen && (
    <button type="button" onClick={() => setFormOpen(true)}>
      새 준비 건 만들기
    </button>
  )

  return (
    <main className="my-cases">
      <h1>내 준비 건</h1>

      {loadFailed && (
        <p className="error" role="alert">
          준비 건 목록을 불러오지 못했습니다.
        </p>
      )}

      {cases === null && !loadFailed && <p>불러오는 중</p>}

      {cases !== null && cases.length === 0 && <p>아직 준비 건이 없습니다.</p>}

      {cases !== null && cases.length > 0 && <CaseList cases={cases} />}

      {cases !== null && openFormButton}

      {formOpen && <CaseForm onCreated={handleCreated} />}
    </main>
  )
}
