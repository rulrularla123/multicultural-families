import { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { getProvision, getRelatedProvisions } from '../api/provisions'
import type { ProvisionDetail, RelatedProvision } from '../api/types'
import { ErrorBox, Loading } from '../components/States'

export default function Provision({ id }: { id: string }) {
  const { lang, t, navigate, back, canGoBack } = useApp()
  const [provision, setProvision] = useState<ProvisionDetail | null>(null)
  const [related, setRelated] = useState<RelatedProvision[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    Promise.all([getProvision(id), getRelatedProvisions(id).catch(() => [])])
      .then(([p, r]) => {
        if (!active) return
        setProvision(p)
        setRelated(r)
      })
      .catch(() => {
        if (active) setError(t('provision.error'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const summary = provision ? (lang === 'vi' ? provision.summary_vi : provision.summary_ko) : null

  return (
    <div className="stack">
      {canGoBack && (
        <button className="back-link" onClick={back}>
          ← {t('provision.back')}
        </button>
      )}

      {loading && <Loading label={t('provision.loading')} />}
      {error && <ErrorBox message={error} />}

      {provision && !loading && (
        <div className="stack">
          <div>
            <p className="provision-path">{provision.path}</p>
            <h1 className="page-title">{provision.number_label}</h1>
            <span className={`badge ${provision.effective ? 'badge--general' : 'badge--caution'}`}>
              {provision.effective ? t('provision.current') : t('provision.notCurrent')}
            </span>
          </div>

          {summary && <div className="card">{summary}</div>}

          <div className="provision-text">{provision.full_text_ko}</div>

          {provision.source_url && (
            <a href={provision.source_url} target="_blank" rel="noreferrer" className="back-link">
              {t('provision.source')} ↗
            </a>
          )}

          <div>
            <h2 className="page-title" style={{ fontSize: 15 }}>
              {t('provision.related')}
            </h2>
            {related.length === 0 && <p className="page-desc">{t('provision.related.empty')}</p>}
            {related.map((r, i) => (
              <button
                key={`${r.provision_id}-${i}`}
                className="provision-related-item"
                onClick={() => navigate({ name: 'provision', id: r.provision_id })}
              >
                <strong>{r.rel}</strong> · {r.path}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
