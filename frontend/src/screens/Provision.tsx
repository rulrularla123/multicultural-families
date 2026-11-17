import { ArrowUpRight, ChevronLeft } from 'lucide-react'
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
          <ChevronLeft size={15} aria-hidden /> {t('provision.back')}
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

          <VersionBox provision={provision} />

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

function VersionBox({ provision: p }: { provision: ProvisionDetail }) {
  const { lang, t } = useApp()
  const status = p.version_status ?? 'unknown'
  const warning = p.version_warning ?? (status === 'outdated' ? 'outdated' : 'unchecked')
  const fmt = (iso: string | null | undefined, time = false) =>
    iso
      ? new Intl.DateTimeFormat(lang === 'vi' ? 'vi-VN' : 'ko-KR', {
          dateStyle: 'medium',
          ...(time ? { timeStyle: 'short', timeZone: 'Asia/Seoul' } : {}),
        }).format(new Date(iso))
      : '—'
  const badge = status === 'outdated' ? 'badge--caution' : warning ? 'badge--caution' : 'badge--general'
  const official = p.official_url ?? p.source_url

  return (
    <section className="card version-box" aria-label={t('provision.version.title')}>
      <strong>{t('provision.version.title')}</strong>
      <dl className="facts">
        <div>
          <dt>{t('provision.version.promulgated')}</dt>
          <dd>
            {fmt(p.issued_date)}
            {p.promulgation_no ? ` (${p.promulgation_no})` : ''}
          </dd>
        </div>
        <div>
          <dt>{t('provision.version.effective')}</dt>
          <dd>{fmt(p.effective_from)}</dd>
        </div>
        <div>
          <dt>{t('provision.version.checked')}</dt>
          <dd>
            <span className={`badge ${badge}`}>{t(`provision.version.${status}`)}</span>{' '}
            {p.version_checked_at ? fmt(p.version_checked_at, true) : t('provision.version.never')}
          </dd>
        </div>
      </dl>
      {status === 'upcoming' && p.upcoming_effective_from && (
        <p className="page-desc">
          {t('provision.version.upcomingNote').replace('{date}', fmt(p.upcoming_effective_from))}
        </p>
      )}
      {warning === 'outdated' && (
        <p className="version-box__warn">{t('provision.version.outdatedNote')}</p>
      )}
      {warning === 'unchecked' && <p className="page-desc">{t('provision.version.uncheckedNote')}</p>}
      <div className="version-box__links">
        {official && (
          <a href={official} target="_blank" rel="noreferrer" className="back-link">
            {t('provision.official')} <ArrowUpRight size={13} aria-hidden />
          </a>
        )}
        {p.version_url && (
          <a href={p.version_url} target="_blank" rel="noreferrer" className="back-link">
            {t('provision.versionSource')} <ArrowUpRight size={13} aria-hidden />
          </a>
        )}
      </div>
    </section>
  )
}
