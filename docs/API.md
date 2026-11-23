# API 약속 (화면과 서버가 주고받는 것)

- 작성일: 2026-11-09
- 근거: [백로그](requirements/backlog.md), [DATA-MODEL](DATA-MODEL.md)
- 경로 앞부분은 모두 `/api/v1`이다.

## 공통 규칙

| 항목 | 내용 |
| --- | --- |
| 서버 주소 | 로컬 `http://127.0.0.1:8000`. 화면은 `http://localhost:5173` |
| 익명 ID | 화면이 처음 열릴 때 UUID를 만들어 브라우저에 저장하고, 본인 분석 건 요청에 `X-Client-Id` 헤더로 보낸다(8~64자). 헤더가 없거나 길이가 맞지 않으면 400. 채팅은 `analysis_id`를 보낼 때 헤더가 필요하다 |
| 언어 | 요청 본문 또는 쿼리의 `lang`: `vi`(기본) · `ko`. 답변·분석 문구가 이 언어로 나온다. 조문 원문은 항상 한국어 |
| 응답 형식 | JSON. 질문 스트리밍만 SSE(`text/event-stream`) |
| 오류 형식 | `{"detail": "사용자에게 보여 줄 문구"}`. 입력 오류(422)는 `{"detail": [{"loc", "msg"}]}` |
| 상태 코드 | 400 익명 ID 없음, 404 없음(다른 익명 ID의 건 포함), 409 지금 상태에서 할 수 없음, 413 파일이 너무 큼, 415 지원하지 않는 파일, 422 입력 오류, 502 LLM 오류 |
| 시간 | UTC 오프셋이 붙은 ISO 8601. 화면에서 한국 시각으로 표시 |

## 1. 질문 답변 (F-01 / US-01)

| 항목 | 내용 |
| --- | --- |
| 요청 | `POST /api/v1/chat/stream` JSON `{message, lang?, history?, session_id?, analysis_id?, as_of?}` (`message` 1~1,000자, `history` 최대 20개 `{role, content}`). `analysis_id`는 본인 서류에 대한 후속 질문, `as_of`는 기준일 |
| 응답 | SSE `stage`(`{stage, label}`) → `delta`(`{text}`)… → 선택적 `reset`(`{}`, 기존 임시 답변 지움) → `answer`(최종 JSON). 오류는 `error`(`{message}`). 근거·검증 결과는 `answer`에 포함 |
| 근거 항목 | `{index, provision_id, quote_ko, quote_translation, translation_status, translation_provider, verified, verify_error}`. `verified=false`면 화면에 "원문 확인 필요" |
| 동기 버전 | `POST /api/v1/chat` 같은 입력, 응답 `AnswerPayload`(아래 필드) (테스트·디버그용) |
| 실패 | 422 입력 형식·길이 오류·공백만 있는 질문. 서류 후속 질문은 헤더 없음 400, 본인 건 아님 404. 스트림 시작 뒤 오류는 HTTP 상태 대신 SSE `error`로 전달 |

근거 항목에는 `version_warning`(`outdated`·`unchecked`·`null`)도 붙는다. `outdated`는 인용한 법령보다 새로운 판이 이미 시행 중이라는 뜻으로, `needs_expert=true`와 상담 안내 `notice`를 붙인다. `unchecked`는 최신 판 확인을 못 했거나 확인한 지 `LAW_VERSION_MAX_AGE_DAYS`(기본 7일)가 지났다는 뜻으로, 공식 원문 대조 안내 `notice`를 붙인다. 서류 분석 결과의 인용(`result.clauses[].citations`, `result.cautions[].citations`)도 같은 필드와 안내를 쓴다.

`AnswerPayload`: `{kind, lang, as_of, answer, citations, confidence, needs_expert, follow_up_questions, notice, disclaimer, sources, search_queries, number_checks, analysis_id, usage}`. `confidence`는 `high`·`medium`·`low`이며, `sources`는 `{provision_id, document_id, title, path, retrieved_by}` 목록이다. `number_checks`에 숫자 검증 결과가 포함된다.

현재 질문·이전 대화·서류 후속 질문 맥락의 식별정보 패턴은 질의 재작성·검색·답변 생성 전에 마스킹한다. 본문 인용 번호와 근거 목록의 연결이 누락되거나 모호하면 한 번 재생성한다. 그래도 연결하지 못하면 해당 법적 주장 대신 근거 확인 실패 안내를 반환한다(`confidence=low`, `needs_expert=true`).

법령 인용 번역은 검증된 `quote_ko`를 NMT API로 번역한 결과다. `translation_status`는 `translated`·`original`·`unavailable`·`not_verified`·`development`이며 실제 API 제공자는 `azure_translator`다. 키 미설정·번역 실패 시 `quote_translation`은 빈 문자열이다. `verified`는 한국어 원문 검증이며 번역 정확도 보증이 아니다. 서류 분석의 인용도 같은 번역 필드를 포함한다. [번역 기준](decisions/law-translation-2026-11-17.md).

## 2. 조문 보기 (F-02 / US-02)

