# 김민건 작업 환경 실행 확인

- 실행일: 2026-11-09. 기준 main b8ee1fe.
- 환경: macOS 15.5, Python 3.11.9(backend/.venv), Node v22.19.0, npm 10.9.3, Docker MySQL 8.4, 실제 Google Chrome.
- 실행 주체: 사용자 요청에 따른 Codex의 CLI·브라우저 자동화. 학생 본인의 수동 확인이나 다른 팀원의 실행을 대신 완료 처리하지 않는다.

## DB와 서버

현재 셸에 DATABASE_URL·TEST_DATABASE_URL이 설정되어 있지 않았다. 실제 비밀 값 파일은 읽지 않았다. 용도를 알 수 없는 다른 프로젝트 DB를 선택하지 않고 127.0.0.1에만 연결한 전용 run_confirmation_test 데이터베이스로 실행했다.

루트에서 아래 명령을 전용 DB 연결 환경과 함께 실제 실행했다.

```sh
DEMO_MODE=1 PYTHONPATH=backend backend/.venv/bin/python -m app.database
```

스키마 생성·준비와 두 번째 재실행 모두 성공, 출력은 `준비 건 스키마 준비 완료. 추가 변경 없음.`이었다. 새 전용 DB라 추가 ALTER가 필요하지 않았다. 기존 action 컬럼이 없는 DB의 추가·데이터 보존·재실행은 아래 테스트 안에서 별도로 검증했다. 이는 연결 정보가 없는 기존 개발 DB를 직접 업데이트했다는 뜻은 아니다.

실제 서버: backend에서 `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, DEMO_MODE=1·전용 DB 환경. 실제 화면: frontend에서 Vite를 `--host 127.0.0.1 --port 5173 --strictPort`로 실행했다. 모의 공통 기준과 글자를 추출할 수 있는 모의 PDF만 사용했고 Gemini는 기본 모의 Transport였다.

## 실행 결과

| 검사 | 결과 |
| --- | --- |
| 루트 `backend/.venv/bin/python -m pytest -c backend/pytest.ini backend/tests backend/common_tests -q --tb=short` (TEST_DATABASE_URL=전용 DB) | 345 passed, 11 subtests passed, 기존 TestClient httpx 폐기 예정 경고 1건 |
| `backend/.venv/bin/python -m pip check` | No broken requirements found. |
| frontend `npm run build` | 성공 |
| frontend `npm run lint` | 성공 |
| 실제 Chrome·FastAPI·MySQL 화면 실행 | 아래 정상·거절 경로 성공, pageerror 없음 |

## 화면에서 확인한 것

1. 언어 미선택 제출은 422와 언어 선택 안내. vi를 고르면 생성 201·목록 반영.
2. 이용자 상세에서 자동 점검 시작 → PDF 추출·등록 기준 대조 → 담당자 승인 대기. 이용자 상세에 초안은 공개되지 않았다.
3. 담당자가 한국어·베트남어·근거·처리 사유를 확인하고 검토 저장. 저장 후 수정하면 승인 버튼이 비활성, 재저장 뒤 승인 가능.
4. 승인 뒤 이용자 화면에서 한국어·베트남어·출처·확인일 동시 표시.
5. 준비 항목 미선택 확인 요청은 화면에서 거절. 준비함 선택 → 체크 저장 → 확인 요청 → 준비 확인 요청 상태.
6. 담당자 완료 화면에서 베트남어 안내 미확인 시 완료 버튼 비활성. 안내 입력·확인 → 완료 200.
7. 이용자에게 완료 안내 두 언어와 끝 상태 읽기 전용 안내 표시. 상태는 준비 확인 완료.
8. 추가 API 검사: 승인 전 점검 결과 요청·다른 이용자의 승인 결과 요청은 403. 기준 변경 후 완료된 건은 재점검 대상에서 제외되고 당시 승인 스냅샷 조회는 200.

전체 5명 실행, 실제 Gemini·실제 공식 자료, 번역문의 언어적 정확성을 검증한 기록은 아니다. 실행을 마친 뒤 이번 검증용 서버·화면·DB는 종료해 기존 포트와 환경을 비워 둔다.
