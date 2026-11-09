import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { createCase } from '../api/cases'
import type { FieldError, UserAccount } from '../types'

type Props = {
  account: UserAccount
  onCreated: () => void
  onCancel: () => void
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

export function CaseForm({ account, onCreated, onCancel }: Props) {
  const [supportType, setSupportType] = useState('F-6-1')
  const [situation, setSituation] = useState('')
  const [displayLanguage, setDisplayLanguage] = useState('')
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
      const result = await createCase({ support_type: supportType, situation, display_language: displayLanguage, files }, account)
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
  const languageErrors = errorsFor('display_language')
  const otherErrors = errors.filter(
    (error) => !['support_type', 'situation', 'display_language', 'files'].includes(error.field),
  )

  return (
    <form className="case-form" onSubmit={handleSubmit} noValidate>
      <h2>새 준비 건 만들기</h2>
      <FieldErrors id="form-errors" errors={otherErrors} />

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
          disabled={submitting}
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
          disabled={submitting}
          value={situation}
          onChange={(event) => setSituation(event.target.value)}
          aria-invalid={situationErrors.length > 0}
          aria-describedby={situationErrors.length > 0 ? 'situation-count situation-errors' : 'situation-count'}
        />
        <p id="situation-count">{Array.from(situation).length.toLocaleString()} / 1,000자 (공백·줄바꿈 포함)</p>
        <FieldErrors id="situation-errors" errors={situationErrors} />
      </div>

      <div className="field">
        <label htmlFor="display-language">표시 언어</label>
        <select
          id="display-language"
          value={displayLanguage}
          disabled={submitting}
          onChange={(event) => setDisplayLanguage(event.target.value)}
          aria-invalid={languageErrors.length > 0}
          aria-describedby={languageErrors.length > 0 ? 'display-language-errors' : undefined}
        >
          <option value="">선택하세요</option>
          <option value="vi">베트남어 (Tiếng Việt)</option>
        </select>
        <FieldErrors id="display-language-errors" errors={languageErrors} />
      </div>

      <div className="field">
        <label htmlFor="files">모의 PDF 서류</label>
        <input
          id="files"
          type="file"
          accept=".pdf,application/pdf"
          multiple
          disabled={submitting}
          onChange={handleFiles}
          aria-invalid={fileErrors.length > 0}
          aria-describedby={fileErrors.length > 0 ? 'files-errors' : undefined}
        />
        <FieldErrors id="files-errors" errors={fileErrors} />
      </div>

      <button type="submit" disabled={submitting}>
        {submitting ? '제출하는 중' : '제출'}
      </button>
      <button className="cancel-button" type="button" disabled={submitting} onClick={onCancel}>취소</button>
    </form>
  )
}
