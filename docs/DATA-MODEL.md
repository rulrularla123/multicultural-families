# 데이터 구조

- 대상 차시: 3주차 1일차 (수업일 2026-11-03)
- 작성일: 2026-11-02
- 수정일: 2026-11-09 (US-02·03·05·07 공유 모델·서버 연결)
- 작성: 김민건 / 개발자1 업무
- 상태: 기존 생성·목록·상세·반려 계약을 유지하고 점검·승인·체크·완료 모델과 담당 서버를 추가했다. 베트남어(vi)·담당자 번역 확인은 사용자 결정이다. 생성 화면의 언어 선택 추가는 별도 담당 작업이며 이번 변경에 포함하지 않는다.
- 근거: [PRD 6·7절](PRD.md#6-데이터-구조), [선정 주제 B 상태 흐름](domain/03-rules-states-llm.md#선정-주제-b의-상태-흐름), [백로그 US-01](requirements/backlog.md#us-01-상황-설명과-서류로-준비-건-만들기)·[US-04](requirements/backlog.md#us-04-담당자가-분석-결과를-반려하기).

## 모델과 필드

기존 US-01·04 모델에 **US-02 자동 점검, US-03 승인, US-05 체크·확인 요청, US-07 완료**를 연결한다. DB는 STACK의 MySQL, 문자열 인코딩은 utf8mb4다. 기준 등록·변경(F-02), 보완 처리(US-06), 입력 수정·재점검 API는 각각 담당자가 이 모델을 사용해 연결한다.

| 모델 | 필드 | 타입 | 필수 | 설명 | 연결된 기능 ID |
| --- | --- | --- | --- | --- | --- |
| PreparationCase (절차 준비 건) | id | BIGINT UNSIGNED, PK | 예 | 준비 건 ID. 시드에서는 고정 ID 사용 | F-01·F-04 |
| PreparationCase | owner_id | VARCHAR(64) | 예 | 모의 이용자 식별자. 담당자 역할은 서버가 별도 판단 | F-01·F-04 |
| PreparationCase | situation | TEXT | 예 | 생성 API의 원문 입력. 공백·줄바꿈을 포함한 Unicode 코드 포인트 1~1,000자. 공백만 입력하면 거절 | F-01·F-04 |
| PreparationCase | display_language | VARCHAR(32), NULL 허용 | 후속 선택 시 | US-01 입력에서 제외하고 NULL 저장. 기존 시드 언어는 유지 | F-05 |
| PreparationCase | status | VARCHAR(32) | 예 | 생성 시 준비중, 아래 한글 상태값 8개만 허용 | F-01·F-04 |
| Attachment (첨부 서류) | id | BIGINT UNSIGNED, PK | 예 | 첨부 식별자. 서버 발급 | F-01 |
| Attachment | case_id | BIGINT UNSIGNED, FK | 예 | 소속 준비 건. 고아 첨부와 임의의 연쇄 삭제 방지 | F-01 |
| Attachment | filename | VARCHAR(255) | 예 | 원래 파일명. 저장 경로나 실제 파일 유효성을 보장하는 필드가 아님 | F-01 |
| Attachment | size_bytes | BIGINT UNSIGNED | 예 | 바이트 크기. DB에서 0~10,485,760 허용. PDF 형식 검사는 생성 API에서 별도 수행 | F-01 |
| Attachment | document_version | INTEGER UNSIGNED | 예 | 기본값 1, 1 이상. 해당 서류가 속한 준비 건의 서류 버전 | F-01·F-03 |
| CheckResult (점검 결과) | id | BIGINT UNSIGNED, PK | 예 | 점검 결과 ID. 비공개 점검 결과. LLM 실패 시 항목은 빈 배열 | F-03·F-04 |
| CheckResult | case_id | BIGINT UNSIGNED, FK | 예 | 소속 준비 건 | F-03·F-04 |
| CheckResult | analysis_items | JSON 배열 | 예 | 담당자용 원본 초안. 이용자 상세 응답에는 포함하지 않음 | F-03·F-04 |
| CheckResult | criterion_versions | JSON 배열 | 예 | 점검 당시 기준 ID·버전 스냅샷. 반려 이력에 보존 | F-02·F-04 |
| CheckResult | invalidated_at | DATETIME(6), NULL 허용 | 반려 시 | 반려 시 기록. 이전 초안을 현재 결과로 쓰지 않음 | F-04 |
| CaseHistory (처리 이력) | case_id | BIGINT UNSIGNED, FK | 예 | 소속 준비 건 | F-04·F-08 |
| CaseHistory | from_status | VARCHAR(32) | 예 | 반려 전 담당자 승인 대기 | F-04 |
| CaseHistory | to_status | VARCHAR(32) | 예 | 반려 후 준비중 | F-04 |
| CaseHistory | actor_id | VARCHAR(64) | 예 | 실제 권한 검사에 사용한 담당자 모의 계정 ID | F-04 |
| CaseHistory | reason | LONGTEXT | 예 | 반려 사유는 앞뒤 공백 제거 후 1자 이상 필수. 사유 없는 전이는 빈 문자열. 검토 수정·삭제·실패 해소는 근거·처리 사유를 JSON으로 기록하며 이용자에게 원문 공개하지 않음 | F-04 |

### 구현에 함께 필요한 기술 필드

| 모델 | 필드·타입 | 쓰는 이유 |
| --- | --- | --- |
| PreparationCase | support_type VARCHAR(16), situation_version·document_version INTEGER, current_check_task_id VARCHAR(64) NULL, created_at DATETIME(6) | F-6-1과 입력 버전 보존. 반려 시 현재 점검 작업 연결 해제. 진행 중 버전·점검 작업 불일치 시 응답 폐기. 입력 수정·재점검 API는 PM 담당 |
| Attachment | extracted_text LONGTEXT NULL, file_data LONGBLOB NULL (지연 로딩) | 생성 시 추출 텍스트는 NULL. 점검은 file_data에서 페이지별 텍스트를 읽고 검사한다. 생성 API는 원본을 file_data에 비공개 저장. 기존 메타데이터 행은 원본 NULL 허용. 목록·상세·LLM 입력에서 원본 제외 |
| CheckResult | situation_version·document_version INTEGER, task_id VARCHAR(64) NULL, failure_reason TEXT NULL | 점검 당시 정보와 실패 코드. 외부 호출 기본값은 모의 Transport이며 실제 Gemini 키·모델 주입은 공유 설정 담당 |
| CaseHistory | id BIGINT UNSIGNED PK, actor_role VARCHAR(16), occurred_at DATETIME(6), criterion_versions JSON 배열 | 이력 식별·처리자 역할·UTC 처리 시각·당시 기준 버전 보존 |

### US-02·03·05·07 추가 모델·필드

| 모델 | 필드·타입 | 설명 |
| --- | --- | --- |
| PreparationCase | office VARCHAR(128) NULL | NULL이면 공통 기준만 사용. 입력·관서 변경 API는 별도 담당 |
| Criterion | id BIGINT UNSIGNED PK, support_type VARCHAR(16), office VARCHAR(128) NULL | 기준 식별자·적용 절차. office=NULL은 공통, 값이 있으면 해당 관서 기준 |
| Criterion | body TEXT, source TEXT, checked_on DATE, version INTEGER UNSIGNED | 공식 본문·출처·확인일·1 이상 버전. 변경 담당은 버전을 올리고 재점검을 연결해야 함 |
| Criterion | is_verified BOOLEAN, is_active BOOLEAN | 기본 미검증·활성. 적용 대상 중 미검증 기준이 있으면 관서 확인 필요로 점검 거절. 공통 기준 1개 이상 필수 |
| CheckResult | reviewed_items JSON NULL, review_reason TEXT NULL | 담당자가 근거와 사유를 남겨 검토한 별도 항목. 원본 analysis_items·failure_reason을 덮어쓰지 않음 |
| CaseApproval | id PK, case_id FK, result_id FK | 준비 건과 점검 결과에 연결된 승인 스냅샷 |
| CaseApproval | situation_version·document_version INTEGER, criterion_versions JSON, items JSON | 승인 당시 입력·기준 버전과 담당자 수정 후 공개 내용. 이전 LLM 원문을 공개하지 않음 |
| CaseApproval | display_language VARCHAR(32) NULL, approved_by VARCHAR(64), approved_at DATETIME(6), invalidated_at DATETIME(6) NULL | 새 승인은 vi·담당자 확인 번역 필수. 승인자·UTC 일시 보존, 새 점검 시 무효화 |
| PreparationItem | id PK, case_id FK, approval_id FK, criterion_id FK, item_key VARCHAR(64) | 준비 건·승인·등록 기준의 실제 FK. item_key는 승인 항목 ID |
| PreparationItem | text TEXT, translated_text TEXT NULL, prepared BOOLEAN NULL | 승인된 한국어·베트남어 항목. NULL=미선택, false=아직, true=준비함 |
| PreparationItem | needs_confirmation BOOLEAN, supplement_reason TEXT NULL, supplement_resolved BOOLEAN | 확인 필요·보완 해소 상태. US-06 담당이 보완 사유와 미해결 상태를 함께 갱신하며 체크 저장만으로 해소하지 않음 |

기준 PK는 DB에서 정수이며 API·LLM의 criterion_id는 문자열로 전달한다. 기존 상태 8개는 추가·변경하지 않는다. 실제 기준 시드는 F-02 담당 범위이며 이번 테스트의 example.test 모의 기준을 공식 기준으로 등록하지 않는다.

## 관계

- PreparationCase 1개 → Attachment·CheckResult·CaseHistory·CaseApproval·PreparationItem 여러 개. CaseApproval은 CheckResult를, PreparationItem은 CaseApproval·Criterion을 FK로 참조한다. 임의의 연쇄 삭제는 설정하지 않는다.
- LLM 실행 중 DB 잠금을 유지하지 않는다. 저장 직전에 상태·현재 작업 ID·상황·서류·적용 기준 버전을 다시 검사한다. 변경되면 결과를 폐기하고 다른 작업이 정한 상태를 덮어쓰지 않는다.
- 승인·체크·확인 요청·완료는 준비 건 행을 잠그고 현재 버전과 권한을 검사한다. 완료된 건은 이후 기준이 바뀌어도 당시 승인 스냅샷과 완료 안내를 조회할 수 있으며 변경 API는 거절한다.
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
| PreparationCase·Attachment | 식별정보가 있는 상황·추출 텍스트, PDF 원본 바이너리 | 기존 제안서·03 문서의 전송 금지 대상. 실제 서류는 사용하지 않음 |
| CaseHistory | reason, actor_id | 반려 사유에 식별정보가 섞일 수 있고 처리자 ID는 분석에 불필요 |
| 내부 모델 | 내부 PK·FK·점검 작업 식별자 | 내부 연결과 권한은 서버에서 관리. 근거 기준 ID·버전의 허용 범위와 얼구분 |

US-02는 식별정보 검사를 통과한 상황·페이지 텍스트·지원 유형·등록 기준만 LLM에 전달한다. 반려 사유·파일명·계정·점검 작업 ID·PDF 원본은 전송하지 않는다. 실제 Gemini 호출 검증은 수행하지 않았으며 기본 연결은 모의 Transport다.

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
| 공유 API 문서·화면 연결 반영 | 기존 US-01·04 계약은 유지. 후속 [서버 계약 전달안](../backend/WORKFLOW-API.md)을 PM·화면·테스트 담당에게 전달. 팀 합의를 수행했다고 표시하지 않음 |
| 생성 시 표시 언어 선택 | 베트남어(vi), 번역문은 담당자 확인으로 사용자 결정. 생성 API·화면 언어 선택은 별도 담당 작업. 현재 생성 API는 유지하고 담당자 검토 시 vi와 확인된 번역문을 저장 |
| 원본·취소 건의 보관 기간 | 이번에는 원본을 비공개 DB에 보존하고 임의의 삭제 기능을 만들지 않음. 실제 자료 처리 전 정책은 클라이언트·팀이 결정 |
| 공통 환경·테스트 담당과 연결 | 기존 민건 담당 case_detail.py를 사용해 새 파일 등록은 불필요. 코드 포인트 길이·원문 보존 기준과 multipart 의존성을 PM·테크리더·테스트 담당에게 전달 |
| 실제 자료·PDF·이력 보관·삭제 정책 | 팀·클라이언트가 실제 자료 처리 전에 결정. 이번 모의 반려 기능에서는 삭제 기능을 추가하지 않음 |
