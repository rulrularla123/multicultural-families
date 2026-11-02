// 화면은 이 파일만 부른다. 서버가 병합되면 함수 안쪽만 실제 요청으로 바꾼다.
import type { CaseInput, CaseSummary, CreateCaseResult } from '../types'
import { mockCreateCase, mockListCases } from './mockCases'

export function listCases(): Promise<CaseSummary[]> {
  return mockListCases()
}

export function createCase(input: CaseInput): Promise<CreateCaseResult> {
  return mockCreateCase(input)
}
