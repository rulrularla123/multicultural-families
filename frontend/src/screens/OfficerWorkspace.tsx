import { useState } from 'react'
import { CriteriaScreen } from './CriteriaScreen'
import { OfficerReviewScreen } from './OfficerReviewScreen'

export function OfficerWorkspace() {
  const [page, setPage] = useState<'review' | 'criteria'>('review')
  return <>
    <nav className="officer-nav" aria-label="담당자 메뉴">
      <button aria-pressed={page === 'review'} onClick={() => setPage('review')}>준비 건 검토</button>
      <button aria-pressed={page === 'criteria'} onClick={() => setPage('criteria')}>기준 관리</button>
    </nav>
    {page === 'criteria' ? <CriteriaScreen /> : <OfficerReviewScreen />}
  </>
}
