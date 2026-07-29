> 기준: 특별상 과제 요구사항 + 외국인 개인 바이어/셀러 와이어프레임 반영 v1.4
> 
> 
> 적용 순서: `001_initial_schema.sql` → `002_marketplace_wireframe.sql` → `003_individual_buyer.sql` → `004_rag_challenge_alignment.sql` → `005_single_contract_review_agent.sql`(구현 예정)
> 

AI 중간 데이터와 역할별 분석은 `AI_UPSTAGE_ARCHITECTURE.md`, RAG 저장·검색·근거 연결은 `RAG_KNOWLEDGE_BASE.md`를 따른다.

## 1. 핵심 변경

와이어프레임은 기존의 “바이어가 계약을 작성해 셀러에게 전송”하는 구조보다 “셀러가 계약 가능한 공고를 게시하고 바이어가 선택”하는 구조에 가깝다. 따라서 다음 두 aggregate를 분리한다.

- `listings`: 셀러의 공개 상품/계약 공고. 같은 공고를 여러 바이어가 탐색한다.
- `contracts`: 특정 외국인 개인 바이어와 셀러 업체 사이의 실제 협상·서명 건.

단체 여행도 계약 당사자인 buyer는 개인이다. `buyer_group_name`과 `requested_people`은 여행 그룹의 문맥을 저장하며 별도 법인·organization을 만들지 않는다. MVP의 단체서명은 `group_representative` 개인 1명이 단체를 대표해 서명하는 방식이다.

공고에서 계약이 시작될 때 `listing_versions`와 `listing_clauses`를 `contract_versions`와 `contract_clauses`로 복사한다. 이후 공고를 수정해도 진행 중인 계약은 바뀌지 않는다.

특별상 과제 기준의 상품 분류와 지원 언어는 다음 값으로 고정한다.

| 구분 | DB 값 | 화면 표시 |
| --- | --- | --- |
| 상품 | `vehicle_rental` | 자동차 렌탈 |
| 상품 | `activity` | 액티비티 |
| 상품 | `tour` | 투어 |
| 상품 | `accommodation` | 숙박 |
| 언어 | `ko-KR` | 한국어 |
| 언어 | `en-US` | English |
| 언어 | `ja-JP` | 日本語 |
| 언어 | `zh-CN` | 简体中文 |

`contract_category`와 `supported_locale` enum을 API, AI schema, RAG metadata의 공통 source of truth로 사용한다.

AI 실행은 FastAPI 고정 workflow와 Solar Pro 3 단일 `contract_review` Agent를 결합한다. 파싱·추출·초안·요약·번역은 고정 task이며, 계약 위험 검토만 제한된 도구 호출 Agent로 기록한다.

## 2. ERD

```mermaid
erDiagram
    AUTH_USERS ||--|| PROFILES : extends
    AUTH_USERS ||--o{ ORGANIZATION_MEMBERS : joins
    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERS : has

    ORGANIZATIONS ||--o{ LISTINGS : publishes
    LISTINGS ||--|| LISTING_TERMS : has
    LISTINGS ||--o{ LISTING_VERSIONS : versions
    LISTING_VERSIONS ||--o{ LISTING_CLAUSES : contains
    LISTINGS ||--o{ PRICE_ESTIMATES : estimates

    LISTINGS ||--o{ CONTRACTS : instantiates
    AUTH_USERS ||--o{ CONTRACTS : individual_buyer
    ORGANIZATIONS ||--o{ CONTRACTS : seller
    CONTRACTS ||--|| CONTRACT_TERMS : has
    CONTRACTS ||--o{ CONTRACT_VERSIONS : versions
    CONTRACT_VERSIONS ||--o{ CONTRACT_CLAUSES : contains

    LISTINGS ||--o{ DOCUMENTS : owns
    CONTRACTS ||--o{ DOCUMENTS : owns
    DOCUMENTS ||--o{ AI_JOBS : processes
    LISTING_VERSIONS ||--o{ AI_ANALYSIS_RUNS : analyzed
    CONTRACT_VERSIONS ||--o{ AI_ANALYSIS_RUNS : analyzed
    AI_ANALYSIS_RUNS ||--o{ AI_FINDINGS : produces
    AI_FINDINGS ||--o{ RAG_EVIDENCE : cites
    KNOWLEDGE_BASES ||--o{ KNOWLEDGE_DOCUMENTS : contains
    KNOWLEDGE_DOCUMENTS ||--o{ KNOWLEDGE_DOCUMENT_VERSIONS : versions
    KNOWLEDGE_DOCUMENT_VERSIONS ||--o{ RAG_EVIDENCE : supports
    AI_ANALYSIS_RUNS ||--o{ RAG_RETRIEVAL_RUNS : searches
    RAG_RETRIEVAL_RUNS ||--o{ RAG_EVIDENCE : returns
    LISTING_VERSIONS ||--o{ LOCALIZED_CONTENTS : localizes
    CONTRACT_VERSIONS ||--o{ LOCALIZED_CONTENTS : localizes
    AI_FINDINGS ||--o{ LOCALIZED_CONTENTS : localizes

    CONTRACTS ||--o{ REVISION_REQUESTS : negotiates
    REVISION_REQUESTS ||--o{ REVISION_REQUEST_ITEMS : contains
    CONTRACTS ||--o{ SIGNATURE_REQUESTS : signs
    SIGNATURE_REQUESTS ||--o{ SIGNATURE_PARTICIPANTS : includes

    AUTH_USERS ||--o{ NOTIFICATIONS : receives
    CONTRACTS ||--o{ AUDIT_EVENTS : records
```

