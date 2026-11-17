import { useRef, useState } from 'react'
import { useApp } from '../AppContext'
import Steps from '../components/Steps'
import { ApiError } from '../api/client'
import { uploadDocument } from '../api/documents'
import { ErrorBox } from '../components/States'

const MAX_SIZE = 10 * 1024 * 1024

export default function Upload() {
  const { lang, t, navigate } = useApp()
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function errorMessage(e: unknown): string {
    if (e instanceof ApiError) {
      if (e.status === 413) return t('upload.error.size')
      if (e.status === 415) return t('upload.error.type')
      if (e.status === 422) return t('upload.error.extract')
    }
    return t('upload.error.generic')
  }

  async function handleFile(file: File) {
    setError(null)
    if (file.size > MAX_SIZE) {
      setError(t('upload.error.size'))
      return
    }
    setBusy(true)
    try {
      const analysis = await uploadDocument(file, lang)
      navigate({ name: 'document', id: analysis.id })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <Steps current={1} />
      <h1 className="page-title">{t('upload.title')}</h1>
      <p className="upload-notice">{t('upload.privacyNotice')}</p>

      {error && <ErrorBox message={error} />}

      <div
        className={`upload-dropzone${dragging ? ' dragging' : ''}`}
        onClick={() => !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const file = e.dataTransfer.files?.[0]
          if (file) void handleFile(file)
        }}
        role="button"
        tabIndex={0}
      >
        <p>{busy ? t('upload.uploading') : t('upload.dragHint')}</p>
        <small className="upload-dropzone__meta">{t('dash.cta.formats')}</small>
        <button
          className="btn"
          type="button"
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation()
            inputRef.current?.click()
          }}
        >
          {t('upload.choose')}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
            e.target.value = ''
          }}
        />
      </div>

    </div>
  )
}
