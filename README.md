# 다문화가족 체류 AI 도우미

한국에 사는 베트남 결혼이민자와 한국인 배우자를 위한 체류(F-6) AI 도우미입니다. 한국 출입국·체류 법령을 근거로 **베트남어로 답하고**, 체류 서류를 분석해 **꼭 확인할 것·주의점·다음 행동**을 알려 줍니다. 근거 조문은 항상 한국어 원문으로 함께 보여 줍니다.

> 법률 정보 제공 서비스이며 법률 자문이나 체류 허가가 아닙니다.

## 팀

| 항목 | 내용 |
| --- | --- |
| 팀명 | multicultural-families (저장소 식별명) |
| 배정받은 큰 도메인 | 다문화 가정의 한국 생활·법률·제도 정보 이용 |
| 세부 주제 (한 줄) | 체류 법령을 근거로 베트남어 질문에 답하고 체류 서류를 분석해 주의점과 다음 행동을 알려 주는 AI 도우미 |
| 팀원과 역할 | [docs/team/roles.md](docs/team/roles.md) |

## 기능

| 기능 | 설명 |
| --- | --- |
| **질문하기** | 체류 질문(베트남어·한국어) → 법령 검색(하이브리드 + 법령 관계 그래프) → 베트남어 답변 스트리밍 → 인용 조문 검증 → 근거 조문 카드 |
| **조문 보기** | 한국어 원문, 현행 여부, 위임·참조 관계 조문 |
| **서류 분석** | PDF·DOCX 업로드 → 식별정보 마스킹 → 개인 상황 질문 → 꼭 확인 / 주의 / 일반 분류, 주의점, 원문 형광펜, 근거 → 다음 행동 체크리스트 |

## 세부 주제 필수 조건

| 조건 | 우리 주제에서는 | 자세히 |
| --- | --- | --- |
| LLM이 서비스 기능 안에서 쓰인다 | OpenAI로 질의 재작성, 답변·서류 분석 생성. 인용 조문은 코드로 검증 | [PRD 7절](docs/PRD.md#7-상태와-llm의-역할) |
| 핵심 대상에 상태 전이가 있다 | 서류 분석 건: 업로드됨 → 질문 대기 → 분석중 → 결과 확인 → 완료 (분석 실패·취소 포함) | [user-flows.md](docs/requirements/user-flows.md), [DATA-MODEL](docs/DATA-MODEL.md) |

## 구조

```
backend/    FastAPI · PostgreSQL(pgvector) · OpenAI — 법령 적재, 검색, 답변·인용 검증, 서류 분석 API
frontend/   React · TypeScript 웹 (Vite)
docs/       PRD, 백로그, API, 데이터 구조, 디자인
```

## 문서 기준

현재 구현은 2026-11-09 인수인계와 PRD v2.0을 기준으로 합니다. `docs/domain/`, `docs/interview/`, `docs/proposal/`와 이전 결정·회고는 당시 조사·제안·실행 기록입니다. 그 안의 담당자 승인 흐름·MySQL·Gemini·예전 US 번호를 현재 요구사항으로 적용하지 않습니다.

## 문서 지도

| 문서 | 내용 |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | 무엇을, 왜 만드는지 |
| [docs/requirements/user-flows.md](docs/requirements/user-flows.md) | 질문하기·서류 분석하기 흐름 |
| [docs/requirements/backlog.md](docs/requirements/backlog.md) | 스토리 US-01~US-09와 인수 조건 |
| [docs/decisions/mvp-scope.md](docs/decisions/mvp-scope.md) | MVP 포함·제외, 다루는 법령 |
| [docs/STACK.md](docs/STACK.md) | 기술 스택과 이유 |
| [docs/DATA-MODEL.md](docs/DATA-MODEL.md) | 법령·서류 분석 건 데이터와 상태값 |
| [docs/API.md](docs/API.md) | 화면과 서버의 약속 |
| [docs/DESIGN.md](docs/DESIGN.md) | 화면 목록, 토큰, 상태 표시 |
| [docs/CODE-STYLE.md](docs/CODE-STYLE.md) | 코딩 규칙, 폴더 구조 |
| [docs/domain/](docs/domain/) | 도메인 조사 (용어, 사람·흐름, 규칙) |
| [docs/team/](docs/team/) | 역할, 작업 규칙 |
| [인수인계](docs/decisions/handoff-2026-11-09.md) | 최신 개발 방향과 작성 당시 작업 목록 |
| [문서 정합성·남은 결정](docs/decisions/handoff-alignment-2026-11-10.md) | main 반영 상태, 미정 항목과 해결안 |
| `logs/` | 일일 기록, 개인 회고 |

## 실행 방법

팀의 [백엔드 실행 안내](backend/README.md)에 기록된 실행 절차입니다. 이번 문서 수정에서 새로 실행한 결과를 뜻하지 않습니다. Python 3.12·Docker·Node.js가 필요합니다.

저장소 루트에서 서버를 준비합니다.

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/python -m ingest load
LLM_FAKE=true .venv/bin/uvicorn app.main:app --reload --port 8000
```

다른 터미널에서 저장소 루트로 이동한 뒤 화면을 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

화면은 `http://localhost:5173`, 서버 상태는 `http://127.0.0.1:8000/health`입니다. DB는 PostgreSQL 16 + pgvector이며 호스트 포트는 5433입니다. `LLM_FAKE=true`는 고정된 개발용 응답으로, 실제 AI 품질 검증과 구분합니다.

실제 OpenAI 연결은 서버의 `OPENAI_API_KEY` 설정과 `LLM_FAKE` 해제 후 조문 요약·임베딩 생성이 필요합니다. 비밀 값 파일을 열거나 커밋하지 않습니다. 자세한 명령은 백엔드 안내를 따릅니다.

## 작업 규칙

- main에 바로 커밋하지 않습니다. 브랜치 → PR → 팀원 1명 이상 승인 → 병합.
- 커밋 메시지는 `종류: 내용` 형식의 한국어 (`docs`·`feat`·`fix`·`test`·`logs`).
