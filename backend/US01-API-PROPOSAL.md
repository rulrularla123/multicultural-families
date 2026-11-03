# US-01 서버 구현안·API 전달 내용

- 작성·수정: 김민건 / 2026-11-03
- 상태: 사용자가 별도 협의 대기를 생략하고 1단계 US-01을 구현하도록 지시해 아래 기술 선택으로 구현했다. 실제 팀 합의·승인 기록으로 대신하지 않는다.
- 기준: [US-01 인수 조건](../docs/requirements/backlog.md#us-01-상황-설명과-서류로-준비-건-만들기), 최신 업무 배분. 표시 언어·자동 점검·PDF 추출은 이번 범위에서 제외한다.

## 1. 구현한 요청·응답

기존 민건 담당 `routers/case_detail.py`에 생성·목록을 추가해 공유 main.py 등록 변경과 새 router 파일명 합의가 필요 없도록 했다. 공통 dependencies.py의 get_actor를 그대로 재사용한다.

| 항목 | 구현 |
| --- | --- |
| 생성 | POST /cases, multipart/form-data |
| 입력 | support_type=F-6-1, situation=원문 문자열, files=동일 키로 반복한 PDF 1~5개 |
| 모의 계정 | X-Demo-Account: demo-user-1 또는 demo-user-2. 담당자·미인증 계정으로 생성하지 못함 |
| 성공 | 201, ok=true와 case 객체. case에는 id·support_type·status·owner_id·created_at(UTC ISO 8601) |
| 입력 거절 | 422, ok=false와 errors 배열. 각 항목은 field·reason |
| 목록 | GET /cases, 200, 본인 준비 건 요약 배열. 생성 일시 내림차순·동일 시각이면 ID 내림차순 |
| 권한 거절 | 계정 없음·알 수 없는 계정 401, 담당자의 생성·본인 목록 요청 403. 기존 detail 오류 형식 유지 |
| 소유자 | 요청에서 owner_id를 받지 않고 인증된 모의 계정에서 결정. 목록의 owner_id 쿼리로 타인 건 조회 불가 |
| 표시 언어 | 입력에서 제외, DB에는 NULL. 기존 상세 응답도 NULL 허용 |

생성 요청 예시(backend 서버가 실행된 상태):

```sh
curl -X POST http://127.0.0.1:8000/cases \
  -H 'X-Demo-Account: demo-user-1' \
  -F 'support_type=F-6-1' \
  -F 'situation=모의 서류로 체류 연장 준비를 확인합니다.' \
  -F 'files=@mock.pdf;type=application/pdf'
curl http://127.0.0.1:8000/cases -H 'X-Demo-Account: demo-user-1'
```

성공 응답 형식(예시 값):

```json
{"ok":true,"case":{"id":1006,"support_type":"F-6-1","status":"준비중","owner_id":"demo-user-1","created_at":"2026-11-03T04:00:00+00:00"}}
```

입력 거절 형식:

```json
{"ok":false,"errors":[{"field":"files","reason":"PDF 파일을 1~5개 선택하세요."}]}
```

현재 frontend의 CaseInput·CreateCaseResult·FieldError를 가능한 한 그대로 연결하도록 한 형식이다. 사용자의 추가 위임으로 화면 어댑터를 실제 요청으로 교체했다. 401·403의 detail과 네트워크 실패는 화면 오류로 표시한다. 실제 API.md 반영은 PM에게 전달할 사항이며 이 작업에서 공유 문서를 덮어쓰지 않았다.

## 2. 이번에 정한 기술 처리

- 상황 설명: 원문의 Unicode 코드 포인트 수로 1~1,000자를 검사한다. 공백·줄바꿈도 수에 포함하고, 공백만 있는 값은 별도로 거절한다. 원문을 잘라 저장하지 않는다. 화면도 같은 기준으로 셀 때는 Array.from(situation).length를 사용해야 한다.
- PDF: 확장자 대소문자를 구분하지 않고 .pdf인지와 바이트 시작이 %PDF-인지 모두 검사한다. MIME 선언만 믿지 않는다. 각 10,485,760바이트 이하, 파일 1~5개. 파일명은 메타데이터 컬럼에 맞춰 255자 이하로 제한한다.
- PDF 원본: Attachment.file_data LONGBLOB에 비공개 저장한다. 원본을 파일명 경로에 쓰지 않고, 목록·상세 응답과 LLM에 넣지 않는다. 추출 텍스트는 NULL이며 이번에 추출하지 않는다. 기존 메타데이터 전용 행과의 호환을 위해 DB 필드는 NULL을 허용하지만 생성 API는 유효한 원본을 반드시 함께 저장한다.
- 원자성: 파일 전부를 검사한 뒤 준비 건과 첨부를 같은 트랜잭션으로 저장한다. 한 파일이라도 거절되거나 첨부 저장이 실패하면 준비 건을 포함해 남기지 않는다.
- 미지원 입력: owner_id·status·display_language 등 허용하지 않은 필드나 중복 지원 유형·상황 입력은 거절한다.
- 표시 언어: 임의의 모국어·빈 문자열·test-language를 넣지 않는다. 이번 US-01 생성 건은 NULL이며 번역·언어 선택은 후속 범위다.
- 기존 DB: `python -m app.database`로 필요한 새 테이블을 만들고, display_language의 NULL 허용과 file_data 추가만 명시적으로 적용한다. 기존 값은 유지하고 재실행할 수 있다. MySQL DDL은 자동 커밋되므로 일반 요청 트랜잭션과 구분한다.
- 의존성: 업로드 파서 python-multipart 0.0.33 한 항목을 requirements에 추가했다. 실행 가능한 서버를 제공하기 위한 필수 변경이며 공통 환경 검토 때 테크리더에게 전달한다.

## 3. 작업 범위와 거른 것

- 변경: models.py·schemas.py·database.py·기존 담당 router·DATA-MODEL·자체 점검·서버 전달 문서. multipart 의존성 한 항목 추가. 추가 위임 후 frontend의 실제 API 어댑터·모의 이용자 선택·입력 오류·목록 갱신도 반영.
- 유지: main.py·dependencies.py·반려 router·기존 반려 테스트 기대값·공유 API·인수 조건·타인 acceptance 폴더.
- 제외: 자동 점검 시작·PDF 텍스트 추출·LLM 호출·기준 등록·승인·취소 API, 표시 언어 선택, 화면 코드 수정.
- 이 구현은 1단계 US-01 서버다. 이후 US-02·03·05·07까지 진행한 것이 아니다.

## 4. 검증 기록

- 구현 전 생성 요청이 404로 실패하는 것을 확인한 후 구현했다.
- 기존 스키마의 필수 언어 컬럼·첨부 메타데이터를 재현해 명시적 업데이트와 데이터 보존·재실행을 검증했다.
- 실제 일회용 MySQL 8.4.8에서 기존 반려·첨부·생성·목록·스키마 업데이트 테스트 총 81개 통과.
- 실제 Uvicorn HTTP: multipart 생성 201, 본인 목록·상세 200, 타인 목록 비노출, 잘못된 PDF 422, 미인증 401, 담당자 목록 403 확인.
- pip check 통과. TestClient의 httpx 지원 폐기 예정 경고 1건은 기존과 같다.
- 팀원 5명 실행·공식 acceptance를 수행한 기록은 아니다. US-01 화면의 임시 응답은 추가 위임 후 실제 요청으로 교체했다.

## 5. 실제 화면 연동 검증 (2026-11-03)

- 사용자가 화면 담당자의 위임을 전달해 US-01 화면도 이번에 연결했다. 기존 디자인과 컴포넌트를 유지했다.
- frontend/src/api/cases.ts의 메모리 mock 대신 fetch·FormData와 X-Demo-Account를 사용한다. mockCases.ts는 삭제했다.
- 모의 이용자 선택, 생성 후 목록 갱신, 공백 포함 코드 포인트 수 표시, 입력 오류·통신 오류·재시도·작성 취소를 연결했다. 계정 변경 시 이전 목록을 즉시 숨기고 이전 요청을 취소한다.
- npm run build·npm run lint 통과.
- 실제 Chrome에서 생성 → MySQL 목록 반영 → 새로고침 후 유지, 이용자별 분리, 입력·PDF 오류, 이모지 1,000자, 통신 실패 후 재시도와 작성 취소를 확인했다. 브라우저 스크립트 오류는 없었다.
- 일회용 DB·서버·브라우저로 확인했으며 5명 개별 실행이나 반려 화면 구현을 대신하지 않는다.

## PR 직전 최신 main 회귀 (2026-11-03)

main 069c889의 취소·식별정보 검사 변경을 fast-forward로 반영했다. 전용 MySQL에서 전체 121개 테스트가 통과했고 기존 TestClient 폐기 예정 경고 1건만 남았다. 이전 81개 결과는 해당 시점의 기록으로 유지한다. 이번 검증용 DB는 종료·제거했다.
