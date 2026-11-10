import { useState } from 'react'
import { useApp } from '../AppContext'
import { cancelAnalysis, submitAnswers } from '../api/documents'
import type { Analysis } from '../api/types'
import { ErrorBox } from '../components/States'

const STEPS = ['extracted', 'searching', 'analyzing', 'verifying']

export default function Progress({ analysis, onChanged }: { analysis: Analysis; onChanged: () => void }) {
  const { t, navigate } = useApp()
  const [busy, setBusy] = useState(false)
  const currentIndex = STEPS.indexOf(analysis.stage ?? '')

  async function cancel() {
    setBusy(true)
    try {
      await cancelAnalysis(analysis.id)
      navigate({ name: 'myDocuments' })
    } finally {
      setBusy(false)
    }
  }

  async function retry() {
    setBusy(true)
    try {
      await submitAnswers(analysis.id, analysis.answers ?? [])
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  if (analysis.status === 'failed') {
    return (
      <div className="stack">
        <h1 className="page-title">{t('progress.failed.title')}</h1>
        <ErrorBox message={analysis.error ?? t('upload.error.generic')} />
        <button className="btn" disabled={busy} onClick={() => void retry()}>
          {t('progress.failed.retry')}
        </button>
      </div>
    )
  }

  return (
    <div className="stack">
      <h1 className="page-title">{t('progress.title')}</h1>
      <div className="progress-steps">
        {STEPS.map((step, i) => (
          <div
            key={step}
            className={`progress-step${i === currentIndex ? ' active' : ''}${
              currentIndex >= 0 && i < currentIndex ? ' done' : ''
            }`}
          >
            <span className="progress-dot" />
            {t(`progress.stage.${step}`)}
          </div>
        ))}
      </div>
      <button className="btn btn--secondary" disabled={busy} onClick={() => void cancel()}>
        {t('progress.cancel')}
      </button>
    </div>
  )
}
