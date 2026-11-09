# 코딩 스타일 (팀 합의)

> **저장 위치:** `docs/CODE-STYLE.md`

> **사용 방법**
> 1. 5명이 같은 규칙으로 쓰기 위한 **팀 규칙**만 적습니다. **테크리더가 씁니다.** 테스트 담당은 테스트 규칙을 한두 줄로 채팅에 전달하고(반영은 테크리더 한 사람), 팀이 결정합니다. 내 취향(응답 언어, 에디터 설정)은 `~/.claude/CLAUDE.md`나 `CLAUDE.local.md`에 둡니다.
> 2. **"깔끔하게"처럼 모호한 문장을 쓰지 않습니다.** 확인할 수 있는 규칙(포매터 설정, 이름 규칙)으로 씁니다. 지키는지 확인하는 **방법**을 오른쪽 칸에 적습니다.
> 3. 규칙은 **8개 이하**로 합니다. 지켜지지 않을 규칙은 없는 게 낫습니다.
> 4. 팀이 합의한 뒤 `CLAUDE.md`에서 `@docs/CODE-STYLE.md`로 가져옵니다 (`CLAUDE.md`는 짧게 둡니다). 2-2에서 `.claude/rules/`로 나눴다면 그 파일과 겹치지 않게 합니다.
> 5. Claude는 규칙끼리 모순되는지 점검하기만 합니다. 규칙의 내용은 팀이 정합니다.
> 6. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 정리 담당: 이주환 (2기 테크리더)
- 작성: 2026-11-02, 2026-11-03 수업 사전 준비
- 합의일: 팀 검토 후 기입. 아래는 검토할 초안이다.
- 근거: [STACK.md](STACK.md), [CLAUDE.md](../CLAUDE.md), 3-1 학생 안내문의 담당 구분

## 규칙

| # | 규칙 | 지키는지 확인하는 방법 |
| --- | --- | --- |
| 1 | Python 파일·함수·변수는 `snake_case`, 클래스는 `PascalCase`. TypeScript 함수·변수는 `camelCase`, React 컴포넌트 파일·함수는 `PascalCase`로 맞춘다 | PR의 추가·수정된 이름을 언어별로 확인한다 |
| 2 | 들여쓰기는 Python 4칸, TypeScript·TSX·CSS·JSON 2칸을 쓴다. 줄 끝 공백은 남기지 않는다. 포매터·린터와 설정 파일은 아직 없으며 도입은 공유 설정 작업으로 분리한다 | 들여쓰기는 PR diff에서 확인한다. 공백 오류는 루트에서 `git diff --check`로 확인한다. 자동 포맷·린트 검사를 했다고 보고하지 않는다 |
| 3 | 서버·화면·테스트는 아래 담당 폴더가 확정된 뒤 각자 자기 폴더만 수정한다. 첫 기능 범위 밖의 코드는 추가하지 않는다 | PR의 변경 경로를 담당 폴더 및 `first-feature.md` 1절과 대조한다. 경로·범위가 비어 있으면 구현을 시작하지 않는다 |
| 4 | 공통 코드·설정·의존성은 이주환, `API.md`·`first-feature.md`·`prd-review.md`·README 문서 지도는 권길현이 수정한다. `DATA-MODEL.md`는 김민건, `DESIGN.md`는 여철준이 수정한다. 다른 담당자에게는 PR 댓글이나 채팅으로 요청한다 | PR에서 파일별 담당을 확인한다. README 실행 방법은 이주환이 갱신하고 권길현과 맞춘다. `.gitignore`는 이번 작업에서 MCP가 파일을 만들 때만 수정한다 |
| 5 | 커밋은 `docs`·`feat`·`fix`·`test`·`logs` 중 하나에 `: 한국어 내용`을 붙인다. 한 커밋에는 한 의도의 변경만 넣고 `main`에 직접 커밋하지 않는다 | `git log --oneline`에서 형식을 확인하고 PR의 변경 파일이 한 작업에 해당하는지 확인한다 |
| 6 | 테스트 함수는 `test_`로 시작하고 확인하는 행동·기대 결과를 이름에 쓴다. 연결된 `US-xx`와 인수 조건 번호는 주석이나 docstring에 쓴다 | 테스트와 백로그·`first-feature.md` 2절을 대조한다. 정상·실패·경계 중 무엇을 검사하는지 읽어서 확인한다 |
| 7 | 테스트와 기대값을 현재 구현에 맞춰 바꾸지 않는다. 입력·기대 결과의 근거는 인수 조건과 `API.md`다. 병합 후 일부러 틀린 구현을 넣어 테스트가 실패하는지 확인하고 원복한다 | 테스트 변경 전후의 입력·기대값을 근거 문서와 비교한다. 테스트 담당이 틀린 구현·실패한 테스트·원복 후 결과를 `first-feature.md` 3절에 남긴다. 테스트 파일이 바뀌었다는 이유만으로 위반으로 보지 않는다 |
| 8 | 키·토큰·비밀번호·실제 개인정보를 코드·문서·로그·`.mcp.json`에 넣지 않는다. `.env` 및 비밀 값 파일은 읽거나 대화에 붙이지 않는다 | `git ls-files .env CLAUDE.local.md`의 빈 결과와 `.gitignore`를 확인한다. 하위 비밀 파일 추적 여부와 PR의 추가 내용도 확인한다. 파일 내용을 열어 비밀 값을 검사하지 않는다 |

