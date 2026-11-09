import { useApp } from '../AppContext'
import { APP_NAME, APP_NAME_VI } from '../i18n'

export default function Header() {
  const { lang, setLang, t, navigate } = useApp()

  return (
    <header className="app-header">
      <button className="app-header__brand" onClick={() => navigate({ name: 'home' })}>
        <span className="app-header__title">{lang === 'vi' ? APP_NAME_VI : APP_NAME}</span>
      </button>
      <nav className="app-header__nav">
        <button className="app-header__link" onClick={() => navigate({ name: 'chat' })}>
          {t('nav.chat')}
        </button>
        <button className="app-header__link" onClick={() => navigate({ name: 'myDocuments' })}>
          {t('nav.myDocuments')}
        </button>
        <button
          className="app-header__lang"
          onClick={() => setLang(lang === 'vi' ? 'ko' : 'vi')}
          aria-label="switch language"
        >
          {t('lang.toggle')}
        </button>
      </nav>
    </header>
  )
}
