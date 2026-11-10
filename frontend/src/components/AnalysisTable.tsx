import { ChevronRight } from 'lucide-react'
import { useApp } from '../AppContext'
import type { AnalysisListItem } from '../api/types'

function Num({ value, kind }: { value: number | undefined; kind: string }) {
  if (value === undefined) return <span className="table__num none">—</span>
  return <span className={`table__num ${value > 0 ? kind : 'none'}`}>{value}</span>
}

export default function AnalysisTable({
  items,
  onDelete,
}: {
  items: AnalysisListItem[]
  onDelete?: (id: string) => void
}) {
  const { t, lang, navigate } = useApp()
  const fmt = new Intl.DateTimeFormat(lang === 'vi' ? 'vi-VN' : 'ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  return (
    <div className="table" role="table">
      <div className="table__head" role="row">
        <span>{t('table.document')}</span>
        <span>{t('table.status')}</span>
        <span style={{ textAlign: 'center' }}>{t('result.counts.must_check')}</span>
        <span style={{ textAlign: 'center' }}>{t('result.counts.caution')}</span>
        <span style={{ textAlign: 'center' }}>{t('result.counts.general')}</span>
        <span>{t('table.created')}</span>
        <span />
      </div>
      {items.map((a) => (
        <div key={a.id} style={{ position: 'relative' }}>
          <button className="table__row" role="row" onClick={() => navigate({ name: 'document', id: a.id })}>
            <span className="table__title">
              {a.title ?? a.filename}
              <span className="table__sub">{a.doc_type_label ?? a.filename}</span>
            </span>
            <span>
              <span className={`badge badge--status s-${a.status}`}>{t(`myDocuments.status.${a.status}`)}</span>
            </span>
            <Num value={a.counts?.must_check} kind="must_check" />
            <Num value={a.counts?.caution} kind="caution" />
            <Num value={a.counts?.general} kind="general" />
            <span className="table__date">{fmt.format(new Date(a.created_at))}</span>
            <span className="table__go">
              <ChevronRight size={16} strokeWidth={2} aria-hidden />
            </span>
          </button>
          {onDelete && (
            <button
              className="btn btn--ghost table__delete"
              onClick={() => onDelete(a.id)}
              aria-label={t('myDocuments.delete')}
            >
              {t('myDocuments.delete')}
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
