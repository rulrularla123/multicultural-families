export type Lang = 'vi' | 'ko'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface Citation {
  index: number
  provision_id: string
  quote_ko: string
  quote_translation: string
  verified: boolean
  verify_error: string | null
}

export interface SourceOut {
  provision_id: string
  document_id: string
  title: string
  path: string
  retrieved_by: string
}

export interface NumberCheck {
  text: string
  values: number[]
  unit: 'krw' | 'months' | 'days' | 'years'
  status: 'verified' | 'not_found'
  provision_id: string | null
  missing: number[]
}

export interface AnswerPayload {
  kind?: 'answer' | 'smalltalk' | 'unclear' | 'no_results'
  lang: Lang
  as_of: string
  answer: string
  citations: Citation[]
  confidence: 'high' | 'medium' | 'low'
  needs_expert: boolean
  follow_up_questions: string[]
  notice: string | null
  disclaimer: string
  sources: SourceOut[]
  search_queries?: string[]
  number_checks: NumberCheck[]
  analysis_id?: string | null
}

export interface StageEvent {
  stage: string
  label: string
}

export interface ProvisionDetail {
  id: string
  document_id: string
  document_title: string
  doc_type: string
  level: string
  number_label: string
  path: string
  full_text_ko: string
  summary_vi: string | null
  summary_ko: string | null
  effective: boolean
  effective_from: string | null
  effective_to: string | null
  status: string
  source_url: string | null
  reviewed: boolean
  reviewed_by: string | null
  reviewed_at: string | null
}

export interface RelatedProvision {
  provision_id: string
  path: string
  rel: string
  direction: 'incoming' | 'outgoing'
  evidence: string
}

export interface Option {
  id: string
  label: string
}

export interface Question {
  id: string
  text: string
  why: string
  options: Option[]
  allow_free_text: boolean
}

export interface InfoItem {
  key: string
  label: string
  value: string
}

export interface Intake {
  doc_kind: string
  doc_type_label: string
  title: string
  summary: string
  basic_info: InfoItem[]
  questions: Question[]
}

export interface Fact {
  id: string
  key: string
  label: string
  value: string
  source: 'document' | 'user'
  confirmed: boolean
}

export interface AnswerIn {
  question_id: string
  option_id?: string | null
  text?: string | null
}

export type AnalysisStatus = 'uploaded' | 'questions' | 'analyzing' | 'failed' | 'review' | 'done' | 'canceled'

export interface ClauseCitation {
  path: string
  quote_ko: string
  provision_id: string
  quote_translation: string
}

export interface Clause {
  id: string
  text: string
  pages: number[]
  title: string
  category: 'must_check' | 'caution' | 'general'
  citations: ClauseCitation[]
  highlights: string[]
  explanation: string
  explanation_detail: string
  explanation_simple: string
}

export interface Caution {
  kind: 'risk' | 'missing' | 'deadline' | 'ambiguity' | 'outdated'
  title: string
  detail: string
  citations: ClauseCitation[]
  clause_ids: string[]
  explanation: string
  explanation_detail: string
  explanation_simple: string
}

export interface NextAction {
  id: string
  due: string | null
  text: string
  clause_id: string | null
}

export interface OpenQuestion {
  id: string
  why: string
  question: string
}

export interface AnalysisResult {
  as_of: string
  title: string
  counts: { must_check: number; caution: number; general: number }
  notice: string | null
  clauses: Clause[]
  summary: string
  summary_simple: string
  situation_note: string
  cautions: Caution[]
  doc_kind: string
  basic_info: InfoItem[]
  confidence: 'high' | 'medium' | 'low'
  disclaimer: string
  page_count: number
  law_sources: { path: string; provision_id: string }[]
  needs_expert: boolean
  next_actions: NextAction[]
  doc_type_label: string
  open_questions: OpenQuestion[]
  document_claims: InfoItem[]
  not_immigration: boolean
}

export interface ChecklistItem {
  index: number
  done: boolean
}

export interface Analysis {
  id: string
  created_at: string
  updated_at: string
  lang: Lang
  filename: string
  file_size: number
  page_count: number | null
  masked_count: number
  status: AnalysisStatus
  stage: string | null
  error: string | null
  title: string | null
  doc_type_label: string | null
  intake: Intake | null
  facts: Fact[]
  answers: AnswerIn[] | null
  result: AnalysisResult | null
  checklist: ChecklistItem[] | null
}

export interface AnalysisListItem {
  id: string
  created_at: string
  filename: string
  status: AnalysisStatus
  title: string | null
  doc_type_label: string | null
  counts: { must_check: number; caution: number; general: number } | null
}

export interface SampleDoc {
  id: string
  title: { vi: string; ko: string }
  filename: string
}
