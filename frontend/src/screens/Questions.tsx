import { useState } from 'react'
import { useApp } from '../AppContext'
import { ApiError } from '../api/client'
import { submitAnswers } from '../api/documents'
import type { Analysis, AnswerIn } from '../api/types'
import { ErrorBox } from '../components/States'

type AnswerState = Record<string, { option_id?: string; text?: string }>

export default function Questions({ analysis, onSubmitted }: { analysis: Analysis; onSubmitted: () => void }) {
  const { t } = useApp()
  const intake = analysis.intake
  const [answers, setAnswers] = useState<AnswerState>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [missing, setMissing] = useState<Set<string>>(new Set())

  if (!intake) return null

  function pick(qId: string, optionId: string) {
    setAnswers((prev) => ({ ...prev, [qId]: { option_id: optionId } }))
  }

  function freeText(qId: string, text: string) {
    setAnswers((prev) => ({ ...prev, [qId]: { text } }))
  }

  async function submit() {
    setError(null)
    const payload: AnswerIn[] = intake!.questions.map((q) => ({
      question_id: q.id,
      option_id: answers[q.id]?.option_id ?? null,
      text: answers[q.id]?.text ?? null,
    }))
    const missingIds = payload.filter((a) => !a.option_id && !a.text).map((a) => a.question_id)
    if (missingIds.length > 0) {
      setMissing(new Set(missingIds))
      setError(t('questions.missing'))
      return
    }
    setBusy(true)
    try {
      await submitAnswers(analysis.id, payload)
      onSubmitted()
    } catch (e) {
      if (e instanceof ApiError && e.missingQuestionIds) {
        setMissing(new Set(e.missingQuestionIds))
        setError(t('questions.missing'))
      } else {
        setError(t('upload.error.generic'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <h1 className="page-title">{t('questions.title')}</h1>
      <div className="card">
        <p style={{ margin: 0, fontWeight: 600 }}>{intake.title}</p>
        <p style={{ margin: '6px 0 0', color: 'var(--muted)', fontSize: 13 }}>{intake.summary}</p>
      </div>

      {intake.basic_info.length > 0 && (
        <div>
          <p className="page-desc" style={{ marginBottom: 6 }}>
            {t('questions.basicInfo')}
          </p>
          <div className="basic-info-grid">
            {intake.basic_info.map((info, i) => (
              <div key={i} className="basic-info-item">
                <span className="label">{info.label}</span>
                {info.value}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <ErrorBox message={error} />}

      {intake.questions.map((q) => (
        <div key={q.id} className={`question-card${missing.has(q.id) ? '' : ''}`}>
          <p style={{ fontWeight: 600, margin: 0 }}>{q.text}</p>
          <p className="question-why">
            {t('questions.why')} {q.why}
          </p>
          <div className="question-options">
            {q.options.map((opt) => (
              <button
                key={opt.id}
                className={`option-pill${answers[q.id]?.option_id === opt.id ? ' selected' : ''}`}
                onClick={() => pick(q.id, opt.id)}
                type="button"
              >
                {opt.label}
              </button>
            ))}
          </div>
          {q.allow_free_text && (
            <input
              className="question-freetext"
              placeholder={t('questions.freeTextPlaceholder')}
              value={answers[q.id]?.text ?? ''}
              onChange={(e) => freeText(q.id, e.target.value)}
            />
          )}
        </div>
      ))}

      <button className="btn btn--block" disabled={busy} onClick={() => void submit()}>
        {busy ? t('questions.submitting') : t('questions.submit')}
      </button>
    </div>
  )
}
