# US-02·03·05·07 서버 계약 전달안

- 작성: 김민건 / 2026-11-09, main `1e51283` 기준 후속 구현. PR 직전 최신 main `f409241` 병합 후 재검증.
- 사용자 확정: 모국어는 베트남어(vi), 번역문은 담당자가 확인한다.
- 코드: `app/workflow.py`, `app/routers/case_workflow.py`. 기존 case_detail router에 연결되어 main.py 수정 없이 등록된다.
- 기존 US-01 생성 API·언어 선택·test_creation.py·공식 인수 테스트는 변경하지 않는다. 이 문서는 PM이 API.md에 옮길 구현 전달안이며 팀 합의 기록이 아니다.

## 공통

기존 X-Demo-Account를 사용한다. 미인증 401, 권한 없음 403, 없는 건 404, 상태·버전 충돌 409, 잘못된 입력 422. 후속 API의 오류는 기존 FastAPI `{detail: ...}` 형식이며 detail은 문자열 또는 아래 명시한 객체다. 원래 US-01 입력 오류 `{ok:false, errors:[{field,reason}]}`는 유지한다. 시간은 UTC 오프셋이 있는 ISO 8601이며 기준 ID는 문자열이다. 수정 요청은 모두 POST로 두어 현재 CORS 허용 방식도 유지한다.

## 1. 자동 점검

`POST /cases/{id}/check`, 본문 없음, 해당 이용자만. 담당자 로그인 없이 동작한다. 생성 이후 화면·호출자가 이 요청을 보내며 서버가 생성 시 자동 예약하거나 영속 작업 큐에 등록하는 기능은 이번 범위가 아니다.

상황·PDF를 읽어 추출·식별정보 검사 후 적용 기준을 확인한다. 통과하면 준비중 → 자동 점검중, LLM 호출 뒤 담당자 승인 대기로 바뀐다. DB 잠금은 LLM 호출 전에 해제한다. 기본은 외부 통신 없는 MockTransport다. 공유 설정 담당은 `app.state.check_transport`에 기존 GeminiTransport를 명시 주입할 수 있고, 키·모델을 자동 선택하지 않는다.

성공 200: `{case_id, status:"담당자 승인 대기", discarded:false, message:"담당자 검토 중"}`. 분석 본문과 실패 원문은 이용자에게 반환하지 않는다. 늦은 결과는 `{case_id, status:현재상태, discarded:true}`로 반환하고 저장하지 않는다.

추출·식별정보 실패는 422와 위치·수정 안내를 반환하고 준비중을 유지한다. 식별정보 값 자체는 반환하지 않는다. 기준 없음·미검증 기준은 409이며 LLM을 호출하지 않는다. LLM 오류·60초 시간 초과·형식 오류는 실패 코드와 자동 점검 실패 이력을 저장한 뒤 담당자 승인 대기로 보낸다.

공통 기준은 office=NULL, 관서 기준은 건의 office와 같은 기준만 적용한다. 적용 대상 중 미검증 기준이 있으면 관서 확인 필요로 중단한다. 관서 미선택이면 공통만 적용하며 추가 관서 요구를 지어내지 않는다.

## 2. 담당자 결과 조회

`GET /cases/{id}/check-result`, 담당자만 200. 이용자는 본인도 403.

필드: case_id, result_id, status, analysis_items, reviewed_items, failure_reason, review_reason, situation_version, document_version, criterion_versions, can_approve. 결과는 현재 작업·버전과 일치해야 한다.

항목: id, kind(cautions/possible_omissions/additional_documents), text, criterion_id, source, checked_on, needs_confirmation. 근거 누락·요청에 없는 ID·응답의 식별정보 패턴은 확인 필요다. 출처·확인일은 등록 기준에서 붙인다.

## 3. 담당자 수정·번역 확인

`POST /cases/{id}/review`, 담당자만. 승인 대기 상태의 현재 result_id가 필요하다.