## 3. 사용자와 조직

### `profiles`

| 컬럼 | 의미 |
| --- | --- |
| `id` | `auth.users.id` |
| `username` | UI 표시/검색용 unique 별칭. 로그인은 이메일 사용 |
| `display_name`, `phone` | 담당자 기본 정보 |
| `country_code`, `locale` | 바이어 국가/화면 언어. locale은 `ko-KR/en-US/ja-JP/zh-CN` |
| `preferred_currency` | 예상 가격 표시 통화 |
| `default_group_name` | 선택적인 기본 여행 단체명 |
| `active_organization_id`, `active_business_role` | 현재 역할 컨텍스트 |

비밀번호와 password hash는 저장하지 않는다. 이메일·비밀번호 변경은 Supabase Auth가 담당한다.

### `organizations`

| 컬럼 | 의미 |
| --- | --- |
| `organization_type` | `buyer` 또는 `seller` |
| `verification_status` | `pending`, `verified`, `rejected` |
| `business_registration_no` | 셀러 검증 정보 |
| `rating_average`, `rating_count` | 상세 화면 표시용 집계값 |

바이어는 Supabase Auth 사용자와 `profiles`로 표현하며 buyer organization을 자동 생성하지 않는다. 단체명은 개인 profile 또는 특정 contract의 선택 정보일 뿐 별도 계약 당사자가 아니다.

`organizations`와 `organization_members`는 MVP에서 셀러 업체와 그 담당자 권한에 사용한다. 기존 `organization_type=buyer` 값은 이전 스키마 호환을 위해 남아 있을 수 있지만 신규 개인 바이어 가입에서는 생성하지 않는다.

셀러는 `pending` 상태에서도 draft 공고를 만들 수 있지만 `verified` 전에는 publish할 수 없다. 실제 검증 자동화가 없는 MVP에서는 관리자 seed 또는 승인 script로 상태를 바꾼다.

## 4. 셀러 공고

### `listings`

공개 카드와 상태를 담당한다.

| 컬럼 | 의미 |
| --- | --- |
| `seller_organization_id` | 공고 소유 셀러 |
| `status` | draft/processing/ready/published/paused/expired/archived |
| `creation_method` | manual/upload |
| `title`, `display_title` | 내부/공개 제목 |
| `district` | 부산 구 단위 지역 |
| `category` | 자동차 렌탈/액티비티/투어/숙박 |
| `seller_description` | AI 요약 근거가 되는 셀러 설명 |
| `ai_summary` | 공개 카드 한 줄 요약 |
| `hero_document_id` | 대표 이미지 document |
| `current_version_id` | 현재 공개/편집 계약 버전 |
| `popularity_score`, `view_count`, `contract_request_count` | 정렬용 지표 |

`published_at`, `paused_at`, `expires_at`로 공개 수명주기를 기록한다.

### `listing_terms`

공고 폼과 필터에 필요한 현재 구조화 조건이다.

- 공급 시작/종료일
- 공급 수량과 단위
- 기준 단가, 통화, 가격 단위
- 최소/최대 인원
- 취소 조건
- 환불 조건
- 정산 조건
- 안전 조건
- 보상 조건
- 책임·면책 조건
- 가격 표시 기준과 계약 가능 안내

### `listing_versions`, `listing_clauses`

