import { useApp } from '../AppContext'
import { HOTLINE } from '../i18n'

/** 사이드바 안내가 숨겨지는 모바일·접힌 화면에서도 법률 정보 안내를 유지한다. */
export default function LegalNotice() {
  const { t } = useApp()
  return (
    <footer className="legal-notice">
      <p>{t('footer.disclaimer')}</p>
      <a href={`tel:${HOTLINE}`}>☎ {HOTLINE}</a>
    </footer>
  )
}