```json
{
  "result_id": 123,
  "reason": "근거와 수정·삭제·실패 해소 사유",
  "translation_confirmed": true,
  "items": [{
    "id": "item-1",
    "kind": "additional_documents",
    "text": "담당자가 검토한 한국어 항목",
    "criterion_id": "7",
    "translated_text": "담당자가 확인한 베트남어 번역문"
  }]
}
```

최종 항목 전체를 보낸다. 항목 1~100개, ID 중복 금지. 등록된 적용 기준의 ID·비어 있지 않은 사유·각 항목의 베트남어 번역·translation_confirmed=true가 필수다. 빈 목록·미확인 번역·근거 없는 항목은 422다. 한국어·번역에 식별정보 패턴을 넣지 않는다. display_language는 vi로 저장한다.

원본 분석·원본 실패 코드는 보존하고 reviewed_items를 별도로 저장한다. 담당자·시간·근거 버전·최종 항목·삭제 항목 ID·실패 해소 사유를 이력에 남겨 삭제만으로 미해결 문제를 숨길 수 없게 한다. 검토 저장 자체로 상태는 바뀌지 않는다.

## 4. 승인

`POST /cases/{id}/approve`, `{result_id:123}`, 담당자만.

미해결 실패·확인 필요·미확인 베트남어 번역·버전 불일치가 있으면 409. 통과하면 서류 준비중으로 바꾸고 승인자·UTC 일시·적용 기준 버전·수정된 공개 항목을 CaseApproval에 보존한다. PreparationItem은 prepared=NULL로 만든다. 상태·승인·항목·이력은 같은 트랜잭션이다.

200: `{case_id, approval_id, status, approved_at, bilingual_ready:true}`. 임의의 LLM 응답만으로 이 경로에 진입하지 않는다.

## 5. 승인 결과·준비 항목 조회

`GET /cases/{id}/approved-result`, 소유자·담당자만. 승인 전 또는 취소 건은 409, 다른 이용자는 403.

200: case_id, approval_id, status, display_language(vi), bilingual_ready, items(승인된 한국어·베트남어·출처·확인일), preparation_items, not_prepared_count, approved_at, completion_notice.

preparation_items: id, item_key, text, translated_text, criterion_id, prepared(NULL/false/true), needs_confirmation, supplement_reason, supplement_resolved. 승인 전 초안·검토 사유·담당자 계정은 공개하지 않는다. 진행 중 승인 결과의 버전이 바뀌면 공개·체크·확인 요청·완료를 거절한다. 완료된 건은 당시 승인 스냅샷과 완료 안내를 읽기 전용으로 조회한다.

## 6. 준비 체크

`POST /cases/{id}/preparation-items`, 해당 이용자·서류 준비중만.

```json
{"items":[{"id":321,"prepared":true},{"id":322,"prepared":false}]}
```

일부 항목만 저장해도 된다. true=준비함, false=아직. NULL·문자열·숫자 대체는 422다. 중복 ID·다른 승인/건의 항목은 전체 거절하며 일부만 저장하지 않는다. 체크 변경으로 보완 해소 상태를 임의로 바꾸지 않는다.

## 7. 확인 요청

`POST /cases/{id}/request-confirmation`, 본문 없음, 해당 이용자·서류 준비중만.

미선택 항목은 409 detail `{message, unselected_item_ids}`. false 항목이 있어도 요청할 수 있다. 승인 버전을 검사한 뒤 준비 확인 요청으로 바꾸고 요청 시간을 이력에 기록한다.

200: `{case_id, status, requested_at, not_prepared_count}`.

## 8. 완료

`POST /cases/{id}/complete`, 담당자·준비 확인 요청만.

```json
{"notice_translation":"담당자가 확인한 베트남어 완료 안내 문구", "translation_confirmed":true}
```

현재 입력·기준 버전 일치, 미해결 보완·확인 필요 없음, 모든 항목 준비함을 검사한다. 위반 시 409 detail `{reasons:[...]}`이며 상태를 바꾸지 않는다. 베트남어 완료 안내 확인도 필수다.