| 요청 | 응답 |
| --- | --- |
| `GET /api/v1/provisions?id={provision_id}` | `{id, document_id, document_title, doc_type, level, number_label, path, full_text_ko, summary_vi, summary_ko, summary_translation_status, summary_translation_provider, effective, effective_from, effective_to, status, source_url, reviewed, reviewed_by, reviewed_at, law_mst, issued_date, promulgation_no, version_url, official_url, loaded_at, version_status, version_checked_at, version_checked_source, upcoming_effective_from, version_warning}`. `version_url`은 적재한 판의 국가법령정보센터 원문, `official_url`은 지금 시행 중인 판의 해당 조 링크 |
| `GET /api/v1/provisions/related?id={provision_id}` | `[{provision_id, path, rel, direction, evidence}]`. 수집 관계는 `REFERENCES`(참조)·`GUIDES`(시행령·규칙 → 법률), 방향은 `outgoing`·`incoming` |
| `GET /api/v1/search?q=...&lang=vi&rewrite=true` (선택: `as_of`) | `{queries_ko, domains, as_of, results: [{provision_id, path, score, source}]}`. 검색 디버그용 |

실패: 404 없는 조문.

## 3. 서류 분석 (F-03~F-07 / US-03~US-06)

| 요청 | 하는 일 | 응답 | 상태 |
| --- | --- | --- | --- |
| `POST /api/v1/documents` JSON `{text, format, file_size, page_count, lang}` | 추출 텍스트를 다시 마스킹하고 서류 파악·질문 생성 | 201 `Analysis` | (시작) → `uploaded` → `questions` |
| `GET /api/v1/documents` | 내 분석 건 목록 (최신순) | `[{id, created_at, filename, status, title, doc_type_label}]` | 없음 |
| `GET /api/v1/documents/{id}` | 상세 | `Analysis` | 없음 |
| `POST /api/v1/documents/{id}/answers` JSON `{answers: [{question_id, option_id?, text?}]}` | 답변 저장, 분석 시작 | 202 `Analysis` | `questions`·`failed` → `analyzing` |
| `POST /api/v1/documents/{id}/checklist` JSON `{index, done}` | 다음 행동 체크 | 200 `Analysis` | `review` ↔ `done` |
| `POST /api/v1/documents/{id}/cancel` | 취소 | 200 `Analysis` | 진행 중 → `canceled` |
| `DELETE /api/v1/documents/{id}` | 삭제 | 204 | 건 삭제 |

`Analysis` 응답: `{id, created_at, updated_at, lang, filename, file_size, page_count, status, stage, intake, facts, answers, result, checklist, error, masked_count, title, doc_type_label}`. 원본 파일과 `job_id`는 돌려주지 않는다.

- `intake`: `{doc_kind, doc_type_label, title, summary, basic_info, questions: [{id, text, why, options: [{id, label}], allow_free_text, terms: [{term, meaning}]}]}`. `terms`는 질문·선택지에 나온 어려운 말 0~2개의 쉬운 풀이다(이전 분석 건에는 없을 수 있음). 질문은 모두 답해야 하며, 선택지 중 하나를 `option_id`로 고르거나 `allow_free_text`가 참이면 `text`로 답할 수 있다
- `result`: `{summary, summary_simple, situation_note, clauses: [{id, title, text, pages, category(must_check·caution·general), explanation_simple, explanation_detail, highlights, citations}], cautions: [{title, kind(risk·missing·deadline·ambiguity·outdated), explanation_simple, explanation_detail, clause_ids, citations}], next_actions: [{id, text, clause_id, due}], open_questions, confidence, needs_expert}`
- `result`에는 추가로 `title`, `doc_type_label`, `doc_kind`, `basic_info`, `counts`, `notice`, `not_immigration`, `disclaimer`, `as_of`, `law_sources`가 포함된다. `open_questions`는 `{id, question, why}` 목록이며, 조항의 `id`와 다음 행동의 `clause_id`가 연결된다.
- `facts`는 현재 상세 응답에 포함되지만 별도 수정 API는 없다. UI 기능 추가를 이번 문서 변경에서 확정하지 않는다.
- 분석은 백그라운드로 돈다. 화면은 `GET /documents/{id}`를 2초마다 불러 `status`·`stage`를 본다.

브라우저가 최대 10MB의 PDF·DOCX에서 글자를 읽고 번호를 가린다. `text`는 최대 80,000자이며, 쪽 경계는 폼피드(`\f`)로 표시한다. `format`은 `pdf` 또는 `docx`이며 원본 파일과 이름은 보내지 않는다.

실패
- 업로드: 415 지원하지 않는 형식 또는 JSON이 아닌 요청, 413 크기 제한 초과, 422 글자 추출 실패 또는 잘못된 요청
- 답변: 422 필수 질문 빠짐 (`{detail, missing_question_ids}`), 409 상태가 맞지 않음
- 체크리스트: 422 없는 번호, 409 `review`·`done`이 아님
- 취소: `uploaded`·`questions`·`analyzing`·`review`에서만 가능. `failed`·`done`·`canceled`는 409

## 4. 상태 확인

`/health`는 `/api/v1` 접두어 없이 호출한다.

| 요청 | 응답 |
| --- | --- |
| `GET /health` | `{status, documents, provisions, chunks, embedded, llm_fake, laws_outdated, laws_unchecked, laws_checked_at}`. `laws_outdated`는 새 판이 시행 중인 법령 수, `laws_unchecked`는 확인 못 했거나 확인이 오래된 법령 수, `laws_checked_at`은 가장 오래된 확인 시각. `law_sync`는 자동 동기화 `{enabled, interval_hours, last_run_at, changed, reloaded, still_outdated, embedded, reindexed, pending_reindex, llm_skipped, error}`(서버 프로세스별, 재시작하면 비워짐) |