## 담당 폴더

2026-11-09 최종 업무 배정을 반영했다. US-01 이후 작업은 이번 배정과 백로그의 해당 스토리를 범위로 삼는다. 아래 후속 파일명은 동시 작업이 겹치지 않도록 나눈 작업 경로이며, 아직 없는 파일은 해당 단계에서 만든다. 파일명·경로가 최신 main과 다르면 기존 구현을 확인하고 이 표를 먼저 맞춘다.

| 영역 | 폴더·파일 | 수정할 수 있는 사람 |
| --- | --- | --- |
| 공유 설정·서버 조립 | `backend/app/main.py`, `backend/app/dependencies.py`, 패키지 초기화 파일, 루트 `CLAUDE.md`, 공유 설정·의존성 | 이주환 |
| 생성·본인 목록·상세 (US-01, 기존 상세) | `backend/app/routers/case_detail.py` | 김민건 |
| 자동 점검 (US-02) | `backend/app/routers/checking.py` | 김민건 |
| 기준 등록·변경 (F-02) | `backend/app/routers/criteria.py` | 이주환 |
| 검토 대기 목록 (F-09) | `backend/app/routers/review_queue.py` | 여철준 |
| 검토 항목 수정·승인·결과 공개 (US-03) | `backend/app/routers/approval.py` | 김민건 |
| 반려 (US-04) | `backend/app/routers/rejection.py` | 김민건 |
| 준비 체크·확인 요청 (US-05) | `backend/app/routers/preparation_check.py` | 김태후 |
| 보완 요청·수정 시작 (US-06) | `backend/app/routers/supplementation.py` | 이주환 |
| 완료 (US-07) | `backend/app/routers/completion.py` | 김태후 |
| 취소 (US-08) | `backend/app/routers/cancellation.py` | 권길현 |
| 입력 수정·버전 증가·재점검 | `backend/app/routers/input_revision.py` | 권길현 |
| 식별정보 검사 | `backend/app/common/identity_patterns.py` | 권길현 |
| PDF 추출·LLM 클라이언트 | `backend/app/common/pdf_extraction.py`, `backend/app/common/llm_client.py` | 이주환 |
| 공유 모델·스키마·DB·기존 시드 | `backend/app/models.py`, `schemas.py`, `database.py`, `seed.py` | 김민건 |
| 공통 기준 시드 (F-02) | `backend/app/criteria_seed.py` | 이주환 |
| 공통 모듈 단위 점검 | `backend/common_tests/` (DB 없이 unittest 실행) | 이주환 |
| 기존 생성·첨부·상세·반려 테스트 | `backend/tests/test_creation.py`, `test_attachment.py`, `test_us01_schema.py`, `test_rejection.py` | 김민건 |
| 자동 점검 테스트 (US-02) | `backend/tests/test_checking.py` (정상·권한), `test_checking_failures.py` (합의한 실패 응답) | 김민건 (정상·권한), 김태후 (실패) |
| 기준·승인·검토 대기 목록 테스트 | `backend/tests/test_criteria.py`, `test_approval.py`, `test_review_queue.py` | 각각 이주환, 김민건, 여철준 |
| 준비 체크·완료 테스트 | `backend/tests/test_preparation_check.py`, `test_completion.py` | 김태후 (김민건 리뷰) |
| 보완 테스트 | `backend/tests/test_supplementation.py` | 이주환 |
| 취소·식별정보·입력 수정 테스트 | `backend/tests/test_cancellation.py`, `test_identity_patterns.py`, `test_input_revision.py` | 권길현 |
| 테스트 공통 fixture | `backend/tests/conftest.py` | 김민건 (스토리 담당자가 필요한 변경 전달) |
| 전체 흐름 인수 테스트 | `backend/tests/acceptance/` (후속 작업에서 생성) | 김태후 주도, 전원 실행 |
| 기존 생성·목록 화면 | `frontend/src/screens/CaseForm.tsx`, `CaseList.tsx`, `MyCasesScreen.tsx`, `MyCasesScreen.css` | 여철준. H2 확정 후 `CaseForm.tsx` 표시 언어 선택 추가는 권길현 |
| 검토 대기 목록 화면 | `frontend/src/screens/ReviewQueueScreen.tsx` | 여철준 |
| 담당자 검토·승인, 이용자 승인 결과 화면 | `frontend/src/screens/ReviewScreen.tsx`, `ApprovedResultScreen.tsx` | 여철준 |
| 준비 체크·완료 화면 | `frontend/src/screens/PreparationCheckScreen.tsx`, `CompletionScreen.tsx` | 김태후 |
| 기준 관리·보완 화면 | `frontend/src/screens/CriteriaScreen.tsx`, `SupplementScreen.tsx` | 이주환 |
| 상태·취소·입력 수정 화면 | `frontend/src/screens/CaseStatusScreen.tsx`, `InputRevisionScreen.tsx` | 권길현 |
| 후속 화면 API·타입·임시 응답 | `frontend/src/api/criteria.ts`, `reviewQueue.ts`, `approval.ts`, `preparationCheck.ts`, `supplementation.ts`, `completion.ts`, `cancellation.ts`, `inputRevision.ts` | 해당 스토리의 화면 담당자. API 응답 타입과 임시 응답도 해당 파일 또는 같은 이름의 스토리별 파일에 둔다 |
| 화면 공통 조립·기존 API·타입 | `frontend/src/App.tsx`, `main.tsx`, `types.ts`, `tokens.css`, `api/cases.ts` | 여철준 (다른 스토리 담당자는 연결에 필요한 변경 전달) |

문서별 수정 담당은 위 규칙 4를 따른다. 다른 담당 파일 변경은 PR에 요청으로 남긴다. 새 router 등록은 이주환에게 전달하며, 스토리별 요청·응답 스키마는 해당 router에서 관리하고 공통 스키마 변경은 김민건과 맞춘다. 공통 기준 시드와 PreparationItem 시드는 Criterion·PreparationItem 모델 확정 후 연결하고, 모의 항목을 실제 승인 결과로 표시하지 않는다. 표의 테스트 파일은 각 스토리의 정상·실패·권한 경로를 담당하며, US-02 실패 테스트는 2단계 API 합의 후 작성한다.