200: `{case_id, status:"준비 확인 완료", completed_at, notice_ko:"민원 접수나 체류기간 연장 허가가 아닙니다", notice_translation, bilingual_ready:true}`. 완료 안내 두 언어는 이력에 보존되며 승인 결과 재조회에서도 읽을 수 있다. 완료·취소 상태에서 새 점검·검토·승인·체크·확인 요청·완료는 거절한다.

## 다른 담당에게 전달할 연결점

- 이주환: Criterion 모델의 body/source/checked_on/version/is_verified/is_active/office를 사용해 F-02 API·공통 기준 시드를 작성. 기준 변경은 version을 올리고 진행 중 작업·승인 무효화 및 재점검을 연결한다. US-06은 PreparationItem.supplement_reason/supplement_resolved와 prepared를 함께 관리한다. 점검 저장과 경합하는 변경은 준비 건 → 기준 순서로 잠그며 여러 건은 ID 오름차순으로 처리한다.
- 권길현: API.md에 후속 계약 반영, 입력 변경은 situation_version/document_version과 current_check_task_id를 갱신해 이전 작업 폐기. 기존 취소 reason=""는 그대로 호환하며 NULL로 바꿀 필요는 없다. 최신 main f409241에 취소 router 등록이 반영되어 이번 브랜치에서도 사용한다.
- 여철준: 새 API에 화면 연결, can_approve로 승인 버튼 제어, 승인 전 결과 비공개, 승인 결과의 한국어·베트남어 동시 표시. 생성 언어 선택은 이번 변경 범위 밖이다.
- 김태후: 새 US-02·03·05·07 공식 인수 테스트 추가. 기존 acceptance 파일·기대값은 변경하지 않았다.

## 실행·검증

기존 backend/README.md의 전용 MySQL·DEMO_MODE 설정을 사용한다. 새 DB는 메타데이터로 테이블을 만들고 기존 DB는 backend에서 `DEMO_MODE=1 .venv/bin/python -m app.database`를 명시 실행한다. 새 테이블과 office/reviewed_items/review_reason을 추가하며 기존 데이터를 지우지 않는다. MySQL DDL은 자동 커밋이므로 일반 요청과 구분한다.

2026-11-09 일회용 MySQL 8.4에서 `TEST_DATABASE_URL=전용_mysql_test_DB .venv/bin/python -m pytest tests common_tests -q`로 기존 인수 테스트와 새 경계 테스트 최신 main f409241의 새 인수 테스트까지 포함해 총 270개·하위 점검 11개 통과. 이전 main 기준 검증은 258개였다. 동시 점검/승인, 이력 저장 실패 롤백, 취소·상황·서류·기준·작업 ID 변경 뒤 늦은 결과 폐기, 과거 승인 원문 비공개, 완료 안내 재조회, 기존 DB 컬럼 추가·재실행을 확인했다. pip check와 git diff --check도 통과했다. 기존 TestClient의 httpx 지원 폐기 예정 경고 1건이 있다.

주환님의 LLM 모듈과 단위 테스트는 원본 커밋 300c079에서 변경 없이 가져왔다. #80이 main 밖에 병합되어 생긴 의존성을 연결하기 위한 재사용이다. 실제 Gemini 통신·키 연결, 영속 작업 큐·서버 재시작 복구, 새 화면 연결, 팀원 5명 개별 실행을 검증한 기록은 아니다. 새 점검은 API 요청으로 시작하며 생성 API의 자동 시작·언어 선택을 이번 작업에서 추가하지 않았다.

## PR 직전 업무 배정 변경

최신 main의 CODE-STYLE은 US-05·07 담당을 김태후로 변경하고 checking.py·approval.py 등 스토리별 경로를 제시한다. 이번 구현은 그 변경 전 사용자가 요청한 US-02·03·05·07 범위를 완성한 코드이며 US-05·07은 김태후에게 인계할 구현으로 포함한다. 현재 case_workflow.py에 후속 router를 모아 기존 case_detail router에서 등록했다. 공유 코드 담당·스토리 담당은 후속 개별 파일 연결 시 이 등록을 함께 정리해 같은 경로를 중복 등록하지 않아야 한다. 이 문서가 새 담당 배정을 바꾸는 것은 아니다.
