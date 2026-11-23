# 법령 번역 처리 기준 — 2026-11-17

## 반영한 피드백과 범위

“법령 정보는 LLM에 맡기기보다 번역 API를 이용하는 것이 좋다”는 피드백에 따라, 법령 인용문과 조문 요약의 번역을 설명 생성에서 분리한다.

| 대상 | 처리 |
| --- | --- |
| 법령 한국어 원문·시행 정보·공식 링크 | 수집·저장한 원문을 사용하고 코드로 인용 검증 |
| 질문 답변·서류 분석의 법령 인용 번역 | 검증된 한국어 인용만 Azure Translator NMT API로 번역 |
| 조문별 베트남어 쉬운 요약 | LLM 한국어 요약 → Azure Translator NMT API 번역 |
| 질문 답변·서류 분석의 설명·개인화 질문 | LLM 유지. 법령 원문 번역과 구분 |

조문 전체 번역이나 답변 전체의 한국어 생성 후 번역은 이번 범위에 포함하지 않는다. 번역 API 도입만으로 법령 해석·최신성·요약·번역 품질이 검증되는 것은 아니다.

## 번역 제공자와 설정

- 추가 요청인 “무료 범위에서만 사용”에 맞춰 Azure Translator **F0 단일 서비스 리소스**를 선택한다. F0는 매 이용 월 200만 자를 제공하며 한도에 도달하면 요청을 중단한다. 다음 이용 월에 다시 사용할 수 있다. 유료 요금제로 직접 변경하지 않는다.
- Azure 표준 REST v3 API에서 `from=ko`, `to=vi`, `textType=plain`, `category=general`을 명시한다. 다른 제공자·번역 LLM·Foundry LLM 배포로 자동 전환하지 않는다.
- 서버 환경변수는 `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION`(지역 리소스일 때 필요, global이면 생략), `TRANSLATION_TIMEOUT_SECONDS`(기본 10초)다. 키 발급·F0 리소스 생성은 Azure 계정에서 필요하다. 앱은 리소스의 요금제를 조회하거나 변경하지 않으므로, F0 여부는 운영자가 포털에서 확인해야 한다. 코드 변경이 실제 계정 연결·무료 요금제 설정 완료를 의미하지 않는다.
- 키는 `Ocp-Apim-Subscription-Key`, 지역은 `Ocp-Apim-Subscription-Region` 헤더에 넣는다. 요청 URL·오류 본문·예외 세부 내용에 키를 남기지 않는다. 공개 법령 인용·한국어 조문 요약만 전송하며 사용자 질문·원본 파일·개인화 답변을 번역 API에 보내지 않는다.
- 이번 구현에서 사용자 정의 번역 모델·용어집은 사용하지 않는다. 법률 용어·부정·기한·금액·예외 표현은 실제 번역 결과로 별도 검토해야 한다.

