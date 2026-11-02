# MCP 사용 결정

- 작성일: 2026-11-02
- 작성: 김태후 (S2 역할 분담에서 MCP 담당)
- 근거: [기술 스택](../STACK.md), [권한 규칙](permissions.md), `CLAUDE.md` "LLM에 보내지 않는 것"
- 결과: Context7 1개를 고름. `.mcp.json`에 키 없이 등록함. Claude Code 안에서의 승인·사용은 아래 "확인 필요" 참고.

## 1. 고른 서버와 이유

| 서버 | 하는 일 | 고른 이유 |
| --- | --- | --- |
| Context7 (`https://mcp.context7.com/mcp`) | 라이브러리 이름으로 공식 문서·예제 코드를 찾아 Claude에게 넘김 | 우리 스택(FastAPI·Pydantic·pytest·React·TypeScript·Gemini API)은 버전마다 사용법이 바뀌는 라이브러리가 많다. Claude가 옛 사용법으로 코드를 쓰면 실행해 봐야 틀린 걸 알게 된다. API 키가 없어도 되고 읽기만 하므로 저장소·DB·비밀값을 건드리지 않는다 |

## 2. 고르지 않은 서버와 이유

| 서버 | 안 고른 이유 |
| --- | --- |
| MySQL | DB 접속 정보(비밀값)가 필요하고, 뼈대에 DB 연결이 아직 없다(`scaffold-log.md` 1절 "뺌"). Claude가 DB를 직접 바꿀 수 있게 되는 위험도 있다 |
| GitHub | 토큰이 필요하다. PR·이슈 확인은 이미 `gh` CLI로 할 수 있다 |
| Playwright(브라우저) | 화면 확인에 쓸 수 있지만 첫 기능 화면이 아직 없다. 스크린샷 등 파일이 생겨 `.gitignore` 관리가 늘어난다. 화면이 생긴 뒤 다시 판단한다 |

## 3. 설치

실제로 실행한 명령(2026-11-02, macOS, Claude Code 2.1.316):

```
claude mcp add --scope project --transport http context7 https://mcp.context7.com/mcp
```

결과: 저장소 루트에 `.mcp.json`이 생겼다. 내용은 서버 이름·종류·주소뿐이고 키는 없다. 따로 설치한 패키지는 없다.

## 4. 연결 확인

| 확인 | 명령 | 결과 |
| --- | --- | --- |
| Claude Code 등록 상태 | `claude mcp get context7` | `Scope: Project config (shared via .mcp.json)`, `Status: ⏸ Pending approval (run \`claude\` to approve)` |
| 서버 접속·도구 목록 | `curl`로 `tools/list` 요청 | 도구 2개 응답: `resolve-library-id`, `query-docs` |
| 실제 조회 | `curl`로 `resolve-library-id`(libraryName `fastapi`) 요청 | FastAPI 문서 ID `/websites/fastapi_tiangolo` 응답 |
| 새로 생긴 로컬 파일 | `ls -a` | `.mcp.json`만 생김. `.gitignore` 수정 안 함 |

**확인 필요:** 프로젝트 MCP는 각자 `claude`를 새로 열 때 승인해야 켜진다. Claude Code 안에서 승인하고 Context7을 써 본 기록은 아직 없다. 승인한 사람이 아래 5절에 적는다.

## 5. 사용 기록

| 날짜 | 쓴 사람 | 무엇을 찾았나 | 결과를 그대로 썼나 / 확인했나 |
| --- | --- | --- | --- |
| 2026-11-02 | 김태후 | 연결 확인용 `fastapi` 문서 ID 조회 (`curl`) | 응답이 오는 것만 확인. 코드에 쓰지 않음 |
|  |  |  |  |

## 6. 쓸 때 지킬 것

- Context7에는 **라이브러리 이름과 사용법 질문만** 보낸다. 상황 설명·PDF 내용·기준 본문·계정 정보 등 서비스 데이터는 보내지 않는다.
- Context7이 보여 준 사용법도 실제로 돌려 보기 전에는 확인된 명령·코드로 적지 않는다.
- 다른 MCP를 더 추가하면 이 문서 1·2절에 이유를 적고, 키가 필요한 서버는 키를 `.mcp.json`에 넣지 않는다.
