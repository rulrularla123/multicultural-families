import { ArrowUpRight } from 'lucide-react'
import { useApp } from '../AppContext'
import type { Citation } from '../api/types'

export default function CitationCard({ citation }: { citation: Citation }) {
  const { t, navigate } = useApp()
  return (
    <div className="citation-card">
      <div className="citation-card__head">
        <strong>[{citation.index}]</strong>
        <span className={`badge ${citation.verified ? 'badge--general' : 'badge--caution'}`}>
          {citation.verified ? t('chat.citation.verified') : t('chat.citation.unverified')}
        </span>
      </div>
      <span className="citation-card__quote">{citation.quote_ko}</span>
      {citation.quote_translation && citation.quote_translation !== citation.quote_ko && (
        <span>{citation.quote_translation}</span>
      )}
      <div>
        <button
          className="citation-card__link"
          onClick={() => navigate({ name: 'provision', id: citation.provision_id })}
        >
          {t('chat.viewProvision')} <ArrowUpRight size={13} aria-hidden />
        </button>
      </div>
    </div>
  )
}
