import { useApp } from '../AppContext'
import { HOTLINE } from '../i18n'

export default function Footer() {
  const { t } = useApp()
  return (
    <footer className="app-footer">
      <p className="app-footer__disclaimer">{t('footer.disclaimer')}</p>
      <a className="app-footer__hotline" href={`tel:${HOTLINE}`}>
        ☎ {HOTLINE} · {t('footer.hotlineLabel')}
      </a>
    </footer>
  )
}
