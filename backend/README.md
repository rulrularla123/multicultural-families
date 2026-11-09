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
- 실제 답변: 환경변수 `OPENAI_API_KEY`를 넣고 `LLM_FAKE`를 끈 뒤 `python -m ingest summarize --lang vi`로 요약·임베딩을 만든다.
- 법령 원문 새로 받기: `python -m ingest fetch` (legalize-kr, 오늘 시행 중인 판을 고른다)
- 시연용 서류: `data/demo/*.docx` (가상 안내문). 다시 만들기: `python scripts/make_demo_docs.py`

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
