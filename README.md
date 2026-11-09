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
| `logs/` | 일일 기록, 개인 회고 |

## 실행 방법

서버·화면 구성 중입니다. 실제로 실행해 본 명령만 여기에 적습니다.

## 작업 규칙

- main에 바로 커밋하지 않습니다. 브랜치 → PR → 팀원 1명 이상 승인 → 병합.
- 커밋 메시지는 `종류: 내용` 형식의 한국어 (`docs`·`feat`·`fix`·`test`·`logs`).