- OCR 추출 또는 AI 생성 결과를 immutable version으로 보존한다.
- `(listing_id, version_no)`는 unique다.
- publish된 버전을 수정하지 않고 새 version을 만든다.
- 공개 시 buyer 관점 AI 분석을 별도로 실행한다.

### `price_estimates`

예상 가격 요청과 결과의 근거를 저장한다.

- 입력 인원/기간/표시 통화
- 결과 금액
- 계산 방식 `deterministic`, `historical_adjusted`
- 사용한 기준 단가와 환율 metadata
- AI 설명과 confidence

LLM이 숫자를 직접 계산한 값을 source of truth로 사용하지 않는다.

## 5. 실제 계약과 협상

### `contracts`

`listing_id`를 통해 원 공고를 추적한다. `buyer_user_id`는 외국인 개인 계약 당사자이며, `seller_organization_id`는 국내 관광업체다. 계약 생성 시 다음을 snapshot한다.

- buyer 개인의 이름·국가·연락처와 seller organization
- 선택적 여행 단체명, 인원수, 서명 자격(`self|group_representative`)
- listing current version/clauses
- 요청 인원과 서비스 기간
- 당시 계산된 예상 가격/통화

`buyer_organization_id`는 이전 B2B 구조와 기존 데이터 호환을 위한 nullable legacy 컬럼이다. 신규 계약 권한과 조회는 `buyer_user_id`를 기준으로 한다. `listing_id`는 nullable로 두어 향후 직접 등록 계약이나 기존 계약 import도 지원한다.

### `contract_parties`

계약 생성 당시 당사자 정보를 snapshot한다.

- seller party: `organization_id`와 업체명/사업자 정보 snapshot
- buyer party: `user_id`와 개인 이름/국가/연락처 snapshot
- 단체 여행: `group_name_snapshot`, `group_size_snapshot`, `signing_capacity=group_representative`

개인 profile이 나중에 수정되어도 체결 당시 party snapshot은 변경하지 않는다.

### `contract_versions`, `contract_clauses`

협상 결과는 기존 내용을 update하지 않고 새 version으로 만든다. `contracts.current_version_id`만 최신 버전을 가리킨다. 서명 요청은 특정 version에 고정된다.

### `revision_requests`

| 컬럼 | 의미 |
| --- | --- |
| `status` | draft/sent/accepted/rejected/partially_accepted/countered/cancelled |
| `contract_version_id` | 요청이 기준으로 삼은 버전 |
| `requested_by_role` | buyer 또는 seller |
| `message` | 전체 요청 설명 |
| `sent_at`, `decided_at` | 전송/결정 시각 |

### `revision_request_items`

12-2 항목별 판단 화면의 source of truth다.

| 컬럼 | 의미 |
| --- | --- |
| `clause_id` | 수정 대상 조항. 새 조항 추가라면 null 가능 |
| `request_type` | 취소 조건, 정산, 인원 변경 등 |
| `reason` | 바이어/셀러 요청 사유 |
| `requested_text` | 요청자가 원하는 문구 |
| `decision` | pending/accepted/rejected/countered |
| `decision_reason` | 상대방 판단 사유 |
| `counter_text` | 상대방 대안 문구 |

모든 item이 결정되어야 revision 전체 결과를 확정한다. `reject-all`은 각 item을 rejected로 일괄 업데이트하는 편의 동작이다. `계약 안하기`는 contract를 cancelled로 바꾸고 열린 revision도 cancelled 처리한다.

## 6. 파일·AI

### `documents`

`listing_id/listing_version_id` 또는 `contract_id/contract_version_id`에 연결할 수 있다.

| purpose | 용도 |
| --- | --- |
| `source_contract` | 셀러가 올린 PDF/DOCX/이미지 |
| `reference` | AI 참고 자료 |
| `listing_hero` | 공개 카드 대표 이미지 |
| `draft_pdf` | 서명 전 렌더링 PDF |
| `signed_contract` | 서명 완료 PDF |
| `audit_trail` | 서명 이력 PDF |
| `parsed_artifact` | Document Parse 결과 JSON |

사용자 계약 원본은 Supabase Storage에 두고 Document Parse/Information Extract 결과를 조항별로 직접 분석한다. 실제 Upstage 제품 adapter가 Universal Extraction 명칭을 사용하더라도 내부 job/API 명칭은 과제 요구사항에 맞춰 `information_extract`로 통일한다. 사용자 계약서는 공용 Vector Store에 올리지 않는다. 별도로 검수한 공식 근거와 승인 템플릿만 Upstage Files/Vector Store에 두며, DB에는 전용 knowledge registry와 provider id, 처리 상태를 저장한다.

