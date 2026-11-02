// 서버 연결 전 임시 응답. 서버가 병합되면 이 파일을 지운다.
// 제한값의 기준은 서버 설정값이다(first-feature.md).
import type { CaseInput, CaseSummary, CreateCaseResult, FieldError } from '../types'

const MAX_SITUATION_LENGTH = 1000
const MAX_FILES = 5
const MAX_FILE_BYTES = 10_485_760
const PDF_SIGNATURE = '%PDF-'

const cases: CaseSummary[] = []

const delay = () => new Promise((resolve) => setTimeout(resolve, 300))

async function isPdf(file: File) {
  if (!file.name.toLowerCase().endsWith('.pdf')) return false
  const head = await file.slice(0, PDF_SIGNATURE.length).text()
  return head === PDF_SIGNATURE
}

async function validate(input: CaseInput) {
  const errors: FieldError[] = []

  if (input.support_type !== 'F-6-1') {
    errors.push({ field: 'support_type', reason: 'F-6-1만 선택할 수 있습니다.' })
  }

  if (input.situation.trim() === '') {
    errors.push({ field: 'situation', reason: '상황 설명을 입력해 주세요.' })
  } else if (input.situation.length > MAX_SITUATION_LENGTH) {
    errors.push({ field: 'situation', reason: '상황 설명은 1,000자 이하로 입력해 주세요.' })
  }

  if (input.files.length === 0) {
    errors.push({ field: 'files', reason: 'PDF 파일을 1개 이상 올려 주세요.' })
  } else if (input.files.length > MAX_FILES) {
    errors.push({ field: 'files', reason: 'PDF 파일은 5개까지 올릴 수 있습니다.' })
  }

  for (const file of input.files) {
    if (!(await isPdf(file))) {
      errors.push({ field: 'files', reason: `${file.name}: PDF 파일이 아닙니다.` })
    } else if (file.size > MAX_FILE_BYTES) {
      errors.push({ field: 'files', reason: `${file.name}: 10MB를 넘습니다.` })
    }
  }

  return errors
}

export async function mockListCases(): Promise<CaseSummary[]> {
  await delay()
  return [...cases]
}

export async function mockCreateCase(input: CaseInput): Promise<CreateCaseResult> {
  await delay()
  const errors = await validate(input)
  if (errors.length > 0) return { ok: false, errors }

  const created: CaseSummary = {
    id: cases.length + 1,
    support_type: input.support_type,
    status: '준비중',
    created_at: new Date().toISOString(),
  }
  cases.push(created)
  return { ok: true, case: created }
}
