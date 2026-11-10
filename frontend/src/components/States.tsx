import type { ReactNode } from 'react'
import { useApp } from '../AppContext'

export function Loading({ label }: { label?: string }) {
  const { t } = useApp()
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      {label ?? t('common.loading')}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useApp()
  return (
    <div className="state state--error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button className="btn btn--secondary" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p>{message}</p>
      {action}
    </div>
  )
}

export function DevFakeBanner({ text }: { text: string }) {
  return <div className="dev-fake-banner">{text}</div>
}
