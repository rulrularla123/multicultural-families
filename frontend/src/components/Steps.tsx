import { Check } from 'lucide-react'
import { useApp } from '../AppContext'

const KEYS = ['steps.upload', 'steps.questions', 'steps.analyzing', 'steps.result']

/** 서류 분석 4단계 표시. current는 1부터 */
export default function Steps({ current, done = false }: { current: number; done?: boolean }) {
  const { t } = useApp()
  return (
    <div>
      <p className="eyebrow">
        STEP {String(current).padStart(2, '0')} / 04
      </p>
      <ol className="steps" aria-label={t('nav.documents')}>
        {KEYS.map((key, i) => {
          const n = i + 1
          const state = n < current || (done && n === current) ? 'done' : n === current ? 'active' : ''
          return (
            <li key={key} className={`step ${state}`} aria-current={state === 'active' ? 'step' : undefined}>
              <span className="step__bar" />
              <span className="step__label">
                <span className="step__num">{state === 'done' ? <Check size={11} strokeWidth={2} aria-hidden /> : n}</span>
                {t(key)}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
