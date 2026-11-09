import { useState } from 'react'
import type { DemoAccount } from './types'
import { MyCasesScreen } from './screens/MyCasesScreen'
import { OfficerWorkspace } from './screens/OfficerWorkspace'

// 회원가입·로그인은 MVP 제외. 모의 계정은 X-Demo-Account 헤더로 보낸다 (API.md 공통 규칙).
function App() {
  const [account, setAccount] = useState<DemoAccount>('demo-user-1')

  return (
    <>
      <div className="account-bar">
        <label htmlFor="demo-account">모의 계정</label>
        <select
          id="demo-account"
          value={account}
          onChange={(event) => setAccount(event.target.value as DemoAccount)}
        >
          <option value="demo-user-1">모의 이용자 1</option>
          <option value="demo-user-2">모의 이용자 2</option>
          <option value="demo-officer">모의 지원 담당자</option>
        </select>
      </div>
      {account === 'demo-officer'
        ? <OfficerWorkspace />
        : <MyCasesScreen key={account} account={account} />}
    </>
  )
}

export default App
