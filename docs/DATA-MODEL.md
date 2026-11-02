# 데이터 구조

- 대상 차시: 3주차 1일차 (수업일 2026-11-03)
- 작성일: 2026-11-02
- 작성: 김민건 / 개발자1 업무
- 상태: US-04 서버와 맞춘 담당자 작성안. 팀 합류에서 확정하고 PM이 PRD에 반영할 내용이다.
- 근거: [PRD 6·7절](PRD.md#6-데이터-구조), [선정 주제 B 상태 흐름](domain/03-rules-states-llm.md#선정-주제-b의-상태-흐름), [백로그 US-04](requirements/backlog.md#us-04-담당자가-분석-결과를-반려하기).

## 모델과 필드

오늘 선택한 기능은 **US-04 담당자 반려(F-04)**다. 반려·사유 표시·분석 비공개에 필요한 세 모델을 정리한다. 상태 목록은 전체 흐름과 동일하게 유지하되 다른 상태의 변경 API까지 구현하지 않는다. DB는 STACK의 MySQL, 문자열 인코딩은 utf8mb4다.

| 모델 | 필드 | 타입 | 필수 | 설명 | 연결된 기능 ID |
| --- | --- | --- | --- | --- | --- |
| PreparationCase (절차 준비 건) | id | BIGINT UNSIGNED, PK | 예 | 준비 건 ID. 시드에서는 고정 ID 사용 | F-01·F-04 |
| PreparationCase | owner_id | VARCHAR(64) | 예 | 모의 이용자 식별자. 담당자 역할은 서버가 별도 판단 | F-01·F-04 |
| PreparationCase | situation | TEXT | 예 | 이용자가 입력한 상황. 오늘은 모의 시드만 사용하고 생성 API는 만들지 않음 | F-01·F-04 |
| PreparationCase | display_language | VARCHAR(32) | 예 | 표시 언어. 시드 실행 시 주입하며 첫 모국어를 임의로 확정하지 않음 | F-05 |
| PreparationCase | status | VARCHAR(32) | 예 | 아래 한글 상태값 8개만 허용 | F-04 |
| CheckResult (점검 결과) | id | BIGINT UNSIGNED, PK | 예 | 점검 결과 ID. 오늘은 비공개 시험용 모의 초안 | F-03·F-04 |
| CheckResult | case_id | BIGINT UNSIGNED, FK | 예 | 소속 준비 건 | F-03·F-04 |
| CheckResult | analysis_items | JSON 배열 | 예 | 담당자용 초안. 이용자 상세 응답에는 포함하지 않음 | F-03·F-04 |
| CheckResult | criterion_versions | JSON 배열 | 예 | 점검 당시 기준 ID·버전 스냅샷. 반려 이력에 보존 | F-02·F-04 |
| CheckResult | invalidated_at | DATETIME(6), NULL 허용 | 반려 시 | 반려 시 기록. 이전 초안을 현재 결과로 쓰지 않음 | F-04 |
| CaseHistory (처리 이력) | case_id | BIGINT UNSIGNED, FK | 예 | 소속 준비 건 | F-04·F-08 |
| CaseHistory | from_status | VARCHAR(32) | 예 | 반려 전 담당자 승인 대기 | F-04 |
| CaseHistory | to_status | VARCHAR(32) | 예 | 반려 후 준비중 | F-04 |
| CaseHistory | actor_id | VARCHAR(64) | 예 | 실제 권한 검사에 사용한 담당자 모의 계정 ID | F-04 |
| CaseHistory | reason | LONGTEXT | 예 | 앞뒤 공백 제거 후 1자 이상인 반려 사유. 해당 건 소유자·담당자만 조회 | F-04 |

### 구현에 함께 필요한 기술 필드

| 모델 | 필드·타입 | 쓰는 이유 |
| --- | --- | --- |
| PreparationCase | support_type VARCHAR(16), situation_version·document_version INTEGER, current_check_task_id VARCHAR(64) NULL, created_at DATETIME(6) | F-6-1과 입력 버전 보존. 반려 시 현재 점검 작업 연결 해제. 다른 스토리의 입력 변경·재점검은 아직 구현하지 않음 |
| CheckResult | situation_version·document_version INTEGER, task_id VARCHAR(64) NULL, failure_reason TEXT NULL | 이후 US-02 연결에 필요한 점검 당시 정보. 오늘 실제 LLM 호출은 없음 |
| CaseHistory | id BIGINT UNSIGNED PK, actor_role VARCHAR(16), occurred_at DATETIME(6), criterion_versions JSON 배열 | 이력 식별·처리자 역할·UTC 처리 시각·당시 기준 버전 보존 |

첨부 서류·적용 기준·준비 항목 및 기준 연결 테이블은 기존 PRD 6절 설계를 유지하고 해당 스토리 구현에서 구체화한다. 오늘 서버에 구현됐다고 표시하지 않는다. JSON 스냅샷이 실제 기준과의 외래 키 검증을 대신하지는 않는다.

## 관계

- PreparationCase 1개 → CheckResult 여러 개, CaseHistory 여러 개. case_id로 연결하고 임의의 연쇄 삭제를 설정하지 않는다.
- 반려는 준비 건 행을 잠근 뒤 현재 상태를 검사하고, 상태 변경·점검 결과 무효화·이력 저장을 한 트랜잭션으로 처리한다. 어느 단계든 실패하면 모두 되돌린다.
- 최소 상세 조회는 소유자·담당자만 허용한다. rejection_reason은 이력에서 계산하는 응답 필드이며 준비 건 테이블에 중복 저장하지 않는다.
- 반려 요청·응답과 모의 계정 사용 방식은 [서버 전달안](../backend/README.md#화면-담당자pm에게-전달할-api-계약)에서 확인한다. 공유 API 약속은 개발자1·2 합의 후 PM이 반영한다.

## 상태값 (핵심 대상의 `status`)

한글 값을 API·DB에서 동일하게 사용한다. 아래 목록은 `03` 문서의 **선정 주제 B** 상태도와 글자·띄어쓰기까지 일치한다.

| 상태값 | `03` 문서의 상태 이름 | 누가 바꿀 수 있나 | 어떤 경우에 바뀌나 |
| --- | --- | --- | --- |
| 준비중 | 준비중 | 이용자 생성 / 담당자 반려 | 유효한 새 건 생성, 또는 승인 대기에서 담당자가 사유 입력 후 반려 |
| 자동 점검중 | 자동 점검중 | 시스템 규칙 | 유효 입력·등록 기준 확인. 진행 중 상황·서류·기준 변경이면 이전 작업 무효화 후 재점검 |
| 담당자 승인 대기 | 담당자 승인 대기 | 시스템 규칙 | 점검 결과 또는 점검 시작 후 실패 사유 저장. 입력·추출 실패는 준비중 유지 |
| 서류 준비중 | 서류 준비중 | 담당자 승인 / 본인 이용자 수정 시작 | 승인 대기에서 유효 결과 승인, 또는 보완 요청에서 수정 시작 |
| 준비 확인 요청 | 준비 확인 요청 | 본인 이용자 | 서류 준비중에 모든 항목의 준비함/아직을 선택하고 확인 요청 |
| 보완 요청 | 보완 요청 | 담당자 | 준비 확인 요청에서 승인 항목 1개 이상과 항목별 이유를 지정 |
| 준비 확인 완료 | 준비 확인 완료 | 담당자 | 확인 요청 상태, 현재 버전 일치, 미해결 보완·확인 필요 없음, 모두 준비함. 끝 상태 |
| 취소 완료 | 취소 완료 | 본인 이용자 | 진행 중 6개 상태에서 취소 확인. 끝 상태 |

- 취소·반려 경로로 가는 상태: 진행 중 6개 상태에서 취소 완료로, 담당자 승인 대기에서 준비중으로 반려. 보완은 준비 확인 요청 → 보완 요청 → 서류 준비중이다.
- LLM이 상태를 **직접 바꾸지 않고**, 사람이나 규칙이 최종 결정하는 곳: 점검은 시스템이 담당자 승인 대기까지만 전이한다. 승인·반려·보완 판정·완료는 담당자가, 취소·체크·수정 시작·확인 요청은 본인 이용자가 요청하고 서버가 권한·상태를 검증한다.
- 끝 상태인 준비 확인 완료·취소 완료에서 수정·첨부·재점검·재승인·취소로 되돌리는 경로는 없다.

## LLM에 보내지 않을 정보

| 모델 | 필드 | 보내지 않는 이유 |
| --- | --- | --- |
| PreparationCase·모의 계정 | owner_id, 계정 ID·이메일 | 분석에 불필요한 계정 정보 |
| PreparationCase·추후 Attachment | 식별정보가 있는 상황·추출 텍스트, PDF 원본 바이너리 | 기존 제안서·03 문서의 전송 금지 대상. 실제 서류는 사용하지 않음 |
| CaseHistory | reason, actor_id | 반려 사유에 식별정보가 섞일 수 있고 처리자 ID는 분석에 불필요 |
| 내부 모델 | 내부 PK·FK·점검 작업 식별자 | 내부 연결과 권한은 서버에서 관리. 근거 기준 ID·버전의 허용 범위와 구분 |

오늘 반려 서버에는 LLM 호출 경로가 없다. 이후 US-02를 연결할 때에도 반려 사유를 입력에 넣지 않는다.

## 시드(예시) 데이터

실제 민원·검토 이력이 아닌 **개발용 모의 사례 5건**이다. support_type은 F-6-1, 표시 언어는 실행 시 주입한다. 계정은 demo-user-1·demo-user-2·demo-officer이며 실제 사용자와 관계없다.

| # | 모델 | 값 (필드=값) | 용도 (어느 스토리·화면) |
| --- | --- | --- | --- |
| 1 | PreparationCase | id=1001, owner_id=demo-user-1, situation=체류기간 연장을 위해 준비한 서류를 확인하고 싶습니다., status=담당자 승인 대기 | US-04 반려 정상 사례, 소유자의 사유 조회 |
| 2 | PreparationCase | id=1002, owner_id=demo-user-2, situation=추가로 준비할 서류가 있는지 알고 싶습니다., status=담당자 승인 대기 | 다른 이용자가 상세·사유를 조회하면 403 |
| 3 | PreparationCase | id=1003, owner_id=demo-user-1, situation=준비 목록을 다시 확인하고 싶습니다., status=준비중 | 승인 대기 외 상태의 반려 거절 |
| 4 | PreparationCase | id=1004, owner_id=demo-user-1, situation=모의 항목 준비가 끝난 사례입니다., status=준비 확인 완료 | 끝 상태의 반려 거절. 실제 허가 완료가 아님 |
| 5 | PreparationCase | id=1005, owner_id=demo-user-1, situation=준비를 중단한 모의 사례입니다., status=취소 완료 | 취소된 건의 반려 거절 |

1001·1002에는 비공개 시험용 CheckResult를 함께 넣으며, criterion_versions는 빈 배열이다. 공식 출처나 실제 분석을 꾸며 넣지 않는다. CaseHistory는 처음에는 비어 있고 반려 성공 시 생성한다. 시드 재실행은 기존 건을 덮어쓰지 않는다.

## 아직 정하지 못한 것

| 항목 | 누가 언제 정하나 |
| --- | --- |
| 첫 기능 범위·완성 기준과 공유 API 약속 반영 | PM·테스트 담당·개발자2와 합류 시. 사용자 선택은 US-04이며 first-feature.md·API.md는 아직 빈 양식 |
| 표시 언어와 화면 배치 | 개발자2·팀이 DESIGN.md에서 합류 시 결정. 반려 API 자체는 번역·언어 선택을 구현하지 않음 |
| 전체 데이터 설계와 PRD v1.0 연결 | 팀이 문서 대조 후 확정하고 PM이 PRD에 반영 |
| 서버 의존성·폴더 구성의 공통 환경 반영 | 테크리더가 backend의 새 구성안을 검토한 뒤 반영 |
| 실제 자료·PDF·이력 보관·삭제 정책 | 팀·클라이언트가 실제 자료 처리 전에 결정. 이번 모의 반려 기능에서는 삭제 기능을 추가하지 않음 |
