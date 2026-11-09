import { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { deleteAnalysis, listMyAnalyses } from '../api/documents'
import type { AnalysisListItem } from '../api/types'
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
    <div className="stack">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          {t('myDocuments.title')}
        </h1>
        <button className="btn" onClick={() => navigate({ name: 'newDocument' })}>
          {t('myDocuments.newDoc')}
        </button>
      </div>

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

      {items && items.length > 0 && (
        <div className="stack" style={{ gap: 8 }}>
          {items.map((item) => (
            <div key={item.id} className="doc-list-item">
              <button className="doc-list-item__main" onClick={() => navigate({ name: 'document', id: item.id })}>
                <p className="doc-list-item__title">{item.title ?? item.filename}</p>
                <p className="doc-list-item__meta">
                  {item.doc_type_label ?? item.filename} ·{' '}
                  {new Date(item.created_at).toLocaleDateString('ko-KR')}
                </p>
              </button>
              <span className="badge badge--status">{t(`myDocuments.status.${item.status}`)}</span>
              <button className="btn btn--danger" onClick={() => void remove(item.id)}>
                {t('myDocuments.delete')}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
