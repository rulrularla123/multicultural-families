# MCP 사용 기록

- 작성 시작일: 2026-11-02 (김태후, 이번 작업 분담의 테스트·MCP 담당)

## 1. 팀 결정 — 우리 팀에 필요한 MCP

**필요한 일 파악** (`STACK.md`, `PRD.md`, `backlog.md`를 보고 외부 도구가 있으면 좋은 일)

| 필요한 일 | 왜 필요한가 (우리 팀 상황에서) |
| --- | --- |
| FastAPI·Pydantic·pytest의 현재 버전 사용법 확인 | 첫 기능의 서버·테스트를 오늘 만든다. STACK.md "새로 배워야 할 것"에 "Python에서 LLM 응답 형식 검증"이 있고, PRD 7절은 Pydantic 검증과 TestClient 테스트를 쓴다. Claude가 옛 버전 사용법으로 쓰면 실행해 봐야 틀린 걸 안다 |
| React·TypeScript의 현재 버전 사용법 확인 | STACK.md "새로 배워야 할 것"에 "React 컴포넌트·상태 관리와 TypeScript 자료형"이 있다 |
| Gemini API 구조화 출력·SDK 사용법 확인 | PRD 7절 "지원되는 세부 모델 ID와 SDK 버전은 실제 연동 전에 확인한다" |

**후보 비교와 선택** (Claude가 찾아 준 것도 공식 문서·저장소로 직접 확인한 것만 적음)

| 후보 서버 | 공식 문서·저장소 (주소, 절) | 하는 일 | 내 컴퓨터에서 실행되는 명령 | 읽기만 / 쓰기도 | 키 필요 | 고른다 / 보류 / 고르지 않는다 | 이유 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Context7 | https://github.com/upstash/context7 "Installation", "Available Tools > MCP Tools" | 라이브러리 이름을 문서 ID로 바꾸고(`resolve-library-id`), 그 문서를 가져온다(`query-docs`) | 없음. 원격 HTTP 서버 `https://mcp.context7.com/mcp`에 연결 | 읽기만 (도구 2개 모두 조회) | 선택. 없어도 동작하고, 있으면 사용 한도가 높아진다("API Key Recommended") | 고른다 | 위 세 가지 필요한 일에 바로 맞는다. 키 없이 쓸 수 있고 저장소·DB·비밀값을 건드리지 않는다. 2026-11-02에 FastAPI·Pydantic·pytest·React·Gemini API 문서 ID가 모두 조회됨(3절) |

| 항목 | 우리 결정 |
| --- | --- |
| 쓰는 서버 (팀당 1~2개부터. 없으면 "연결하지 않음"과 이유) | Context7 1개 |
| 설정 위치 | 저장소 `.mcp.json` (키 없음) |
| 승인 방법 | 각자 프로젝트 서버를 읽고 하나씩 승인 (일괄 승인 설정 안 씀) |
| 버전 고정 여부 🔧 | 고정하지 않음. 원격 HTTP 주소로 연결해 내 컴퓨터에 설치하는 패키지가 없다 |
| 설치에 쓴 공식 문서 (주소, 절) | Claude Code MCP 문서 https://code.claude.com/docs/en/mcp "Option 1: Add a remote HTTP server", "Project scope". 서버 주소는 Context7 README "Installation" |
| 보류한 서버와 이유 | MySQL 계열: 뼈대에 DB 연결이 아직 없다(`scaffold-log.md` 1절 "뺌"). GitHub 계열: PR·이슈 확인은 이미 설치된 `gh` CLI로 한다. 브라우저 계열(Playwright 등): 첫 기능 화면이 아직 없어 화면이 생긴 뒤 다시 본다. 세 후보 모두 공식 문서를 직접 확인하지 않아 위 비교 표에 넣지 않았다 |

설치에 실제로 실행한 명령 (2026-11-02, macOS, Claude Code 2.1.316). 결과로 `.mcp.json`이 생겼고 다른 파일은 생기지 않아 `.gitignore`는 고치지 않았다.

```
claude mcp add --scope project --transport http context7 https://mcp.context7.com/mcp
```

Context7에는 라이브러리 이름과 사용법 질문만 보낸다. 상황 설명·PDF 내용·기준 본문·계정 정보 등 서비스 데이터는 보내지 않는다(`CLAUDE.md` "LLM에 보내지 않는 것"과 같은 기준).

## 2. 연결 확인 (5명 전원, 구현을 시작하기 전에)

| 이름 | 따로 설치한 것 (런타임·브라우저 등, 공식 문서 주소) | `claude mcp list` 상태 | `/mcp` 상태 | 남은 문제 (실패하면 운영체제, 명령, 오류 메시지 그대로) |
| --- | --- | --- | --- | --- |
| 김태후 | 없음 | context7: https://mcp.context7.com/mcp (HTTP) - ⏸ Pending approval (run claude to approve) | 확인 필요 (승인 전) | 새 `claude` 세션에서 승인한 뒤 `/mcp` 상태를 적어야 함 |
| 권길현 | | | | |
| 김민건 | | | | |
| 여철준 | | | | |
| 이주환 | | | | |

## 3. 사용 기록

| 날짜 | 누가 | MCP (서버 이름) | 어떤 작업 | 무엇을 요청했나 | 무엇을 얻었나 | 내가 직접 확인한 것 | 쓰지 않은 것과 이유 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-02 | 김태후 | context7 | 고르기 전 연결·범위 확인 (Claude Code 밖에서 `curl`로 직접 요청) | `tools/list`, 그리고 `resolve-library-id`에 fastapi·pydantic·pytest·react·gemini api | 도구 2개(`resolve-library-id`, `query-docs`)와 문서 ID: `/websites/fastapi_tiangolo`, `/pydantic/pydantic`, `/pytest-dev/pytest`, `/reactjs/react.dev`, `/websites/ai_google_dev_gemini-api` | 응답이 오는 것과 문서 ID 이름 | 문서 본문(`query-docs`)은 받지 않았고 코드에 쓰지 않음. 구현 작업에 쓴 기록이 아님 |
| | | | | | | | |
| | | | | | | | |
