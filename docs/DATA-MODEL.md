# 데이터 구조

- 작성일: 2026-11-09
- DB: PostgreSQL 16+ + pgvector, 문자 인코딩 UTF-8. 스키마 변경은 Alembic 마이그레이션으로만 한다.
- 근거: [PRD 6·7절](PRD.md), [백로그](requirements/backlog.md)

## 1. 법령

| 모델 (테이블) | 필드 | 설명 | 기능 |
| --- | --- | --- | --- |
| LegalDocument (`legal_documents`) | `id` TEXT PK | 법령 ID. 법제처 법령 ID 또는 `출입국관리법` 같은 고유 이름 | F-08 |
| | `doc_type` TEXT | `law`(법률) · `decree`(시행령) · `rule`(시행규칙) · `guide`(안내 매뉴얼) | F-02, F-08 |
| | `title_ko` TEXT, `title_vi` TEXT NULL | 법령명, 베트남어 법령명 | F-02 |
| | `issuer` TEXT NULL, `issued_date` DATE NULL | 소관 부처, 공포일 | F-02 |
| | `effective_from` DATE NULL, `effective_to` DATE NULL | 시행일, 폐지일 (NULL이면 현행) | F-01, F-02 |
| | `source_url` TEXT NULL, `raw_hash` TEXT NULL | 원문 출처, 원문 해시(같은 내용 재적재 감지) | F-08 |
| | `is_sample` BOOL | 테스트용 샘플 법령. 검색에서 뺀다 | F-08 |
| DocumentRelation (`document_relations`) | `src_doc`, `dst_doc`, `rel` (PK) | 법령 사이 관계: `DELEGATES`(법률→시행령·시행규칙), `AMENDS`, `REPLACES` | F-02 |
| Provision (`provisions`) | `id` TEXT PK | 조문 노드 ID. 예: `출입국관리법:J25:H1` (제25조 제1항) | F-01, F-02 |
| | `document_id` FK, `parent_id` TEXT NULL, `jo_id` TEXT | 소속 법령, 상위 노드, 소속 조 | F-02 |
| | `level` TEXT | `pyeon`(편) · `jang`(장) · `jeol`(절) · `jo`(조) · `hang`(항) · `ho`(호) · `mok`(목) | F-02 |
| | `number` TEXT, `heading` TEXT NULL | 번호(제25조의2 같은 가지번호 포함), 조 제목 | F-02 |
| | `text_ko` TEXT, `full_text_ko` TEXT | 노드 자신의 본문, 하위 항·호를 포함한 전체 | F-01, F-02 |
| | `path` TEXT, `ordinal` INT | 표시 경로(제3장 > 제25조), 순서 | F-02 |
| | `effective_from`, `effective_to` DATE NULL | 조문 단위 시행·폐지일 | F-01 |
| Chunk (`chunks`) | `id` PK, `provision_id` FK, `jo_id`, `document_id` | 검색 단위 | F-01 |
| | `kind` TEXT, `lang` TEXT | `original`(원문) · `summary`(쉬운 요약), `ko` · `vi` | F-01 |
| | `content` TEXT, `tokens` TEXT NULL | 내용, 한국어 토큰화 결과 | F-01 |
| | `tsv` TSVECTOR (계산 열) | 전문 검색 | F-01 |
| | `embedding` VECTOR(1536) NULL | 임베딩 | F-01 |
| ProvisionEdge (`provision_edges`) | `src_id`, `dst_id`, `rel` (PK) | 조문 사이 관계: `REFERENCES`(참조), `DELEGATES`(위임), `AMENDS`, `REPEALS` | F-01, F-02 |
| | `evidence` TEXT, `method` TEXT, `confidence` FLOAT | 근거 문구, `rule`·`llm`·`manual`, 확신도 | F-02 |
| UnresolvedReference (`unresolved_references`) | `src_id`, `evidence`, `reason` | 해석하지 못한 참조. 대상 법령을 추가 적재할 때 본다 | F-08 |

## 2. 서류 분석 건 (핵심 대상)