### `ai_jobs`, `ai_analysis_runs`, `ai_findings`

AI target은 listing version 또는 contract version 중 정확히 하나다.

- seller 분석: 공고 작성 중 셀러에게 불리한 조항 점검
- buyer 분석: 공개 원문 화면에서 바이어에게 모호하거나 불리한 조항 점검
- 공개 API는 buyer 분석만 반환한다.
- 모든 finding은 모델명, prompt version, evidence와 disclaimer를 가진다.

`005_single_contract_review_agent.sql`에서는 `ai_analysis_runs`에 다음 실행 metadata를 추가한다.

| 컬럼 | 의미 |
| --- | --- |
| `execution_mode` | `fixed_task` 또는 `single_agent` |
| `agent_name` | Agent 실행이면 `contract_review`, 고정 task면 null |
| `max_iterations` | 허용된 최대 도구 반복 횟수. MVP는 2 |
| `iterations_used` | 실제 수행한 반복 횟수 |
| `stop_reason` | `completed`, `max_iterations`, `insufficient_evidence`, `provider_error` |
| `execution_metadata` | 사용한 tool 이름, 호출 순서, schema version 등 비민감 metadata |

원문 prompt, 전체 계약서, API 응답 전문은 `execution_metadata`에 저장하지 않는다. Agent의 각 File Search 호출은 기존 `rag_retrieval_runs`에 별도 행으로 남기며, 최종 채택된 근거만 `rag_evidence`에 고정한다.

### RAG knowledge registry

공식 법령·행정규칙·표준약관과 팀 승인 템플릿은 사용자 파일용 `documents`에 섞지 않고 다음 전용 테이블로 관리한다.

| 테이블 | 의미 |
| --- | --- |
| `knowledge_bases` | 공식/템플릿 corpus와 Upstage Vector Store 연결 |
| `knowledge_documents` | 논리 문서, 출처, 권위 수준, 공식 URL, 적용 상품 카테고리 |
| `knowledge_document_versions` | 시행일, hash, immutable Storage 경로, Upstage file id, active/superseded 상태 |
| `rag_retrieval_runs` | analysis별 한국어 query, metadata filter, top-k와 provider 요청 기록 |
| `rag_evidence` | finding별 고정 근거의 rank, score, page, section, excerpt, bbox |
| `localized_contents` | 공고·계약·finding의 한국어/영어/일본어/중국어 결과 cache |

AI 패널의 근거 번호는 `rag_evidence.id`를 가리킨다. 문서가 개정되어도 체결·분석 당시 사용한 `knowledge_document_versions` snapshot을 유지해 같은 페이지와 인용을 재현한다.

MVP 공식 자료는 PDF를 그대로 Upstage Files/Vector Store에 적재한다. `knowledge_document_versions.metadata`에는 `file_format=pdf`, `is_searchable`, `parse_required`, `original_page_count`를 기록한다. Markdown 정규화 경로는 nullable이며 필수 ingestion 단계가 아니다. 국내여행 표준약관은 `common`에 한 번만 저장하고 `contract_categories={tour}`로 제한한다.

## 7. 전자서명

### `signature_requests`

- `provider_template_id`: 모두싸인 templateId
- `provider_document_id`: 요청 응답 id
- `provider_status`: ON_PROCESSING/ON_GOING/COMPLETED raw 값
- `current_signing_order`: 모두싸인 현재 순서
- `signed_document_id`, `audit_trail_document_id`: Storage에 복사한 최종 파일

### `provider_events`

모두싸인 웹훅 원본 전체를 그대로 로그에 남기지 않고 식별값과 정규화 결과를 저장한다.

- `(provider, provider_event_id)` unique로 중복 웹훅을 막는다.
- `payload_hash`로 같은 event id의 변조된 재전송을 감지한다.
- `processed`, `processing_error`, `processed_at`으로 재처리 상태를 추적한다.
- 완료 PDF와 audit trail의 Storage 복사가 성공한 뒤에만 signature request와 contract를 `completed/signed`로 바꾼다.

### `signature_participants`

`provider_role_name`은 모두싸인 템플릿의 `바이어`, `셀러`와 정확히 일치해야 한다. buyer participant에는 개인 바이어의 이름과 이메일을 사용한다.

단체 대표 서명에서는 `represents_group_name`, `represents_group_size`, `representation_confirmed_at`을 기록한다. 이는 대표자 1명의 서명이며 참가자 전원의 서명이 아니다. 대표 권한 확인 문구와 계약 version은 `audit_events`에도 남긴다.

