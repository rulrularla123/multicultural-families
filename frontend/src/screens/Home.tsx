import { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { listMyAnalyses } from '../api/documents'
import type { AnalysisListItem } from '../api/types'
import { Loading } from '../components/States'

export default function Home() {
  const { t, navigate } = useApp()
  const [recent, setRecent] = useState<AnalysisListItem[] | null>(null)

  useEffect(() => {
    let active = true
    listMyAnalyses()
      .then((list) => {
        if (active) setRecent(list.slice(0, 3))
      })
      .catch(() => {
        if (active) setRecent([])
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">{t('home.tagline')}</h1>
      </div>

      <div className="home-cards">
        <button className="home-card" onClick={() => navigate({ name: 'chat' })}>
          <p className="home-card__title">{t('home.card.chat.title')}</p>
          <p className="home-card__desc">{t('home.card.chat.desc')}</p>
        </button>
        <button className="home-card" onClick={() => navigate({ name: 'newDocument' })}>
          <p className="home-card__title">{t('home.card.documents.title')}</p>
          <p className="home-card__desc">{t('home.card.documents.desc')}</p>
        </button>
      </div>

      <div>
        <h2 className="page-title" style={{ fontSize: 16 }}>
          {t('home.recent.title')}
        </h2>
        {recent === null && <Loading />}
        {recent !== null && recent.length === 0 && <p className="page-desc">{t('home.recent.empty')}</p>}
        {recent !== null && recent.length > 0 && (
          <div className="stack" style={{ gap: 8 }}>
            {recent.map((a) => (
              <button
                key={a.id}
                className="home-recent-item"
                onClick={() => navigate({ name: 'document', id: a.id })}
              >
                <span>{a.title ?? a.filename}</span>
                <span className="badge badge--status">{t(`myDocuments.status.${a.status}`)}</span>
              </button>
            ))}
            <button className="back-link" onClick={() => navigate({ name: 'myDocuments' })}>
              {t('home.recent.viewAll')} →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
