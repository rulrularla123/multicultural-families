# API 약속 (화면과 서버가 주고받는 것)

- 작성일: 2026-11-09
- 근거: [백로그](requirements/backlog.md), [DATA-MODEL](DATA-MODEL.md)
- 경로 앞부분은 모두 `/api/v1`이다.

## 공통 규칙

| 항목 | 내용 |
| --- | --- |
| 서버 주소 | 로컬 `http://127.0.0.1:8000`. 화면은 `http://localhost:5173` |
| 익명 ID | 화면이 처음 열릴 때 UUID를 만들어 브라우저에 저장하고, 모든 요청에 `X-Client-Id` 헤더로 보낸다. 서류 분석 API는 이 헤더가 없으면 400 |
| 언어 | 요청 본문 또는 쿼리의 `lang`: `vi`(기본) · `ko`. 답변·분석 문구가 이 언어로 나온다. 조문 원문은 항상 한국어 |
| 응답 형식 | JSON. 질문 스트리밍만 SSE(`text/event-stream`) |
| 오류 형식 | `{"detail": "사용자에게 보여 줄 문구"}`. 입력 오류(422)는 `{"detail": [{"loc", "msg"}]}` |
| 상태 코드 | 400 익명 ID 없음, 404 없음(다른 익명 ID의 건 포함), 409 지금 상태에서 할 수 없음, 413 파일이 너무 큼, 415 지원하지 않는 파일, 422 입력 오류, 502 LLM 오류 |
| 시간 | UTC 오프셋이 붙은 ISO 8601. 화면에서 한국 시각으로 표시 |

## 1. 질문 답변 (F-01 / US-01)

| 항목 | 내용 |
| --- | --- |
| 요청 | `POST /api/v1/chat/stream` JSON `{question, lang, history?}` (`question` 1~1,000자, `history`는 최근 대화 0~6개) |
| 응답 | SSE 이벤트 `delta`(답변 조각), `citations`(검증된 근거 목록), `done`(`{needs_expert, confidence}`), 오류는 `error`(`{detail}`) |
| 근거 항목 | `{provision_id, document_title, number_label, quote, effective, verified}`. `verified=false`면 화면에 "원문 확인 필요" |
| 동기 버전 | `POST /api/v1/chat` 같은 입력, 응답 `{answer, citations, needs_expert, confidence}` (테스트·디버그용) |
| 실패 | 422 빈 질문·1,000자 초과, 502 LLM 오류 |

## 2. 조문 보기 (F-02 / US-02)

| 요청 | 응답 |
| --- | --- |
| `GET /api/v1/provisions?id={provision_id}&lang=vi` | `{id, document_id, document_title, doc_type, level, number_label, heading, path, full_text_ko, summary, effective, effective_from, effective_to}` |
| `GET /api/v1/provisions/related?id={provision_id}` | `[{id, rel, direction, number_label, document_title, heading}]` (`rel`: REFERENCES·DELEGATES·AMENDS·REPEALS) |
| `GET /api/v1/search?q=...&limit=10` | 조문 검색 결과 `[{provision_id, number_label, document_title, snippet, score}]` |

실패: 404 없는 조문.

## 3. 서류 분석 (F-03~F-07 / US-03~US-06)

| 요청 | 하는 일 | 응답 | 상태 |
| --- | --- | --- | --- |
| `POST /api/v1/documents` multipart `file`, `lang` | 업로드, 추출, 마스킹, 서류 파악, 질문 생성 | 201 `Analysis` | (시작) → `uploaded` → `questions` |
| `GET /api/v1/documents` | 내 분석 건 목록 (최신순) | `[{id, created_at, filename, status, title, doc_type_label}]` | 없음 |
| `GET /api/v1/documents/{id}` | 상세 | `Analysis` | 없음 |
| `POST /api/v1/documents/{id}/answers` JSON `{answers: [{question_id, option_id?, text?}]}` | 답변 저장, 분석 시작 | 202 `Analysis` | `questions`·`failed` → `analyzing` |
| `POST /api/v1/documents/{id}/checklist` JSON `{index, done}` | 다음 행동 체크 | 200 `Analysis` | `review` ↔ `done` |
| `POST /api/v1/documents/{id}/cancel` | 취소 | 200 `Analysis` | 진행 중 → `canceled` |
| `DELETE /api/v1/documents/{id}` | 삭제 | 204 | 건 삭제 |
| `GET /api/v1/documents/samples` | 샘플 서류 목록 (US-09) | `[{id, title, description}]` | 없음 |
| `POST /api/v1/documents/samples/{sample_id}` | 샘플로 분석 건 만들기 | 201 `Analysis` | → `questions` |

`Analysis` 응답: `{id, created_at, lang, filename, page_count, status, stage, intake, answers, result, checklist, error, masked_count}`. 원본 파일과 `job_id`는 돌려주지 않는다.

- `intake`: `{doc_type_label, title, summary, questions: [{id, text, why, options: [{id, label}], allow_free_text}]}`. 질문은 모두 답해야 하며, 선택지 중 하나를 `option_id`로 고르거나 `allow_free_text`가 참이면 `text`로 답할 수 있다
- `result`: `{summary, summary_simple, situation_note, clauses: [{clause_id, title, category(must_check·caution·general), explanation_simple, explanation_detail, highlights, citations}], cautions: [{title, kind(risk·missing·deadline·ambiguity·outdated), explanation_simple, explanation_detail, clause_ids, citations}], next_actions: [{text, clause_id, due}], open_questions, confidence, needs_expert}`
- 분석은 백그라운드로 돈다. 화면은 `GET /documents/{id}`를 2초마다 불러 `status`·`stage`를 본다.

실패
- 업로드: 415 PDF·DOCX 아님, 413 10MB 초과, 422 글자 추출 실패(스캔·이미지 PDF)
- 답변: 422 필수 질문 빠짐 (`{detail, missing_question_ids}`), 409 상태가 맞지 않음
- 체크리스트: 422 없는 번호, 409 `review`·`done`이 아님
- 취소: 409 `done`·`canceled`

## 4. 상태 확인

| 요청 | 응답 |
| --- | --- |
| `GET /health` | `{status, documents, provisions, chunks, embedded, llm_fake}` |
