# 백엔드 (FastAPI · PostgreSQL + pgvector)

한국 출입국·체류 법령(출입국관리법, 재한외국인처우기본법, 다문화가족지원법, 국적법과 각 시행령·시행규칙)을 조문 단위로 적재하고,
하이브리드 검색(BM25 + 벡터)과 조문 관계 그래프로 근거를 찾아 베트남어·한국어로 답한다. 인용은 원문과 코드로 대조한다.

## 실행 방법

Python 3.12, Docker가 필요하다.

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
docker compose up -d db                 # localhost:5433
.venv/bin/alembic upgrade head
.venv/bin/python -m ingest load         # data/laws → 조문·청크·관계 그래프
LLM_FAKE=true .venv/bin/uvicorn app.main:app --reload --port 8000
```

- `LLM_FAKE=true`: OpenAI 없이 고정 응답으로 화면 흐름만 확인한다. 답변에 `[DEV FAKE RESPONSE]`가 붙는다.
- 실제 답변: 서버 환경변수 `OPENAI_API_KEY`를 설정하고 `LLM_FAKE`를 끈다. 법령 번역에는 별도로 `AZURE_TRANSLATOR_KEY`가 필요하다. 기존 `ingest summarize --lang vi`는 한국어 요약(OpenAI) → 베트남어 번역(Azure Translator NMT) → 임베딩 순서다. 실제 번역 API 호출·품질은 운영 설정 후 별도 확인해야 한다.
- 법령 원문 새로 받기: `python -m ingest fetch` (legalize-kr, 오늘 시행 중인 판을 고른다)
- 최신 판 확인: `python -m ingest versions` — 적재한 판(법령MST)이 지금 시행 중인 판인지 확인해 DB에 저장한다. 결과는 조문 화면·답변 근거·`/health`에 보인다. `LAW_GO_KR_OC`(국가법령정보센터 Open API 인증값)가 있으면 법제처 공식 현행 판과, 없으면 legalize-kr과 비교한다. `--strict`는 새 판이 시행 중이거나 확인하지 못한 법령이 있으면 종료 코드 1을 낸다.
- 최신 판 동기화: `python -m ingest sync` — 위 확인을 한 뒤 새 판이 시행 중인 법령만 legalize-kr에서 받아 재적재하고, 그 법령의 쉬운 요약(원래 있던 언어만)과 임베딩을 새로 만든 다음 다시 확인한다. 바뀌지 않은 법령의 청크·임베딩은 건드리지 않는다. `--dry-run`은 확인만 한다. `LLM_FAKE=true`면 재적재까지만 하고 요약·임베딩은 대기(`needs_reindex`)로 남겨, 실제 키로 다음에 실행할 때 채운다.
- 자동 동기화: 서버(uvicorn)가 켜져 있으면 `LAW_SYNC_INTERVAL_HOURS`(기본 24)시간마다 위 `sync`를 스스로 실행한다. 10분마다 때가 됐는지 보고, 마지막 확인이 주기보다 오래됐을 때만 돈다(서버를 다시 켜도 바로 다시 돌지 않음). 요약·임베딩 대기 법령이 있고 실제 LLM이 켜져 있으면 주기와 관계없이 채운다. 실패하면 1시간 뒤 다시 시도한다. 끄려면 `LAW_SYNC_INTERVAL_HOURS=0`. 마지막 결과는 `/health`의 `law_sync`에 보인다. 자동 동기화가 `data/laws` 파일을 새 판으로 덮어쓸 수 있으므로 `git status`에 법령 파일 변경이 보이면 새 판이 들어온 것이다.
- 시연용 서류: `data/demo/*.docx` (가상 안내문). 다시 만들기: `python scripts/make_demo_docs.py`

### 법령 번역 설정

- Azure에서 **Translator 단일 서비스 리소스**를 만들고 가격 책정 계층을 **F0(무료)**로 선택한다. F0는 매 이용 월 200만 자를 제공하며, 한도 소진 시 번역이 중단된다. 앱이 요금제를 조회·변경하지 않으므로 리소스가 F0인지 Azure 포털에서 확인해야 한다.
- 서버에만 `AZURE_TRANSLATOR_KEY`를 설정한다. 지역 리소스는 `AZURE_TRANSLATOR_REGION`도 설정하고, global 리소스는 생략한다. 키 값은 브라우저·로그·저장소에 넣지 않으며 HTTP 헤더로만 전송한다.
- `TRANSLATION_TIMEOUT_SECONDS`는 요청별 제한 시간이며 기본 10초다. `LLM_FAKE=true`에서는 외부 번역 API도 호출하지 않고 `[DEV FAKE TRANSLATION]`으로 구분한다.
- 질문 답변·서류 분석의 법령 인용은 한국어 원문 검증 후 Azure 표준 NMT API로 번역한다. 키 미설정·무료 한도 초과·번역 실패 시 원문은 유지하고 번역 불가를 표시한다. 다른 유료 번역 API나 LLM 번역으로 자동 전환하지 않는다. 답변·분석 설명은 여전히 LLM이 생성한다.
- 조문 요약의 기존 LLM 베트남어 청크는 재사용하지 않는다. 번역 키 설정 후 기존 `summarize --lang vi` 작업으로 NMT 요약·임베딩을 생성해야 한다. 생성 전에도 한국어 조문으로 검색할 수 있다.
- 번역 API 비용은 기존 OpenAI `usage_log` 집계에 포함되지 않는다. [번역 처리·이전 기준](../docs/decisions/law-translation-2026-11-17.md)을 참고한다.

### 프론트엔드

위 백엔드를 `http://127.0.0.1:8000`에 띄운 상태에서 실행한다. Node.js가 필요하다.

```bash
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

- 화면은 `http://127.0.0.1:8000/api/v1`을 호출한다 (`frontend/src/api/client.ts`). 백엔드 CORS는 `http://localhost:5173`·`http://127.0.0.1:5173`만 허용한다(`app/core/config.py`의 `cors_origins`).
- `npm run build`(타입 체크 + 빌드), `npm run lint`(oxlint)로 확인한다.
- Claude Code 세션에서는 저장소 루트의 `.claude/launch.json`에 등록된 `frontend-dev` 설정으로 미리보기 브라우저에서 바로 열 수 있다.

## 테스트

```bash
.venv/bin/python -m pytest -q                    # DB 없이 도는 단위 테스트
TEST_DB=1 .venv/bin/python -m pytest -q          # 위 DB 적재 후 API 전체 흐름까지
```

## 구조

| 폴더 | 내용 |
| --- | --- |
| `ingest/` | 법령 수집(fetch)·파싱(편·장·절·조·항·호·목)·참조 추출·관계 그래프·청크·요약·임베딩 |
| `app/retrieval/` | 질의 재작성, BM25·벡터 검색(RRF), 그래프 확장 |
| `app/generation/` | 답변 생성(구조화 출력), 인용 검증, 숫자 검증 |
| `app/documents/` | 서류 추출(PDF·DOCX), 조항 분할, 서류 파악·질문, 분석 |
| `app/services/` | 채팅·서류 분석 상태 처리 |
| `app/api/v1/` | `/api/v1/chat`, `/documents`, `/provisions`, `/search` |
