# 서버 연동 검토·인계 기록

- 검토자: 김민건 / 2026-11-09.
- 시작 기준: main 5198415. PR 94(API 문서)·95(기준 API)·96(검토 대기 목록)·97(점검·승인 화면)·98(기준 관리·자동 재점검)·99(보완)을 별도 임시 복사본에 합쳐 검증했다. PR 병합 여부와 이 검토용 통합 실행은 구분한다.
- 외부 Gemini는 호출하지 않고 기존 모의 Transport·가상 자료·일회용 MySQL 8.4를 사용했다. 실제 민원이나 팀원 실행 기록을 대신하지 않는다.

## 확인한 계약

1. 기준 등록 API의 숫자 ID를 서버 내부 FK로 사용하고, 점검·승인의 criterion_id는 문자열로 기록한다. 같은 ID의 version 증가와 현재 적용 기준 전체 대조가 맞는다. #98은 변경된 기준에 해당하는 진행 중 건을 무효화·재점검하고 완료·취소 건은 제외한다.
2. API 문서 #94의 8개 경로를 서버와 대조했다. 검토 저장·체크 저장의 성공 응답을 명시하고 완료 요청의 오류를 문자열 detail과 reasons 객체로 구분했다. LLM 실패는 HTTP 200이지만 담당자 승인 가능한 성공 분석을 뜻하지 않도록 문구를 정리했다.
3. #97의 실제 화면을 Chrome·FastAPI·MySQL로 연결해 생성 언어 미선택 422 → vi 생성 → PDF 추출·점검 → 담당자 번역 확인·검토 저장·승인 → 이용자 한국어·베트남어 동시 표시를 확인했다. 승인 전 결과 조회와 타인 승인 결과 조회는 403이었다.
4. #99와 기존 준비 체크·완료 서버를 연결해 확인 요청 → 보완 → 수정 시작 → 다시 체크·확인 요청 → 미해결 보완 완료 거절 → 담당자 해소 → 완료를 HTTP로 확인했다. 기준 변경 뒤 완료 건의 승인 스냅샷도 유지됐다.

## 발견·수정

- 기준 변경으로 준비중에 돌아간 이력이 실제 반려 사유로 표시됐다. 회귀 테스트 2개가 먼저 실패하는 것을 확인한 뒤 CaseHistory.action을 추가했다. 실제 반려는 rejection, 일반 전이는 transition으로 기록해 구분한다. 이전 action=NULL 반려 이력과 기존 DB 업데이트·재실행도 검사한다. 기존 데이터베이스는 서버 재실행 전에 backend에서 `DEMO_MODE=1 .venv/bin/python -m app.database`로 필드를 추가해야 한다.
- 검토 저장 후 한국어·번역문 등을 고쳐도 이전 저장본으로 승인할 수 있었다. #97에서 저장하지 않은 변경이 있으면 승인을 차단하고 재저장 후에만 활성화하도록 수정했다. 실제 Chrome에서 수정 전 활성 상태를 재현하고 수정 후 차단·재저장·승인을 확인했다. 새 검토 항목은 중복되지 않는 ID를 발급한다.
- 병합 충돌: #95·96은 main.py의 router 등록이, #97·99는 CaseDetailPanel.tsx의 점검·승인 결과·보완 영역이 겹친다. 어느 한쪽을 버리지 않고 모두 유지해야 한다. 검토용 통합본은 이렇게 정리했다.

## US-05·07 담당자에게 인계

실제 서버는 case_workflow.py에 등록되어 있다. 이후 파일을 나누면 기존 router 등록을 제거해 같은 경로를 이중 등록하지 않는다. 화면의 임시 응답 전환은 해당 담당자가 수행한다.

- 체크: `POST /cases/{id}/preparation-items`, `{items:[{id, prepared:true 또는 false}]}`. 소유자·서류 준비중만. 응답은 `{case_id,status,items}`. 임시 화면의 content/is_ready는 실제 text/prepared로 바꾼다. 미선택은 NULL이며 아직(false)과 구분한다.
- 확인 요청: 체크 저장 성공 뒤 `POST /cases/{id}/request-confirmation`(본문 없음). 미선택·버전 불일치는 409. 아직(false)이 있어도 접수한다. 준비 항목 조회는 `GET /cases/{id}/approved-result`의 preparation_items를 쓴다. 표시 시 not_prepared_count는 false 항목 수다.
- 완료: `POST /cases/{id}/complete`, `{notice_translation:담당자가 확인한 베트남어 문구,translation_confirmed:true}`. 담당자·확인 요청 상태만. 버전·미해결 보완·확인 필요·준비함 조건을 서버가 검사한다. 기본 문자열 detail과 `{reasons:[...]}` 모두 화면에 표시해야 한다.
- 보완: #99의 supplement_resolved를 그대로 사용한다. 이용자의 준비함 체크만으로 보완을 해소하지 않는다. 담당자의 resolve-supplements 뒤에만 완료할 수 있다.
- 완료 화면: 서버 notice_ko/notice_translation 또는 approved-result의 completion_notice를 사용한다. 기존 임시 화면의 베트남어 자리 표시 문구로 완성했다고 표시하지 않는다.
- 현재 main의 준비 체크·완료 화면은 임시 응답이며 App 연결도 아직 없다. 이번 확인은 해당 화면 전체 연동을 마쳤다는 뜻이 아니다.

## 실행 결과

- 시작 main의 회귀·이력 구분 수정: pytest tests common_tests → 278개·하위 점검 11개 통과.
- 검토용 통합본: 수정 전 341개, 수정 후 345개·하위 점검 11개 통과.
- 실제 Chrome 정상 흐름과 저장 전 승인 차단 검증 완료. 페이지 실행 오류 없음.
- 화면 build·lint 통과. 기존 TestClient의 httpx 폐기 예정 경고 1건 외 별도 테스트 경고 없음.
