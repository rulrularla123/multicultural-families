import { apiDelete, apiGet, apiPost } from './client'
import { prepareUpload } from '../documents/prepareUpload'
import type { Analysis, AnalysisListItem, AnswerIn, Lang } from './types'

export async function uploadDocument(file: File, lang: Lang): Promise<Analysis> {
  const prepared = await prepareUpload(file)
  return apiPost<Analysis>('/documents', { ...prepared, lang })
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
