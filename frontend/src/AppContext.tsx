import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { Lang } from './api/types'
import { t as translate } from './i18n'
import type { View } from './nav'
import { sameView } from './nav'

function loadLang(): Lang {
  try {
    const saved = localStorage.getItem('ui_lang')
    if (saved === 'vi' || saved === 'ko') return saved
  } catch {
    /* ignore */
  }
  return 'vi'
}

interface AppContextValue {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string) => string
  view: View
  navigate: (v: View) => void
  back: () => void
  canGoBack: boolean
}

const AppCtx = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(loadLang)
  const [stack, setStack] = useState<View[]>([{ name: 'home' }])

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try {
      localStorage.setItem('ui_lang', l)
    } catch {
      /* ignore */
    }
  }, [])

  const navigate = useCallback((v: View) => {
    setStack((prev) => {
      if (prev.length > 0 && sameView(prev[prev.length - 1], v)) return prev
      if (v.name === 'home' || v.name === 'myDocuments' || v.name === 'chat') return [v]
      return [...prev, v]
    })
  }, [])

  const back = useCallback(() => {
    setStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev))
  }, [])

  const value = useMemo<AppContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => translate(lang, key),
      view: stack[stack.length - 1],
      navigate,
      back,
      canGoBack: stack.length > 1,
    }),
    [lang, setLang, stack, navigate, back],
  )

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppCtx)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
