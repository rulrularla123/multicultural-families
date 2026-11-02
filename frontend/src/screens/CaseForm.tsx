import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { createCase } from '../api/cases'
import type { FieldError } from '../types'

type Props = {
  onCreated: () => void
}

function FieldErrors({ id, errors }: { id: string; errors: FieldError[] }) {
  if (errors.length === 0) return null
  return (
    <ul id={id} className="field-errors">
      {errors.map((error) => (
        <li key={error.reason}>{error.reason}</li>
      ))}
    </ul>
  )
}

export function CaseForm({ onCreated }: Props) {
  const [supportType, setSupportType] = useState('F-6-1')
  const [situation, setSituation] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [errors, setErrors] = useState<FieldError[]>([])
  const [submitFailed, setSubmitFailed] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const errorsFor = (field: FieldError['field']) =>
    errors.filter((error) => error.field === field)

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(event.target.files ?? []))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setSubmitFailed(false)
    setErrors([])
    try {
      const result = await createCase({ support_type: supportType, situation, files })
      if (result.ok) {
        onCreated()
      } else {
        setErrors(result.errors)
      }
    } catch {
      setSubmitFailed(true)
    } finally {
      setSubmitting(false)
    }
  }

  const situationErrors = errorsFor('situation')
  const fileErrors = errorsFor('files')
  const supportTypeErrors = errorsFor('support_type')

  return (
    <form className="case-form" onSubmit={handleSubmit} noValidate>
      <h2>새 준비 건 만들기</h2>

      {submitFailed && (
        <p className="error" role="alert">
          제출하지 못했습니다. 입력한 내용은 그대로 있으니 다시 시도해 주세요.
        </p>
      )}

      <div className="field">
        <label htmlFor="support-type">지원 유형</label>
        <select
          id="support-type"
          value={supportType}
          onChange={(event) => setSupportType(event.target.value)}
          aria-describedby={supportTypeErrors.length > 0 ? 'support-type-errors' : undefined}
        >
          <option value="F-6-1">F-6-1 체류기간 연장</option>
        </select>
        <FieldErrors id="support-type-errors" errors={supportTypeErrors} />
      </div>

      <div className="field">
        <label htmlFor="situation">상황 설명</label>
        <textarea
          id="situation"
          rows={6}
          value={situation}
          onChange={(event) => setSituation(event.target.value)}
          aria-invalid={situationErrors.length > 0}
          aria-describedby={situationErrors.length > 0 ? 'situation-errors' : undefined}
        />
        <FieldErrors id="situation-errors" errors={situationErrors} />
      </div>

      <div className="field">
        <label htmlFor="files">모의 PDF 서류</label>
        <input
          id="files"
          type="file"
          accept=".pdf,application/pdf"
          multiple
          onChange={handleFiles}
          aria-invalid={fileErrors.length > 0}
          aria-describedby={fileErrors.length > 0 ? 'files-errors' : undefined}
        />
        <FieldErrors id="files-errors" errors={fileErrors} />
      </div>

      <button type="submit" disabled={submitting}>
        {submitting ? '제출하는 중' : '제출'}
      </button>
    </form>
  )
}
