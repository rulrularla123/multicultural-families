// 화면 전환(예: 근거 조문 보기 → 뒤로)으로 Chat 화면이 다시 마운트돼도 대화가 사라지지 않도록
// 메시지 상태를 AppProvider와 함께 계속 떠 있는 이 store에 둔다. 서류별 후속 질문은 analysisId로 구분한다.
import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { AnswerPayload } from './api/types'

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  answer?: AnswerPayload
  pending?: boolean
  error?: string
}

function uid() {
  return Math.random().toString(36).slice(2)
}

interface ChatStoreValue {
  getMessages: (key: string) => DisplayMessage[]
  setMessages: (key: string, updater: (prev: DisplayMessage[]) => DisplayMessage[]) => void
  getSessionId: (key: string) => string
}

const ChatStoreCtx = createContext<ChatStoreValue | null>(null)

export function ChatStoreProvider({ children }: { children: ReactNode }) {
  const [threads, setThreads] = useState<Record<string, DisplayMessage[]>>({})
  const sessionIds = useRef<Record<string, string>>({})

  const getMessages = useCallback((key: string) => threads[key] ?? [], [threads])

  const setMessages = useCallback((key: string, updater: (prev: DisplayMessage[]) => DisplayMessage[]) => {
    setThreads((prev) => ({ ...prev, [key]: updater(prev[key] ?? []) }))
  }, [])

  const getSessionId = useCallback((key: string) => {
    if (!sessionIds.current[key]) sessionIds.current[key] = uid()
    return sessionIds.current[key]
  }, [])

  return (
    <ChatStoreCtx.Provider value={{ getMessages, setMessages, getSessionId }}>{children}</ChatStoreCtx.Provider>
  )
}

export function useChatThread(key: string) {
  const ctx = useContext(ChatStoreCtx)
  if (!ctx) throw new Error('useChatThread must be used within ChatStoreProvider')
  const messages = ctx.getMessages(key)
  const setMessages = useCallback(
    (updater: (prev: DisplayMessage[]) => DisplayMessage[]) => ctx.setMessages(key, updater),
    [ctx, key],
  )
  const sessionId = ctx.getSessionId(key)
  return { messages, setMessages, sessionId }
}
