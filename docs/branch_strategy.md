# Branch Strategy

BusanLink는 포크 없이 하나의 공동 레포지토리에서 협업합니다.

## 브랜치 규칙

- `main`: 리뷰와 테스트를 마친 배포 가능한 코드만 둡니다.
- `main`에 직접 푸시하지 않습니다. 모든 변경은 PR로 병합합니다.
- 작업 브랜치는 최신 `main`에서 만듭니다.
- PR 병합 후 작업 브랜치는 삭제합니다.

## 브랜치 이름

- 기능: `feature/<short-description>` — `feature/login-page`
- 버그 수정: `fix/<short-description>` — `fix/upload-error`
- 리팩터링: `refactor/<short-description>`
- 문서: `docs/<short-description>`
- 테스트: `test/<short-description>`
- 의존성: `chore/deps-<package>`

영어 소문자, 숫자, `/`, `-`만 사용하고, 설명은 2~5단어로 작성합니다.

## 작업 흐름

```bash
# 1. 작업 전 main 최신화
git switch main
git pull origin main

# 2. main에서 작업 브랜치 생성
git switch -c feature/login-page

# 3. 작업 후 커밋과 푸시
git add .
git commit -m "feat: 로그인 페이지 추가"
git push -u origin feature/login-page
```

GitHub에서 `feature/login-page` → `main` PR을 만들고 리뷰를 받은 뒤 병합합니다.

## 충돌 해결

PR에서 충돌이 발생하면 최신 `main`을 작업 브랜치에 반영합니다.

```bash
git switch feature/login-page
git fetch origin
git merge origin/main
```

충돌을 해결하고 테스트한 뒤 커밋·푸시하고, 다시 리뷰를 요청합니다.