테스트에서는 같은 이메일을 두 역할에 쓸 수 있으므로 unique 기준은 이메일이 아니라 `(signature_request_id, party_role)`다.

모두싸인 인증 이메일/API 키는 DB에 저장하지 않고 서버 secret 환경변수로만 주입한다.

## 8. 인덱스와 목록 조회

공개 탐색:

- `(status, category, district, published_at desc)`
- `(status, popularity_score desc)`
- `(status, base_price_amount_minor)`는 `listing_terms` join을 고려해 별도 검색 view 또는 query 사용
- 공급 기간 `(service_start_date, service_end_date)`

셀러 화면:

- `(seller_organization_id, status, updated_at desc)`
- 계약 `(seller_organization_id, status, updated_at desc)`

바이어 마이페이지:

- `(buyer_user_id, status, updated_at desc)`
- 기간 종료 버킷용 `contract_terms(service_end_date)`

검색 규모가 커지면 title/display_title에 `pg_trgm` GIN index를 사용한다.

## 9. Storage

| bucket | 공개 여부 | 용도 |
| --- | --- | --- |
| `listing-assets` | private | 대표 이미지. API가 짧은 signed URL 발급 |
| `contract-documents` | private | 원본 계약서 |
| `contract-artifacts` | private | parse JSON과 draft PDF |
| `signed-contracts` | private | 완료 PDF와 audit trail |
| `rag-knowledge` | private | 공식/템플릿 PDF 원본 snapshot, 선택적 parse/page artifact, manifest |

```
{seller_org_id}/listings/{listing_id}/{document_id}/original.pdf
{seller_org_id}/listings/{listing_id}/{document_id}/parsed.json
{seller_org_id}/listings/{listing_id}/hero/{document_id}.{ext}
{seller_org_id}/contracts/{contract_id}/{version_id}/draft.pdf
{seller_org_id}/contracts/{contract_id}/{signature_request_id}/signed.pdf
{seller_org_id}/contracts/{contract_id}/{signature_request_id}/audit-trail.pdf
```

## 10. RLS와 공개 접근

- 공개 browsing은 FastAPI의 `/public` endpoint가 service role로 필요한 컬럼만 projection한다.
- 브라우저가 Supabase 테이블을 직접 조회해 계약 원문이나 내부 finding을 가져가지 않는다.
- seller listing 쓰기는 seller organization member만 가능하다.
- `publish`는 organization이 verified인지 domain service에서 확인한다.
- 계약/수정 요청/서명 정보는 `buyer_user_id = auth.uid()`인 개인 바이어 또는 seller organization 구성원만 접근한다.
- `profiles`, `notifications`는 본인만 조회한다.
- `audit_events`, `provider_events`, `ai_*`는 클라이언트 직접 쓰기를 허용하지 않는다.

FastAPI service role은 RLS를 우회하므로 repository 호출 전 개인 바이어는 `actor_user_id`, 셀러는 `organization_id`와 membership을 검증한다.

## 11. 개인정보와 보안

- 비밀번호는 Supabase Auth에만 저장한다.
- API 키, service role key, 실제 계약 원문을 Git이나 로그에 남기지 않는다.
- 공개 공고 API는 사업자번호, 담당자 전화번호/이메일을 반환하지 않는다.
- AI prompt log에 원문 계약이나 개인정보를 평문으로 기록하지 않는다.
- provider download URL은 만료될 수 있으므로 즉시 Storage로 복사한다.
- 공고를 비공개 처리해도 이미 체결된 contract와 감사 로그는 삭제하지 않는다.

## 12. 데모 seed

| 엔티티 | 값 |
| --- | --- |
| Seller | 해운대 오션스테이, verified, accommodation |
| Listing | 2026 부산 여름 객실 공급, published, 해운대구 |
| Listing terms | 7~8월, 30실, 145,000 KRW/room-night, 최소 20명 |
| Buyer | Yuki Tanaka, JP, ja-JP, JPY, 선택 단체명 `GlobalTrip 여행 모임` |
| Contract request | 개인 대표자, 30명 단체, 2박, 취소 조건 수정 요청 |
| Finding | 취소 수수료 확정 시점 모호 `medium` |
| Revision items | 취소 기한 변경, 인원 변경 조항 추가 |
| Locales | ko-KR 원문, ja-JP 데모, en-US/zh-CN 동일 pipeline 결과 |

실제 auth UUID와 API credential은 migration seed에 고정하지 않는다.
