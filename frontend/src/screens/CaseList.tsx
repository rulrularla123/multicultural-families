import type { CaseSummary } from '../types'

const dateFormat = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  dateStyle: 'medium',
  timeStyle: 'short',
})

type Props = {
  cases: CaseSummary[]
}

export function CaseList({ cases }: Props) {
  return (
    <table className="case-list">
      <thead>
        <tr>
          <th scope="col">지원 유형</th>
          <th scope="col">생성 일시</th>
          <th scope="col">현재 상태</th>
        </tr>
      </thead>
      <tbody>
        {cases.map((item) => (
          <tr key={item.id}>
            <td>{item.support_type}</td>
            <td>{dateFormat.format(new Date(item.created_at))}</td>
            <td>{item.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
