# [프로젝트 가제목]

> 이 파일은 저장소의 첫 화면입니다. 처음 온 사람(교사, 클라이언트, 다른 팀)이 1분 안에 "누가 무엇을 만들고, 기록은 어디 있는지" 알 수 있게 **요약과 링크만** 둡니다.
> 조사 내용은 아래 문서 지도의 각 파일에 씁니다. README에 조사 내용을 옮겨 적지 않습니다.
> `>`로 시작하는 안내 문장은 내용을 채운 뒤 지워도 됩니다.

## 팀

| 항목 | 내용 |
| --- | --- |
| 팀명 | |
| 배정받은 큰 도메인 | |
| 세부 주제 (한 줄) | `___(누가)가 ___(무엇)을 할 수 있게 하는 서비스` — 4단계에서 확정한 뒤 씁니다 |
| 팀원과 역할 | [docs/team/roles.md](docs/team/roles.md) |

## 세부 주제 필수 조건

| 조건 | 우리 주제에서는 | 자세히 |
| --- | --- | --- |
| LLM이 서비스 기능 안에서 쓰인다 | (예: 고객 문의를 읽고 답변 초안을 만들어 CS 담당이 고쳐 보낸다) | [03-rules-states-llm.md](docs/domain/03-rules-states-llm.md#3-4-llm이-들어갈-자리) |
| 핵심 대상에 상태 전이가 있다 | (예: 결제완료 → 상품준비중 → 배송지시 → 배송중 → 배송완료, 취소·반품 분기) | [03-rules-states-llm.md](docs/domain/03-rules-states-llm.md#3-2-핵심-대상과-상태-전이) |

## 문서 지도

| 단계 | 파일 | 하는 일 | 상태 |
| --- | --- | --- | --- |
| 0 | [docs/team/roles.md](docs/team/roles.md) | 팀 구성, 역할, 교대 계획 | ☐ |
| 0 | [docs/domain/README.md](docs/domain/README.md) | 조사 관점, 태그 규칙, 파일 규칙, 찾아볼 곳 | 읽기만 |
| 1 | [docs/domain/01-first-look-glossary.md](docs/domain/01-first-look-glossary.md) | 첫인상, 용어 사전, 검색어 | 초안 완료 · 리뷰 대기 |
| 2 | [docs/domain/02-people-flow-benchmark.md](docs/domain/02-people-flow-benchmark.md) | 사람, 현재 흐름, 데이터, 기존 서비스, 논문 | ☐ |
| 3 | [docs/domain/03-rules-states-llm.md](docs/domain/03-rules-states-llm.md) | 규칙, 상태 전이, LLM 자리, 법령·통계 | ☐ |
| - | [docs/domain/cards/](docs/domain/cards/) | 논문·자료 근거 카드 (카드마다 파일 하나) | ☐ |
| - | [docs/domain/ai-check-log.md](docs/domain/ai-check-log.md) | AI에게 물어본 것과 확인 결과 | ☐ |
| 4 | [docs/decisions/topic-selection.md](docs/decisions/topic-selection.md) | 필수 조건 확인, 후보 평가, 주제 확정 | ☐ |
| 5 | [docs/interview/mvp-assumptions-questions.md](docs/interview/mvp-assumptions-questions.md) | MVP 가설, 기능 목록, 가정·위험, 질문지, 미팅 준비 | ☐ |
| 6 | [docs/proposal/README.md](docs/proposal/README.md) | **클라이언트에게 보내는 프로젝트 제안서** (Claude 초안 → 팀 확인 → Word 양식, 완성본 docx·PDF) | ☐ |
| - | `logs/pre-[GitHub 아이디].md` | 개인 회고 (사람마다 파일 하나) | ☐ |

> 단계가 끝나면 상태 칸을 ☑로 바꾸고 PR로 올립니다.

## 작업 규칙

- 첫 커밋 이후에는 main에 바로 커밋하지 않습니다. 모든 변경은 브랜치를 만들고 PR로 올린 뒤, 팀원 1명 이상이 승인하면 병합합니다.
- 표가 있는 단계 파일(01~03, topic-selection 등)은 **블록마다 정리 담당 1명**이 고칩니다. 다른 사람은 근거 카드를 쓰거나 PR에 댓글을 남깁니다. 여러 명이 같은 파일을 동시에 고치면 충돌이 납니다.
- 근거 카드와 개인 회고는 사람마다 파일이 달라 동시에 써도 충돌하지 않습니다.
