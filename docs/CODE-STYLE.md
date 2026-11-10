# 코딩 스타일

- 작성일: 2026-11-09
- 근거: [STACK.md](STACK.md)

## 규칙

| # | 규칙 | 지키는지 확인하는 방법 |
| --- | --- | --- |
| 1 | Python 파일·함수·변수는 `snake_case`, 클래스는 `PascalCase`. TypeScript 함수·변수는 `camelCase`, React 컴포넌트 파일·함수는 `PascalCase` | PR diff에서 이름 확인 |
| 2 | Python은 `ruff check`를 통과한다(줄 길이 120). TypeScript는 `npm run lint`(oxlint)와 `npm run build`를 통과한다 | CI와 로컬에서 같은 명령 |
| 3 | 서버 코드는 아래 폴더 구조를 따른다. API 라우터는 얇게 두고 로직은 `services/`·`retrieval/`·`generation/`·`documents/`에 둔다 | PR의 변경 경로 확인 |
| 4 | DB 스키마는 Alembic 마이그레이션으로만 바꾼다. 모델과 마이그레이션은 같은 PR에 넣는다 | `alembic upgrade head`가 빈 DB에서 성공하는지 CI로 확인 |
| 5 | 커밋은 `docs`·`feat`·`fix`·`test`·`logs` 중 하나에 `: 한국어 내용`. `main`에 직접 커밋하지 않고 PR로 올린다 | `git log --oneline` |
| 6 | 테스트 함수는 `test_`로 시작하고 확인하는 행동을 이름에 쓴다. 관련 `US-xx`는 docstring에 쓴다. LLM은 `LLM_FAKE` 또는 테스트 대역으로 대신하고 실제 API를 부르지 않는다 | pytest, PR 리뷰 |
| 7 | 테스트 기대값은 인수 조건과 API.md에서 가져온다. 구현에 맞춰 바꾸지 않는다 | PR 리뷰 |
| 8 | 키·토큰·비밀번호·실제 개인정보를 코드·문서·로그에 넣지 않는다. `.env`는 저장소에 올리지 않는다 | `git ls-files .env backend/.env`가 비어 있음 |

## 폴더 구조

| 폴더 | 내용 |
| --- | --- |
| `backend/app/api/v1/` | FastAPI 라우터 (chat, provisions, search, documents) |
| `backend/app/core/` | 설정, DB 연결, 언어, 체류 용어집 |
| `backend/app/models/` | SQLAlchemy 모델 |
| `backend/app/retrieval/` | 질의 재작성, BM25, 벡터 검색, 그래프 확장, 리랭크 |
| `backend/app/generation/` | 답변 생성, 인용 검증 |
| `backend/app/documents/` | 서류 추출·나누기·마스킹·개인화 질문·분석 |
| `backend/app/services/` | API가 부르는 흐름 (질문 답변, 서류 분석 상태 관리) |
| `backend/app/common/` | 식별정보 패턴 검사·마스킹 |
| `backend/ingest/` | 법령 수집·파싱·관계 추출·적재 명령 |
| `backend/alembic/` | 마이그레이션 |
| `backend/tests/` | 서버 테스트 |
| `backend/data/demo/` | 샘플 서류 (가상 문서) |
| `frontend/src/` | React 화면 (`api/`, `screens/`, `components/`, `i18n/`) |
