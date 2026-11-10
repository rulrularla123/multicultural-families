import { useState } from 'react'
import './App.css'
import { AppProvider, useApp } from './AppContext'
import { ChatStoreProvider } from './chatStore'
import Sidebar from './components/Sidebar'
import LegalNotice from './components/LegalNotice'
import Home from './screens/Home'
import Chat from './screens/Chat'
import Provision from './screens/Provision'
import Upload from './screens/Upload'
import DocumentFlow from './screens/DocumentFlow'
import MyDocuments from './screens/MyDocuments'

function Screen() {
  const { view } = useApp()
  switch (view.name) {
    case 'home':
      return <Home />
    case 'chat':
      return <Chat key={view.q ?? view.analysisId ?? '_'} analysisId={view.analysisId} initialQuestion={view.q} />
    case 'provision':
      return <Provision id={view.id} />
    case 'newDocument':
      return <Upload />
    case 'document':
      return <DocumentFlow id={view.id} />
    case 'myDocuments':
      return <MyDocuments />
    default:
      return null
  }
}

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem('sidebar_collapsed') === '1'
  } catch {
    return false
  }
}

function Shell() {
  const { view } = useApp()
  const isChat = view.name === 'chat'
  const [collapsed, setCollapsed] = useState(loadCollapsed)

  function toggle() {
    setCollapsed((c) => {
      try {
        localStorage.setItem('sidebar_collapsed', c ? '0' : '1')
      } catch {
        /* ignore */
      }
      return !c
    })
  }

  return (
    <div className={`app-shell${collapsed ? ' collapsed' : ''}`}>
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main className={`app-main${isChat ? ' app-main--chat' : ''}`}>
        <div className="app-main__inner">
          <div className="app-screen"><Screen /></div>
          <LegalNotice />
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <ChatStoreProvider>
        <Shell />
      </ChatStoreProvider>
    </AppProvider>
  )
}
