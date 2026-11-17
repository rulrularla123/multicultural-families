import { useApp } from '../AppContext'
import type { TranslationStatus } from '../api/types'

export default function LegalTranslation({ text, status }: { text?: string | null; status?: TranslationStatus }) {
  const { lang, t } = useApp()
  if (lang === 'ko') return null
  if (text && (status === 'translated' || status === 'development')) {
    return (
      <div>
        <p style={{ margin: '4px 0' }}>{text}</p>
        <small>{t(status === 'development' ? 'translation.development' : 'translation.label')}</small>
      </div>
    )
  }
  return <small>{t('translation.unavailable')}</small>
}
