import { useEffect, useRef, useState } from 'react'
import { useApp } from '../AppContext'
import { useChatThread } from '../chatStore'
import type { DisplayMessage } from '../chatStore'
import { streamChat } from '../api/client'
import { addRecentQuestion } from '../recentQuestions'
import type { ChatMessage as ApiChatMessage, StageEvent } from '../api/types'
import CitationCard from '../components/CitationCard'
import { DevFakeBanner } from '../components/States'

const SUGGESTED_KEYS = ['chat.suggested.1', 'chat.suggested.2', 'chat.suggested.3', 'chat.suggested.4']

function uid() {
  return Math.random().toString(36).slice(2)
}

export default function Chat({ analysisId, initialQuestion }: { analysisId?: string; initialQuestion?: string }) {
  const { lang, t } = useApp()
  const threadKey = analysisId ?? '_general'
  const { messages, setMessages, sessionId } = useChatThread(threadKey)
  const [input, setInput] = useState('')
  const [stage, setStage] = useState<StageEvent | null>(null)
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, stage])

  useEffect(() => () => abortRef.current?.abort(), [])

  // 사이드바 검색창에서 넘어온 질문은 한 번만 보낸다
  const sentInitialRef = useRef(false)
  useEffect(() => {
    if (!initialQuestion || sentInitialRef.current) return
    sentInitialRef.current = true
    void send(initialQuestion)
  }, [initialQuestion]) // eslint-disable-line react-hooks/exhaustive-deps

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setInput('')
    addRecentQuestion(trimmed, analysisId)
    const userMsg: DisplayMessage = { id: uid(), role: 'user', content: trimmed }
    const assistantId = uid()
    const history: ApiChatMessage[] = messages
      .filter((m) => !m.error)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: 'assistant', content: '', pending: true }])
    setBusy(true)
    setStage(null)

    const controller = new AbortController()
    abortRef.current = controller

    await streamChat(
      {
        message: trimmed,
        lang,
        history,
        session_id: sessionId,
        analysis_id: analysisId ?? null,
      },
      {
        onStage: (ev) => setStage(ev),
        onDelta: (chunk) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + chunk } : m)),
          )
        },
        onReset: () => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: '' } : m)))
        },
        onAnswer: (answer) => {
          setStage(null)
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: answer.answer, answer, pending: false } : m,
            ),
          )
        },
        onError: () => {
          setStage(null)
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, pending: false, error: t('chat.error') } : m)),
          )
        },
      },
      controller.signal,
    )
    setBusy(false)
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    void send(input)
  }

  return (
    <div className="chat-layout">
      {analysisId && <DevFakeBanner text={t('chat.fromDocument')} />}
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="state state--empty">
            <p>
              <strong>{t('chat.empty.title')}</strong>
            </p>
            <p>{t('chat.empty.desc')}</p>
            <div className="chat-suggested">
              {SUGGESTED_KEYS.map((k) => (
                <button key={k} onClick={() => void send(t(k))}>
                  {t(k)}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`chat-bubble chat-bubble--${m.role}`}>
            {m.content.includes('[DEV FAKE RESPONSE]') && <DevFakeBanner text={t('chat.devFake')} />}
            {m.content || (m.pending ? '…' : '')}

            {m.error && <p style={{ color: 'var(--danger)', marginTop: 6 }}>{m.error}</p>}

            {m.answer && (
              <>
                <div style={{ marginTop: 8 }}>
                  <span className={`badge badge--confidence-${m.answer.confidence}`}>
                    {t(`chat.confidence.${m.answer.confidence}`)}
                  </span>
                </div>

                {m.answer.needs_expert && (
                  <p style={{ color: 'var(--danger)', marginTop: 6, fontSize: 13 }}>{t('chat.needsExpert')}</p>
                )}

                {m.answer.citations.length > 0 && (
                  <div className="citation-list">
                    <strong style={{ fontSize: 13 }}>{t('chat.citations.title')}</strong>
                    {m.answer.citations.map((c) => (
                      <CitationCard key={c.index} citation={c} />
                    ))}
                  </div>
                )}

                {m.answer.follow_up_questions.length > 0 && (
                  <div className="chat-suggested">
                    {m.answer.follow_up_questions.map((q, i) => (
                      <button key={i} onClick={() => void send(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        ))}

        {stage && <div className="chat-stage">{t(`chat.stage.${stage.stage}`) || stage.label}</div>}
      </div>

      <form className="chat-input-row" onSubmit={onSubmit}>
        <textarea
          value={input}
          maxLength={1000}
          placeholder={t('chat.placeholder')}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send(input)
            }
          }}
          aria-label={t('chat.placeholder')}
        />
        <button className="btn" type="submit" disabled={busy || !input.trim()}>
          {busy ? t('chat.sending') : t('chat.send')}
        </button>
      </form>
    </div>
  )
}