공식 근거: [번역 REST 요청·응답](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/v3/translate), [인증 헤더](https://learn.microsoft.com/en-us/azure/ai-services/translator/text-translation/reference/authentication), [지원 언어](https://learn.microsoft.com/en-us/azure/ai-services/translator/language-support), [F0 요금표](https://azure.microsoft.com/en-us/pricing/details/translator/), [무료 한도 소진 시 중단](https://www.microsoft.com/en-us/translator/business/faq/).

## 응답·화면과 실패 처리

- LLM의 `Citation` 출력에서는 `quote_translation`을 제거한다. 검증·재생성·인용 정렬이 끝난 뒤 서버가 번역을 추가한다. 검증 실패 인용은 번역하지 않는다.
- 채팅과 서류 분석 인용은 `quote_translation`, `translation_status`, `translation_provider`를 반환한다. `verified`는 한국어 원문 확인 여부이며 번역 정확도 검증을 뜻하지 않는다.
- 상태는 `translated`(API 성공), `original`(한국어 요청, 원문 유지), `unavailable`(키 미설정·장애), `not_verified`(인용 검증 실패), `development`(개발용 대역)다. 실제 API 성공 제공자 값은 `azure_translator`다.
- 키 미설정·시간 초과·무료 한도 초과(403)·인증 오류(401)·요청 제한(429)·서버 오류·불완전한 응답은 빈 번역과 `unavailable`로 처리한다. 유료 서비스나 LLM 번역으로 대체하지 않는다. 화면에는 한국어 원문과 번역 불가 안내를 표시한다. 성공 번역에는 기계번역·참고용임을 표시한다.
- `LLM_FAKE=true`에서는 번역 API도 호출하지 않는다. `[DEV FAKE TRANSLATION]` 대역은 실제 번역으로 저장하지 않는다.
- 예전 서류 분석 결과의 출처 없는 번역은 조회 시 숨긴다. DB에 저장된 분석 원본을 덮어쓰지 않는다. 브라우저에 남아 있는 이전 채팅도 번역 상태가 없으면 번역문을 표시하지 않는다.

## 요약 적재·검색·캐시

- `ingest summarize --lang vi`는 번역 키부터 확인한 뒤, 없는 한국어 요약을 생성하고 해당 본문을 NMT로 번역한다. 경로·조문 ID는 번역 요청에 넣지 않는다. 성공한 묶음만 저장하며 실패한 묶음은 재시도할 수 있다.
- `chunks.kind=azure_translated_summary`, `lang=vi`로 새 요약을 저장한다. 기존 LLM `summary`·`vi`와 다른 제공자의 `translated_summary`는 삭제하지 않고 표시·검색·신규 임베딩 대상에서 제외한다. `kind`는 기존 TEXT 열이므로 DB 스키마 변경은 없다.
- 조문 보기의 `summary_vi`는 새 NMT 요약만 사용한다. `summary_translation_status`, `summary_translation_provider`로 상태·제공자를 알린다. 기존 한국어 원문·요약은 유지한다.
- 기존 설치에서는 번역 키 설정 후 요약·임베딩 작업이 필요하다. 이번 코드 수정으로 기존 DB의 번역이 자동 생성되지는 않는다.
- 인용 번역의 성공 결과는 원문 SHA-256 해시·대상 언어·번역 구현 버전별로 최대 1,024개를 프로세스 메모리에 캐시한다. 원문이 바뀌면 별도 요청하며, 실패는 캐시하지 않는다. 서버 재시작 시 초기화된다.
- 저장된 요약은 법령 원문 재적재 시 원문·청크와 함께 교체된다. 번역 모델·정책 변경 시에는 기존 번역 요약의 재생성 절차를 별도로 정해야 한다.
- 번역 API 과금은 OpenAI 토큰·비용 집계와 별도다. 이번 작업에서 실제 번역 비용·품질·시간 절감을 측정한 것은 아니다.

## 검증 범위

- 자동 테스트에서는 HTTP 대역으로 Azure 요청·응답, 지역 헤더, 무료 한도 초과·장애, 캐시, 실제 앱의 JSON·SSE 경로와 서류 분석, 한국어 요약 후 번역, 이전 번역 제외를 확인한다. PostgreSQL 적재·조회 테스트와 외부 번역 API의 실제 호출·품질 평가는 구분한다.
- Azure 계정·F0 리소스·키 연결, 실제 베트남어 법률 번역 품질, 브라우저 화면 검증·배포는 별도 확인이 필요하다. 실행 결과는 이 PR의 검증 기록을 따른다.

## 2026-11-17 검증 결과

- 최신 main(`e8cfd1c`)을 pull 받은 뒤 일회용 PostgreSQL 16 + pgvector에 마이그레이션·공개 법령을 적재하고 `TEST_DB=1`, `LLM_FAKE=true`로 전체 백엔드 테스트를 실행했다. **134개 통과**했다. 기존 서비스 DB는 사용하지 않았다.
- 번역 테스트 25개가 Azure 요청·응답·지역 인증 헤더, 키 미설정, 무료 한도 초과(403)·인증 오류(401)·요청 제한(429)·서버 오류·시간 초과, 잘못된 대상 언어·불완전 응답, 캐시, JSON·SSE 경로, 서류 분석·요약 적재·조문 조회를 확인한다. 번역 HTTP 응답은 대역을 사용했다.
- `ruff check app ingest tests scripts`, 프론트엔드 `npm run build`, `npm run lint`, `git diff --check`, 변경 문서 7개의 상대 링크 확인을 통과했다. 프론트엔드 린트에는 수정 범위 밖의 기존 경고 4개가 남아 있다.
- PR 대상 파일만 반영한 별도 프론트엔드 사본에서도 빌드를 통과했다. 로컬의 별도 폰트·잠금 파일 변경이 성공 조건에 포함되지 않도록 확인했다.
- 실제 Azure 계정의 F0 설정과 유효 키·베트남어 번역 품질·배포 확인은 수행하지 않았다.
