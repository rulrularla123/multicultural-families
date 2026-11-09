import { useCallback, useEffect, useRef, useState } from 'react'
import { useApp } from '../AppContext'
import { getAnalysis } from '../api/documents'
import type { Analysis } from '../api/types'
import { ErrorBox, Loading } from '../components/States'
import Questions from './Questions'
import Progress from './Progress'
import Result from './Result'

const POLL_MS = 2000

export default function DocumentFlow({ id }: { id: string }) {
  const { t, navigate } = useApp()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      const a = await getAnalysis(id)
      setAnalysis(a)
      setError(null)
    } catch {
      setError(t('common.error.notFound'))
    }
  }, [id, t])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!analysis) return
    const active = analysis.status === 'uploaded' || analysis.status === 'analyzing'
    if (!active) return
    timerRef.current = window.setTimeout(() => void load(), POLL_MS)
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [analysis, load])

  useEffect(() => {
    if (analysis?.status === 'canceled') navigate({ name: 'myDocuments' })
  }, [analysis, navigate])

  if (error) return <ErrorBox message={error} onRetry={() => void load()} />
  if (!analysis) return <Loading />

  switch (analysis.status) {
    case 'uploaded':
      return <Loading label={t('progress.title')} />
    case 'questions':
      return <Questions analysis={analysis} onSubmitted={() => void load()} />
    case 'analyzing':
    case 'failed':
      return <Progress analysis={analysis} onChanged={() => void load()} />
    case 'review':
    case 'done':
      return <Result analysis={analysis} onChanged={() => void load()} />
    case 'canceled':
      return null
    default:
      return null
  }
}
