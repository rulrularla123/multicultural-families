import { useEffect, useState } from 'react'
import { ChevronRight, FilePlus2, FolderOpen, House, MessageSquareText, PanelLeft, Phone } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useApp } from '../AppContext'
import { listMyAnalyses } from '../api/documents'
import { HOTLINE } from '../i18n'
import type { View } from '../nav'

const NAV: { view: View; key: string; icon: LucideIcon; match: View['name'][]; count?: boolean }[] = [
  { view: { name: 'home' }, key: 'nav.home', icon: House, match: ['home'] },
  { view: { name: 'chat' }, key: 'nav.chat', icon: MessageSquareText, match: ['chat', 'provision'] },
  { view: { name: 'myDocuments' }, key: 'nav.myDocuments', icon: FolderOpen, match: ['myDocuments', 'document'], count: true },
]

export default function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { lang, setLang, t, view, navigate } = useApp()
  const [count, setCount] = useState<number | null>(null)

  // 화면이 바뀔 때마다 내 분석 개수를 다시 센다 (업로드·삭제 반영)
  useEffect(() => {
    let active = true
    listMyAnalyses()
      .then((list) => active && setCount(list.length))
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [view])

  return (
    <aside className="sidebar">
      <div className="sidebar__top">
        <button className="sidebar__brand" onClick={() => navigate({ name: 'home' })} title={t('brand.title')}>
          <span className="brand-badge">{t('brand.badge')}</span>
          <span className="sidebar__brand-text">
            <strong>{t('brand.title')}</strong>
            <small>{t('brand.subtitle')}</small>
          </span>
        </button>
        <button
          className="icon-btn sidebar__toggle"
          onClick={onToggle}
          aria-label={t(collapsed ? 'sidebar.expand' : 'sidebar.collapse')}
          title={t(collapsed ? 'sidebar.expand' : 'sidebar.collapse')}
        >
          <PanelLeft size={22} strokeWidth={1.8} aria-hidden />
        </button>
      </div>

      <p className="sidebar__label">{t('sidebar.menu')}</p>
      <nav className="sidebar__nav">
        {NAV.map((item) => {
          const active = item.match.includes(view.name)
          return (
            <button
              key={item.key}
              className={`sidebar__item${active ? ' active' : ''}`}
              onClick={() => navigate(item.view)}
              aria-current={active ? 'page' : undefined}
              title={t(item.key)}
            >
              <item.icon size={22} strokeWidth={1.8} aria-hidden />
              <span>{t(item.key)}</span>
              {item.count && count !== null && !collapsed && <span className="sidebar__count">{count}</span>}
            </button>
          )
        })}
        <button
          className={`sidebar__item${view.name === 'newDocument' ? ' active' : ''}`}
          onClick={() => navigate({ name: 'newDocument' })}
          title={t('sidebar.newAnalysis')}
        >
          <FilePlus2 size={22} strokeWidth={1.8} aria-hidden />
          <span>{t('sidebar.newAnalysis')}</span>
        </button>
      </nav>

      <div className="sidebar__lang">
        <p className="sidebar__label">{t('sidebar.language')}</p>
        <div className="segmented" role="group" aria-label={t('sidebar.language')}>
          {(['vi', 'ko'] as const).map((l) => (
            <button key={l} className={lang === l ? 'active' : ''} onClick={() => setLang(l)}>
              {l === 'vi' ? 'Tiếng Việt' : '한국어'}
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar__foot">
        <div className="sidebar__divider" />
        <a className="profile-row" href={`tel:${HOTLINE}`} title={t('footer.hotlineLabel')}>
          <span className="avatar">
            <Phone size={18} strokeWidth={2} aria-hidden />
          </span>
          <span className="profile-row__text">
            <strong>☎ {HOTLINE}</strong>
            <small>{t('footer.hotlineLabel')}</small>
          </span>
          <ChevronRight size={20} strokeWidth={2} aria-hidden />
        </a>
        <p className="sidebar__disclaimer">{t('footer.disclaimer')}</p>
      </div>
    </aside>
  )
}
