import { ArrowUpRight } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../AppContext'
import { setChecklistItem } from '../api/documents'
import type { Analysis, Clause } from '../api/types'

const CATEGORY_ORDER: Clause['category'][] = ['must_check', 'caution', 'general']

export default function Result({ analysis, onChanged }: { analysis: Analysis; onChanged: () => void }) {
  const { t, navigate } = useApp()
  const result = analysis.result
  const checklist = analysis.checklist ?? []
  const [pending, setPending] = useState<Set<number>>(new Set())

  if (!result) return null

  const sortedClauses = [...result.clauses].sort(
    (a, b) => CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category),
  )

  async function toggle(index: number, done: boolean) {
    setPending((prev) => new Set(prev).add(index))
    try {
      await setChecklistItem(analysis.id, index, done)
      onChanged()
    } finally {
      setPending((prev) => {
        const next = new Set(prev)
        next.delete(index)
        return next
      })
    }
  }

  return (
    <div className="stack">
      <h1 className="page-title">{result.title}</h1>

      {result.not_immigration && <div className="state state--error">{t('result.notImmigration')}</div>}

      <div className="result-summary-card">
        <p style={{ margin: 0, fontWeight: 600 }}>{t('result.summary')}</p>
        <p style={{ margin: '6px 0' }}>{result.summary_simple || result.summary}</p>
        {result.situation_note && (
          <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)' }}>
            {t('result.situationNote')}: {result.situation_note}
          </p>
        )}

        <div className="result-counts">
          <span className="badge badge--must_check">
            {t('result.counts.must_check')} {result.counts.must_check}
          </span>
          <span className="badge badge--caution">
            {t('result.counts.caution')} {result.counts.caution}
          </span>
          <span className="badge badge--general">
            {t('result.counts.general')} {result.counts.general}
          </span>
        </div>

        <span className={`badge badge--confidence-${result.confidence}`}>
          {t('result.confidence')}: {t(`chat.confidence.${result.confidence}`)}
        </span>

        {result.needs_expert && (
          <div className="state state--error" style={{ marginTop: 8, textAlign: 'left' }}>
            <strong>{t('result.needsExpert')}</strong>
            <p style={{ margin: '4px 0 0' }}>{t('result.needsExpert.desc')}</p>
          </div>
        )}
      </div>

      <div className="result-grid">
        <div>
          <h2 className="section-title">{t('result.clauses.title')}</h2>
          <div className="stack" style={{ gap: 8 }}>
            {sortedClauses.map((clause) => (
              <div key={clause.id} className={`clause-card ${clause.category}`}>
                <div className="clause-card__head">
                  <p className="clause-card__title">{clause.title}</p>
                  <span className={`badge badge--${clause.category}`}>{t(`result.category.${clause.category}`)}</span>
                </div>
                <p style={{ margin: 0, fontSize: 13 }}>{clause.explanation_simple}</p>
                {clause.highlights.length > 0 && (
                  <div>
                    {clause.highlights.map((h, i) => (
                      <span key={i} className="highlight-chip">
                        {h}
                      </span>
                    ))}
                  </div>
                )}
                {(clause.explanation_detail || clause.citations.length > 0) && (
                  <details>
                    <summary>{t('result.clauses.viewOriginal')}</summary>
                    <div className="clause-card__detail">
                      <p>{clause.explanation_detail}</p>
                      {clause.citations.map((c, i) => (
                        <button
                          key={i}
                          className="citation-card__link"
                          style={{ display: 'block', marginTop: 4 }}
                          onClick={() => navigate({ name: 'provision', id: c.provision_id })}
                        >
                          {c.provision_id} <ArrowUpRight size={13} aria-hidden />
                        </button>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>

        <aside className="result-aside">
          {result.cautions.length > 0 && (
            <div>
              <h2 className="section-title">{t('result.cautions.title')}</h2>
              <div className="stack" style={{ gap: 8 }}>
                {result.cautions.map((c, i) => (
                  <div key={i} className="caution-card">
                    <p style={{ margin: 0, fontWeight: 600 }}>{c.title}</p>
                    <p style={{ margin: '4px 0 0', fontSize: 13 }}>{c.explanation_simple}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.next_actions.length > 0 && (
            <div>
              <h2 className="section-title">
                {t('result.checklist.title')}
                <span className="count">
                  {checklist.filter((c) => c.done).length} / {result.next_actions.length}
                </span>
              </h2>
              <div className="checklist-progress" aria-hidden="true">
                <span
                  style={{
                    width: `${(checklist.filter((c) => c.done).length / Math.max(1, result.next_actions.length)) * 100}%`,
                  }}
                />
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {result.next_actions.map((action, index) => {
                  const done = checklist.find((c) => c.index === index)?.done ?? false
                  return (
                    <label key={action.id} className={`next-action-item${done ? ' done' : ''}`}>
                      <input
                        type="checkbox"
                        checked={done}
                        disabled={pending.has(index)}
                        onChange={(e) => void toggle(index, e.target.checked)}
                      />
                      <span>
                        <span className="next-action-text">{action.text}</span>
                        {action.due && <span className="next-action-due">{action.due}</span>}
                      </span>
                    </label>
                  )
                })}
              </div>
            </div>
          )}

          {result.open_questions.length > 0 && (
            <div>
              <h2 className="section-title">{t('result.openQuestions.title')}</h2>
              <div className="stack" style={{ gap: 8 }}>
                {result.open_questions.map((q) => (
                  <div key={q.id} className="card">
                    <p style={{ margin: 0, fontWeight: 600 }}>{q.question}</p>
                    <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>{q.why}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button className="btn btn--block" onClick={() => navigate({ name: 'chat', analysisId: analysis.id })}>
            {t('result.askMore')}
          </button>
        </aside>
      </div>
    </div>
  )
}
