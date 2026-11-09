import './App.css'
import { AppProvider, useApp } from './AppContext'
import { ChatStoreProvider } from './chatStore'
import Header from './components/Header'
import Footer from './components/Footer'
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
      return <Chat analysisId={view.analysisId} />
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

function Shell() {
  const { view } = useApp()
  const isChat = view.name === 'chat'
  return (
    <div className="app-shell">
      <Header />
      <main className={`app-main${isChat ? ' app-main--chat' : ''}`}>
        <Screen />
      </main>
      {!isChat && <Footer />}
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
