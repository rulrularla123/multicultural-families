import { apiDelete, apiGet, apiPost, apiUpload } from './client'
import type { Analysis, AnalysisListItem, AnswerIn, Lang, SampleDoc } from './types'

export function uploadDocument(file: File, lang: Lang): Promise<Analysis> {
  const form = new FormData()
  form.append('file', file)
  form.append('lang', lang)
  return apiUpload<Analysis>('/documents', form)
}

export function listSamples(): Promise<SampleDoc[]> {
  return apiGet<SampleDoc[]>('/documents/samples')
}

export function createFromSample(sampleId: string, lang: Lang): Promise<Analysis> {
  const form = new FormData()
  form.append('lang', lang)
  return apiUpload<Analysis>(`/documents/samples/${sampleId}`, form)
}

export function listMyAnalyses(): Promise<AnalysisListItem[]> {
  return apiGet<AnalysisListItem[]>('/documents')
}

export function getAnalysis(id: string): Promise<Analysis> {
  return apiGet<Analysis>(`/documents/${id}`)
}

export function submitAnswers(id: string, answers: AnswerIn[]): Promise<Analysis> {
  return apiPost<Analysis>(`/documents/${id}/answers`, { answers })
}

export function setChecklistItem(id: string, index: number, done: boolean): Promise<Analysis> {
  return apiPost<Analysis>(`/documents/${id}/checklist`, { index, done })
}

export function cancelAnalysis(id: string): Promise<Analysis> {
  return apiPost<Analysis>(`/documents/${id}/cancel`)
}

export function deleteAnalysis(id: string): Promise<void> {
  return apiDelete(`/documents/${id}`)
}
