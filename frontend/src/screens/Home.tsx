import { useCallback, useEffect, useState } from 'react'
import {
  ArrowUp,
  BookOpenCheck,
  ChevronRight,
  CircleAlert,
  FileClock,
  FileCheck2,
  FilePlus2,
  FileText,
  History,
  ListChecks,
  MessageSquareText,
  Upload,
} from 'lucide-react'
import { useApp } from '../AppContext'
import { getHealth } from '../api/client'
import type { Health } from '../api/client'
import { getAnalysis, listMyAnalyses, setChecklistItem } from '../api/documents'
import type { AnalysisListItem } from '../api/types'
import { Loading } from '../components/States'
import { loadRecentQuestions } from '../recentQuestions'
import type { RecentQuestion } from '../recentQuestions'

interface Todo {
  analysisId: string
  docTitle: string
  index: number
  text: string
  due: string | null
}

const ACTIVE = new Set(['uploaded', 'questions', 'analyzing', 'failed'])
const SUGGESTED = ['chat.suggested.1', 'chat.suggested.2', 'chat.suggested.3']

export default function Home() {
  const { t, lang, navigate } = useApp()
  const [items, setItems] = useState<AnalysisListItem[] | null>(null)
  const [todos, setTodos] = useState<Todo[] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [recentQs] = useState<RecentQuestion[]>(loadRecentQuestions)
  const [question, setQuestion] = useState('')

  const loadTodos = useCallback(async (list: AnalysisListItem[]) => {
    // 결과가 나온 최근 서류 3건의 남은 체크리스트를 모은다
    const targets = list.filter((a) => a.status === 'review').slice(0, 3)
    const details = await Promise.all(targets.map((a) => getAnalysis(a.id).catch(() => null)))
    const out: Todo[] = []
    for (const a of details) {
      if (!a?.result) continue
      a.result.next_actions.forEach((action, index) => {
        const done = a.checklist?.find((c) => c.index === index)?.done ?? false
        if (!done)
          out.push({ analysisId: a.id, docTitle: a.result!.title ?? a.filename, index, text: action.text, due: action.due })
      })
    }
    setTodos(out)
  }, [])

  useEffect(() => {
    let active = true
    listMyAnalyses()
      .then((list) => {
        if (!active) return
        setItems(list)
        void loadTodos(list)
      })
      .catch(() => {
        if (active) {
          setItems([])
          setTodos([])
        }
      })
    getHealth()
      .then((h) => active && setHealth(h))
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [loadTodos])

  async function complete(todo: Todo) {
    setTodos((prev) => prev?.filter((x) => !(x.analysisId === todo.analysisId && x.index === todo.index)) ?? null)
    try {
      await setChecklistItem(todo.analysisId, todo.index, true)
    } catch {
      if (items) void loadTodos(items)
    }
  }

  function ask(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (q) navigate({ name: 'chat', q })
  }

  const fmtDate = (iso: string) =>
    new Intl.DateTimeFormat(lang === 'vi' ? 'vi-VN' : 'ko-KR', { month: '2-digit', day: '2-digit' }).format(new Date(iso))

  const total = items?.length ?? 0
  const inProgress = items?.filter((a) => ACTIVE.has(a.status)).length ?? 0
  const review = items?.filter((a) => a.status === 'review').length ?? 0
  const done = items?.filter((a) => a.status === 'done').length ?? 0
  const mustCheck = items?.reduce((sum, a) => sum + (a.status === 'review' ? (a.counts?.must_check ?? 0) : 0), 0) ?? 0

  return (
    <div className="dash">
      {/* 바로 질문 */}
      <section className="panel panel--ask span-8">
        <form className="ask-box" onSubmit={ask}>
          <MessageSquareText size={20} aria-hidden />
          <input
            value={question}
            maxLength={1000}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={t('dash.ask.placeholder')}
            aria-label={t('dash.ask.placeholder')}
          />
          <button className="btn ask-box__send" type="submit" disabled={!question.trim()} aria-label={t('chat.send')}>
            <ArrowUp size={18} aria-hidden />
          </button>
        </form>
        <div className="chip-row">
          {SUGGESTED.map((k) => (
            <button key={k} className="chip" onClick={() => navigate({ name: 'chat', q: t(k) })}>
              {t(k)}
            </button>
          ))}
        </div>
      </section>

      {/* 새 서류 분석 */}
      <section className="panel panel--cta span-4">
        <button className="cta-main" onClick={() => navigate({ name: 'newDocument' })}>
          <span className="panel--cta__icon">
            <FilePlus2 size={22} aria-hidden />
          </span>
          <span className="panel--cta__text">
            <strong>{t('sidebar.newAnalysis')}</strong>
            <small>{t('dash.cta.desc')}</small>
          </span>
          <ChevronRight size={20} aria-hidden />
        </button>
        <p className="cta-meta">
          <Upload size={13} aria-hidden /> {t('dash.cta.formats')}
        </p>
      </section>

      {/* 요약 숫자 */}
      <div className="kpi span-3">
        <span className="kpi__icon">
          <FileText size={18} aria-hidden />
        </span>
        <p className="kpi__label">{t('dash.kpi.total')}</p>
        <p className="kpi__value">{items ? total : '—'}</p>
      </div>
      <div className="kpi span-3">
        <span className="kpi__icon kpi__icon--info">
          <FileClock size={18} aria-hidden />
        </span>
        <p className="kpi__label">{t('dash.kpi.inProgress')}</p>
        <p className="kpi__value">{items ? inProgress + review : '—'}</p>
      </div>
      <div className="kpi span-3">
        <span className="kpi__icon kpi__icon--danger">
          <CircleAlert size={18} aria-hidden />
        </span>
        <p className="kpi__label">{t('dash.kpi.mustCheck')}</p>
        <p className="kpi__value">{items ? mustCheck : '—'}</p>
      </div>
      <div className="kpi span-3">
        <span className="kpi__icon kpi__icon--success">
          <FileCheck2 size={18} aria-hidden />
        </span>
        <p className="kpi__label">{t('dash.kpi.done')}</p>
        <p className="kpi__value">{items ? done : '—'}</p>
      </div>

      {/* 최근 분석 서류 */}
      <section className="panel span-8">
        <header className="panel__head">
          <h2>
            <FileText size={17} aria-hidden /> {t('home.recent.title')}
          </h2>
          <button className="panel__link" onClick={() => navigate({ name: 'myDocuments' })}>
            {t('home.recent.viewAll')} <ChevronRight size={14} aria-hidden />
          </button>
        </header>
        {items === null && <Loading />}
        {items !== null && items.length === 0 && (
          <div className="panel__empty">
            <p>{t('home.recent.empty')}</p>
            <button className="btn" onClick={() => navigate({ name: 'newDocument' })}>
              <FilePlus2 size={15} aria-hidden /> {t('sidebar.newAnalysis')}
            </button>
          </div>
        )}
        {items !== null && items.length > 0 && (
          <ul className="list">
            {items.slice(0, 6).map((a) => (
              <li key={a.id}>
                <button className="list__row" onClick={() => navigate({ name: 'document', id: a.id })}>
                  <span className="list__icon">
                    <FileText size={16} aria-hidden />
                  </span>
                  <span className="list__main">
                    <strong>{a.title ?? a.filename}</strong>
                    <small>
                      {a.doc_type_label ?? a.filename} · {fmtDate(a.created_at)}
                    </small>
                  </span>
                  {a.counts && (
                    <span className="mini-counts" aria-label={t('result.clauses.title')}>
                      <span className="must_check">{a.counts.must_check}</span>
                      <span className="caution">{a.counts.caution}</span>
                      <span className="general">{a.counts.general}</span>
                    </span>
                  )}
                  <span className={`badge badge--status s-${a.status}`}>{t(`myDocuments.status.${a.status}`)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 최근 질문 */}
      <section className="panel span-4">
        <header className="panel__head">
          <h2>
            <History size={17} aria-hidden /> {t('dash.recentQuestions')}
          </h2>
          <button className="panel__link" onClick={() => navigate({ name: 'chat' })}>
            {t('nav.chat')} <ChevronRight size={14} aria-hidden />
          </button>
        </header>
        {recentQs.length === 0 && (
          <div className="panel__empty">
            <p>{t('dash.recentQuestions.empty')}</p>
          </div>
        )}
        {recentQs.length > 0 && (
          <ul className="list">
            {recentQs.slice(0, 6).map((q) => (
              <li key={q.at}>
                <button
                  className="list__row"
                  onClick={() => navigate({ name: 'chat', q: q.text, analysisId: q.analysisId })}
                  title={t('dash.recentQuestions.again')}
                >
                  <span className="list__icon">
                    <MessageSquareText size={16} aria-hidden />
                  </span>
                  <span className="list__main">
                    <strong className="clamp-1">{q.text}</strong>
                    <small>{fmtDate(q.at)}</small>
                  </span>
                  <ChevronRight size={16} className="list__chev" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 남은 할 일 */}
      <section className="panel span-8">
        <header className="panel__head">
          <h2>
            <ListChecks size={17} aria-hidden /> {t('dash.todo')}
            {todos && todos.length > 0 && <span className="panel__count">{todos.length}</span>}
          </h2>
        </header>
        {todos === null && <Loading />}
        {todos !== null && todos.length === 0 && (
          <div className="panel__empty">
            <p>{t('dash.todo.empty')}</p>
          </div>
        )}
        {todos !== null && todos.length > 0 && (
          <ul className="list">
            {todos.slice(0, 6).map((todo) => (
              <li key={`${todo.analysisId}-${todo.index}`} className="todo">
                <input
                  type="checkbox"
                  onChange={() => void complete(todo)}
                  aria-label={todo.text}
                />
                <button className="list__main todo__body" onClick={() => navigate({ name: 'document', id: todo.analysisId })}>
                  <strong>{todo.text}</strong>
                  <small>
                    {todo.docTitle}
                    {todo.due && <span className="todo__due"> · {todo.due}</span>}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 법령 데이터 상태 */}
      <section className="panel span-4">
        <header className="panel__head">
          <h2>
            <BookOpenCheck size={17} aria-hidden /> {t('dash.laws')}
          </h2>
        </header>
        <dl className="facts">
          <div>
            <dt>{t('dash.laws.docs')}</dt>
            <dd>{health ? health.documents : '—'}</dd>
          </div>
          <div>
            <dt>{t('dash.laws.provisions')}</dt>
            <dd>{health ? health.provisions.toLocaleString() : '—'}</dd>
          </div>
          <div>
            <dt>{t('dash.laws.mode')}</dt>
            <dd>
              {health ? (
                <span className={`badge ${health.llm_fake ? 'badge--caution' : 'badge--general'}`}>
                  {health.llm_fake ? t('dash.laws.fake') : t('dash.laws.live')}
                </span>
              ) : (
                '—'
              )}
            </dd>
          </div>
        </dl>
        <p className="panel__note">{t('dash.laws.note')}</p>
      </section>
    </div>
  )
}
