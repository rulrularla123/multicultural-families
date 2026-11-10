// 최근 질문을 브라우저에만 저장한다 (홈 대시보드 바로가기용). 서버에는 보내지 않는다.
export interface RecentQuestion {
  text: string
  at: string
  analysisId?: string
}

const KEY = 'recent_questions'
const MAX = 8

export function loadRecentQuestions(): RecentQuestion[] {
  try {
    const raw = localStorage.getItem(KEY)
    const list = raw ? (JSON.parse(raw) as RecentQuestion[]) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

export function addRecentQuestion(text: string, analysisId?: string) {
  try {
    const rest = loadRecentQuestions().filter((q) => q.text !== text)
    const next = [{ text, at: new Date().toISOString(), analysisId }, ...rest].slice(0, MAX)
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
}

export function clearRecentQuestions() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
