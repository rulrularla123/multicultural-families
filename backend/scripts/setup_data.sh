#!/usr/bin/env bash
# 법령 DB 준비: 마이그레이션 → data/laws 적재(조문·관계 그래프) → (키가 있으면) 베트남어 요약·임베딩
# 사용: cd backend && docker compose up -d db && ./scripts/setup_data.sh
# 법령 원문을 새로 받으려면 먼저: .venv/bin/python -m ingest fetch
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

echo "▶ DB 마이그레이션"
.venv/bin/alembic upgrade head

echo "▶ 법령 적재·관계 그래프"
$PY -m ingest load

if [ "${LLM_FAKE:-false}" != "true" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "▶ 조문별 베트남어 요약 + 임베딩 (OpenAI API 사용)"
  $PY -m ingest summarize --lang vi
else
  echo "⚠ OPENAI_API_KEY가 환경변수에 없거나 LLM_FAKE=true라 요약·임베딩을 건너뜀"
  echo "  가짜 임베딩으로 벡터 검색 경로만 확인하려면: LLM_FAKE=true $PY -m ingest embed"
fi
echo "✓ 완료"