| 모델 (테이블) | 필드 | 설명 | 기능 |
| --- | --- | --- | --- |
| Analysis (`analyses`) | `id` UUID PK | 분석 건 ID | F-03~F-07 |
| | `client_id` TEXT, 인덱스 | 브라우저 익명 ID. 다른 ID의 건은 보이지 않는다 | F-07 |
| | `created_at`, `updated_at` TIMESTAMPTZ | 올린 일시, 바뀐 일시 | F-07 |
| | `lang` TEXT | 결과 언어 `vi` · `ko` | F-09 |
| | `filename`, `mime` TEXT, `file_size` INT, `page_count` INT NULL | 파일 정보. 원본 파일은 저장하지 않는다 | F-03 |
| | `text` TEXT | 마스킹한 추출 텍스트. 쪽 경계는 폼피드(`\f`) | F-03, F-05 |
| | `masked_count` INT | 마스킹한 식별정보 개수 (값은 저장하지 않음) | F-03 |
| | `status` TEXT | 아래 상태값 | 전체 |
| | `stage` TEXT NULL | 분석중 세부 단계 (추출·검색·분석·검증) | F-05 |
| | `job_id` TEXT NULL | 현재 분석 작업 ID. 취소·재시도 뒤 늦게 온 결과를 버리는 데 쓴다 | F-05, F-07 |
| | `intake` JSONB NULL | 서류 종류, 한 줄 요약, 개인 상황 질문 목록 | F-04 |
| | `answers` JSONB NULL | 질문 답변 | F-04 |
| | `result` JSONB NULL | 분석 결과 (요약, 조항 분류, 주의점, 다음 행동, 추가 질문, 확신도, 전문가 상담 필요) | F-05 |
| | `checklist` JSONB NULL | 다음 행동별 체크 여부 `[{index, done}]` | F-06 |
| | `error` TEXT NULL | 분석 실패 이유 (사용자에게 보여 줄 문구) | F-05 |
| UsageLog (`usage_log`) | `id`, `created_at`, `kind`, `model`, `input_tokens`, `output_tokens` | LLM 사용량 기록 (비용 확인용) | 전체 |

### 상태값 (`analyses.status`)

| 상태값 | 화면 표시 | 누가 바꾸나 | 언제 |
| --- | --- | --- | --- |
| `uploaded` | 업로드됨 | 서버 | 유효한 파일을 받아 추출·마스킹을 끝냄 |
| `questions` | 질문 대기 | 서버 | 서류 종류·요약·개인화 질문 생성 완료 |
| `analyzing` | 분석중 | 사용자 요청 → 서버 | 필수 질문에 모두 답하고 분석 시작 |
| `failed` | 분석 실패 | 서버 | LLM 오류·시간 초과·형식 오류. 다시 시도하면 `analyzing` |
| `review` | 결과 확인 | 서버 | 분석 결과 저장 (인용 검증 포함) |
| `done` | 완료 | 사용자 | 체크리스트를 모두 체크. 하나라도 풀면 `review` |
| `canceled` | 취소됨 | 사용자 | `uploaded`·`questions`·`analyzing`·`review`에서 취소. 끝 상태 |

- 분석 결과를 저장할 때 `job_id`가 지금 작업과 같고 상태가 `analyzing`일 때만 저장한다. 취소·재시도 뒤 도착한 결과는 버린다.
- `done`·`canceled`에서는 분석 시작·재시도가 거절된다(409). 삭제는 언제든 된다.

## 3. LLM에 보내지 않는 정보

| 데이터 | 이유 |
| --- | --- |
| 식별정보 패턴(외국인등록번호, 주민등록번호, 여권번호, 휴대전화번호) | 추출 직후 마스킹해서 저장하고, 마스킹한 텍스트만 보낸다 |
| 원본 파일 | 저장하지도 보내지도 않는다 |
| `client_id`, 분석 건 ID, `job_id` | 분석에 필요 없다 |

## 4. 시드·샘플 데이터

| 데이터 | 용도 |
| --- | --- |
| 샘플 법령 2건 (`is_sample=true`) | 테스트. 검색에서 빠진다 |
| 샘플 서류 2건 (`backend/data/demo/`) | US-09 체험, 데모. 가상 문서이며 실제 개인정보 없음 |
