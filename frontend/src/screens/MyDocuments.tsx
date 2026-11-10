import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { deleteAnalysis, listMyAnalyses } from '../api/documents'
import type { AnalysisListItem } from '../api/types'
import AnalysisTable from '../components/AnalysisTable'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorBox, Loading } from '../components/States'

export default function MyDocuments() {
  const { t, navigate } = useApp()
  const [items, setItems] = useState<AnalysisListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  function load() {
    setError(null)
    listMyAnalyses()
      .then(setItems)
      .catch(() => setError(t('common.error.generic')))
  }

  useEffect(load, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function remove(id: string) {
    if (!window.confirm(t('myDocuments.deleteConfirm'))) return
    await deleteAnalysis(id)
    load()
  }

  return (
    <div>
      <PageHeader
        eyebrow={t('myDocuments.eyebrow')}
        title={
          <>
            {t('myDocuments.title')} {items && <span style={{ color: 'var(--faint)' }}>{items.length}</span>}
          </>
        }
        actions={
          <button className="btn" onClick={() => navigate({ name: 'newDocument' })}>
            <Plus size={14} strokeWidth={2} aria-hidden /> {t('myDocuments.newDoc')}
          </button>
        }
      />

      {error && <ErrorBox message={error} onRetry={load} />}
      {!items && !error && <Loading />}
      {items && items.length === 0 && (
        <EmptyState
          message={t('myDocuments.empty')}
          action={
            <button className="btn" onClick={() => navigate({ name: 'newDocument' })}>
              {t('myDocuments.newDoc')}
            </button>
          }
        />
      )}
      {items && items.length > 0 && <AnalysisTable items={items} onDelete={(id) => void remove(id)} />}
    </div>
  )
}
