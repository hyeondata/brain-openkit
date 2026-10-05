# Brain OpenKit v0.2.0a3 릴리스

[English](release-0.2.0a3.md) | 한국어

이 알파 버전은 CLI와 Claude Code·Codex 플러그인의 전체 소스를
[GitHub 릴리스](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a3)로 제공합니다.
Python 3.11 이상이 필요합니다. PyPI와 공개 플러그인 디렉터리 등록은 이번 배포에 포함하지 않습니다.

## 다운로드와 설치

릴리스 페이지에서 다음 파일을 같은 디렉터리에 내려받습니다.

- `brain_openkit-0.2.0a3-py3-none-any.whl`: CLI 설치 파일입니다.
- `brain_openkit-0.2.0a3.tar.gz`: 스킬 8개, 호스트 manifest, 실행기, 예제,
  문서를 포함한 전체 소스 배포본입니다.
- `release-verification.json`: 소스·배포 파일·테스트·호스트 실행 검증 기록입니다.
- `SHA256SUMS`: 배포 파일의 체크섬입니다.

설치 전에 파일을 검증합니다. 다음은 macOS 예제입니다.

```bash
shasum -a 256 -c SHA256SUMS
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ./brain_openkit-0.2.0a3-py3-none-any.whl
brain-openkit --version
```

Linux에서는 `sha256sum -c SHA256SUMS`를 사용할 수 있습니다. Windows에서는
`Get-FileHash -Algorithm SHA256` 결과를 `SHA256SUMS`와 대조하고,
`.venv\Scripts\Activate.ps1`로 가상 환경을 활성화합니다.

호스트 플러그인은 소스 압축 파일을 풀어 전체 디렉터리를 유지한 상태에서
[Claude Code·Codex 설치 안내](agent-integration.ko.md)를 따르세요. wheel을 설치해도
호스트 플러그인이 등록되지는 않습니다. 제품 디렉터리와 Obsidian vault는 분리합니다.
태그로 고정한 저장소를 사용할 수도 있습니다.

```bash
git clone --branch v0.2.0a3 --depth 1 https://github.com/hyeondata/brain-openkit.git
```

## 이 버전의 기능

로컬 BM25 검색은 노트 경로, 줄 번호, 정확한 원문 발췌를 반환합니다.
호스트 스킬 8개는 초기화, 검색, 원문 수집, 저장, 정리, 검사, 발췌형 개요,
출처가 있는 조사를 지원합니다. 변경 미리 보기와 정확한 계획 ID로 쓰기를 적용하고
트랜잭션을 기록합니다. 실행 취소는 기록된 변경 후 내용과 현재 내용을 대조합니다.
분류 기본 제공자는 Kev이며 포함된 실행 스크립트가 고정된 Hugging Face Kev 0.8B
가중치를 선택합니다. Laya와 TypeSafe Jev로 교체할 수 있습니다. 검색·평가는
모델 서버 없이 BM25를 기본으로 사용합니다.

모델별 별도 실행 환경은 [로컬 모델 안내](local-models.ko.md)에 있습니다.
호스팅된 Claude·Codex 세션에는 각 호스트의 인증과 모델 사용 권한이 필요합니다.
로컬 판단 모델을 실행해도 호스트 세션 전체가 오프라인이 되지는 않습니다.

## 검증과 한계

배포 파일과 호스트 실행은 이전 모델·앱 검증과 구분해 확인합니다.
릴리스에 첨부한 `release-verification.json`은 정확한 소스 커밋, 배포 파일 체크섬,
설치 검사와 호스트 실행 결과를 기록하며, 배포 산출물에 대한 검증의 기준입니다.

이전 근거로 [Kev 0.8B](kev-08-verification-2026-10-05.md),
[Laya·Kev 0.5B](model-verification-2026-10-05.md),
[Obsidian 앱 검증](obsidian-app-verification-2026-10-05.ko.md)이 있습니다.
앱에서는 한영 본문, 검색, 속성, 링크, 백링크, 그래프 갱신과 fold 실행 취소 후
원본 파일의 정확한 복원을 확인했습니다.

이는 합성 vault에서 수행한 제한된 기능 검증이며 실제 대규모 환경의 품질·비용
비교가 아닙니다. 모델 태그 오탐이 기록되어 있으며 Claude·Codex와 품질이 같다고
주장하지 않습니다. TypeSafe Jev의 실제 키를 이용한 추론은 미검증입니다.
CLI와 호스트 스킬은 별도의 Obsidian 플러그인 화면을 설치하지 않습니다.
계획과 트랜잭션 기록에는 노트 내용이 포함되므로 vault와 함께 비공개로 관리하세요.
