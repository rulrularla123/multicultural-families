# 다문화가족 체류 행정 준비 도우미

> 이 파일은 저장소의 첫 화면입니다. 처음 온 사람(교사, 클라이언트, 다른 팀)이 1분 안에 "누가 무엇을 만들고, 기록은 어디 있는지" 알 수 있게 **요약과 링크만** 둡니다.
> 조사 내용은 아래 문서 지도의 각 파일에 씁니다. README에 조사 내용을 옮겨 적지 않습니다.
> `>`로 시작하는 안내 문장은 내용을 채운 뒤 지워도 됩니다.

## 팀

| 항목 | 내용 |
| --- | --- |
| 팀명 | multicultural-families (저장소 식별명) |
| 배정받은 큰 도메인 | 다문화 가정의 한국 생활·법률·제도 정보 이용 |
| 세부 주제 (한 줄) | 한국어 안내 이해에 도움이 필요한 결혼이민자가 체류기간 연장 준비 항목을 이해하고 보완할 수 있게 하는 서비스 |
| 팀원과 역할 | [docs/team/roles.md](docs/team/roles.md) |

## 세부 주제 필수 조건

| 조건 | 우리 주제에서는 | 자세히 |
| --- | --- | --- |
| LLM이 서비스 기능 안에서 쓰인다 | Claude가 공식 원문으로 쉬운 다국어 설명·준비 항목 초안을 만들고 담당자가 제공 전에 승인 | [03-rules-states-llm.md](docs/domain/03-rules-states-llm.md#3-4-llm이-들어갈-자리) |
| 핵심 대상에 상태 전이가 있다 | 절차 준비 건: 준비중 → 안내 검토 대기 → 서류 준비중 → 준비 확인 요청 → 준비 확인 완료. 보완·취소·버전 변경 경로 포함 | [03-rules-states-llm.md](docs/domain/03-rules-states-llm.md#3-2-핵심-대상과-상태-전이) |

## 문서 지도

| 단계 | 파일 | 하는 일 | 상태 |
| --- | --- | --- | --- |
| 0 | [docs/team/roles.md](docs/team/roles.md) | 팀 구성, 역할, 교대 계획 | 작성 완료 |
| 0 | [docs/domain/README.md](docs/domain/README.md) | 조사 관점, 태그 규칙, 파일 규칙, 찾아볼 곳 | 읽기만 |
| 1 | [docs/domain/01-first-look-glossary.md](docs/domain/01-first-look-glossary.md) | 첫인상, 용어 사전, 검색어 | 작성 완료 · 기존 출처·태그 유지 |
| 2 | [docs/domain/02-people-flow-benchmark.md](docs/domain/02-people-flow-benchmark.md) | 사람, 현재 흐름, 데이터, 기존 서비스, 논문 | 작성 완료 · 논문 3편 결론·표 및 공식 서비스 비교 반영 |
| 3 | [docs/domain/03-rules-states-llm.md](docs/domain/03-rules-states-llm.md) | 규칙, 상태 전이, LLM 자리, 법령·통계 | 작성 완료 · 서비스 규칙·법령 확인 범위 구분 |
| - | [docs/domain/cards/](docs/domain/cards/) | 논문·자료 근거 카드 (카드마다 파일 하나) | 학술논문 3편 결론·표 확인 및 공식 자료 연결 |
| - | [docs/domain/ai-check-log.md](docs/domain/ai-check-log.md) | AI에게 물어본 것과 확인 결과 | 조사 확인·질문지 모의 검토 기록 작성 |
| 4 | [docs/decisions/topic-selection.md](docs/decisions/topic-selection.md) | 필수 조건 확인, 후보 평가, 주제 확정 | B를 문서 기준 주제로 선정 · 현장 검증은 5단계 가정 |
| 5 | [docs/interview/mvp-assumptions-questions.md](docs/interview/mvp-assumptions-questions.md) | MVP 가설, 기능 목록, 가정·위험, 질문지, 미팅 준비 | 작성 완료 · 문서 검토 기록·미팅 역할 배정 |
| 6 | [docs/proposal/README.md](docs/proposal/README.md) | **클라이언트에게 보내는 프로젝트 제안서** (Claude 초안 → 팀 확인 → Word 양식, 완성본 docx·PDF) | ☐ |
| - | `logs/pre-[GitHub 아이디].md` | 개인 회고 (사람마다 파일 하나) | ☐ |
| 2-1 | [docs/requirements/user-flows.md](docs/requirements/user-flows.md) | 첫 데모에서 보여줄 핵심 사용자 흐름 (상태 4개 이상) | ☑ 상태 6개 · 취소·반려 US-04·06·08 연결 |
| 2-1 | [docs/requirements/backlog.md](docs/requirements/backlog.md) | 스토리와 인수 조건, 필수/선택 | ☑ 필수 8개 · 금지어 없음 |
| 2-1 | [docs/decisions/mvp-scope.md](docs/decisions/mvp-scope.md) | MVP 포함·제외(이유), 제안서(v2)와 다른 점 | 작성 중 · 제안서(v2)와 다른 점 남음 |
| 2-1 | [docs/decisions/stack-inputs.md](docs/decisions/stack-inputs.md) | 기술 스택을 정하기 전 우리 팀 경험·조건 정리 | 작성 중 · 팀원별 줄 채우는 중 |
| 2-1 | [docs/team/working-agreement.md](docs/team/working-agreement.md) | 팀 작업 규칙 | ☐ |
| 2-1 | [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) | 스토리·버그 이슈 양식 | ☐ |
| 2-2 | [docs/STACK.md](docs/STACK.md) | 기술 스택 결정과 이유 | ☐ |
| 2-2 | [docs/PRD.md](docs/PRD.md) | 정한 문서를 모은 PRD v0.1과 대조 기록 | ☐ |
| 2-2 | [CLAUDE.md](CLAUDE.md) | Claude가 매 세션 읽는 팀 지침 | ☐ |
| 2-2 | [.claude/settings.json](.claude/settings.json) | 허용·확인·차단 권한 | ☐ |
| 2-2 | [docs/decisions/permissions.md](docs/decisions/permissions.md) | 권한 규칙의 이유와 시험 결과 | ☐ |
| 2-2 | [docs/team/claude-rules.md](docs/team/claude-rules.md) | 팀 규칙 합의 기록 | ☐ |
| 2-2 | [.claude/agents/](.claude/agents/) | stack-advisor, prd-writer | ☐ |
| 2-2 | [docs/decisions/scaffold-log.md](docs/decisions/scaffold-log.md) | 뼈대 계획·실행 결과·막힌 지점 | ☐ |

> 단계가 끝나면 상태 칸을 ☑로 바꾸고 PR로 올립니다.

## 작업 규칙

- 첫 커밋 이후에는 main에 바로 커밋하지 않습니다. 모든 변경은 브랜치를 만들고 PR로 올린 뒤, 팀원 1명 이상이 승인하면 병합합니다.
- 표가 있는 단계 파일(01~03, topic-selection 등)은 **블록마다 정리 담당 1명**이 고칩니다. 다른 사람은 근거 카드를 쓰거나 PR에 댓글을 남깁니다. 여러 명이 같은 파일을 동시에 고치면 충돌이 납니다.
- 근거 카드와 개인 회고는 사람마다 파일이 달라 동시에 써도 충돌하지 않습니다.
