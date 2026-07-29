# Supabase database

`migrations/`의 SQL 파일은 파일명 순서대로 깨끗한 Supabase PostgreSQL에 적용합니다.
이미 적용한 migration 파일은 수정하지 않고, 다음 변경은 새 파일로 추가합니다.

## Migration 구성

- `001_initial_schema.sql`: 프로필과 셀러 조직
- `002_marketplace_wireframe.sql`: 공고, 계약, 협상, 문서, 서명 저장 구조
- `003_individual_buyer.sql`: 관계 무결성, 조회 인덱스, 개인 바이어·셀러 RLS
- `004_rag_challenge_alignment.sql`: AI 실행, RAG 지식 문서·근거, 다국어 cache

모든 bucket은 private으로 운영합니다. Storage bucket과 object 정책은 파일 업로드 기능을
구현하는 후속 브랜치에서 실제 접근 흐름과 함께 추가합니다.

## 로컬 검증

로컬 PostgreSQL의 `initdb`, `pg_ctl`, `psql`이 필요합니다.

```bash
./supabase/tests/run_migrations.sh
```

이 명령은 임시 빈 PostgreSQL을 만들고 migration을 순서대로 적용한 다음 다음 항목을
검사합니다.

- 모든 애플리케이션 테이블의 RLS 활성화
- 주요 목록 조회 인덱스 존재
- 프로필 본인 접근
- 셀러 조직 멤버의 공고 작성 권한
- 관계없는 사용자의 공고 작성 및 계약 조회 차단
- 공고 version의 불변성
- 애플리케이션 DB에 비밀번호 컬럼이 없는지 여부

테스트용 `auth.users`와 `auth.uid()` 모형은 임시 DB에만 만들며 migration에는 포함하지
않습니다. 실제 Supabase 환경에서는 Supabase Auth가 이 schema를 제공합니다.
