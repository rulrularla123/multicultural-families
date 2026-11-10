import type { ReactNode } from 'react'

export default function PageHeader({
  eyebrow,
  title,
  desc,
  actions,
}: {
  eyebrow?: string
  title: ReactNode
  desc?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="page-header__title">{title}</h1>
        {desc && <p className="page-desc">{desc}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  )
}
