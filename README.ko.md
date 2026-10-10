<h1 align="center">Brain OpenKit</h1>

<p align="center">
  <strong>Obsidian을 위한 오픈소스 세컨드 브레인 도구 모음.</strong><br>
  판단 제공자를 교체할 수 있는 원문 기반 검색·검토 후 노트 정리 도구.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb" alt="MIT 라이선스"></a>
  <img src="https://img.shields.io/badge/status-alpha-d97706" alt="알파">
  <a href="https://huggingface.co/convaiinnovations/laya"><img src="https://img.shields.io/badge/optional%20model-Laya-0f766e" alt="선택적 모델: Laya"></a>
</p>

<p align="center">
  <a href="README.md">English</a> · 한국어<br>
  <a href="#현재-기능">소개</a> · <a href="#소스에서-설치">설치</a> ·
  <a href="docs/agent-integration.ko.md">Claude Code / Codex</a> ·
  <a href="docs/conversation-archive.ko.md">대화 아카이브</a> ·
  <a href="#제공자">제공자</a> · <a href="#로드맵">로드맵</a>
</p>

> **알파 버전 [v0.2.0a4](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4)입니다.**
> CLI와 호스트 플러그인을 같은 버전으로 설치하려면 태그 체크아웃을 사용하세요.
> GitHub 릴리스 파일로 CLI와 전체 소스를 제공하며, PyPI에는 배포하지 않았습니다.
> 각 버전의 검증 근거와 한계는 [0.2.0a4 검증](docs/release-0.2.0a4.ko.md),
> [이전 0.2.0a3 검증](docs/release-0.2.0a3.ko.md),
> [구현·검증 기록](docs/implementation-notes.md)을 참고하세요.

**현재 검증 환경은 macOS입니다.** 테스트와 CI는 macOS 및 Python 3.11
이상을 대상으로 합니다. Windows와 Linux에서는 이번 변경을 검증하지 않았습니다.
기록된 앱·실제 모델 검증은 Apple Silicon 환경이며, Intel Mac은 별도로 검증하지
않았습니다. 이전 릴리스 보고서의 CI 결과는 당시의 검증 기록으로 유지합니다.

아래의 선택적 `ko-decision`·`codex` 제공자, 문서 전체 분류와 `--prompt-language` 옵션은 아직 릴리스하지
않은 소스 변경입니다. `v0.2.0a4` 태그와 릴리스 파일에는 없으며, 이 변경이 포함된
체크아웃에서 사용할 수 있습니다.

Brain OpenKit은 원문 경로, 줄 번호, 발췌와 함께 Markdown 문단을 찾습니다.
**기본 검색은 모델이나 API 키가 필요 없는 로컬 BM25입니다.** Claude Code와 Codex는
동일한 8개 스킬로 근거를 검색하고 노트를 작성하며 검토한 변경을 적용할 수 있습니다.
선택적 Laya·Kev·ko-decision·Codex·TypeSafe Jev 어댑터는 관련성·분류·태그를 판단하고,
노트 초안 작성은 호스트 Claude/Codex 모델이 담당합니다.

## 현재 기능

- 수정·삭제된 노트를 반영하고 1부터 시작하는 시작·끝 줄 번호와 원문을 검색합니다.
  재정렬이 실패하면 전체 BM25 순서를 유지합니다.
- 최대 10개 분류와 30개 태그 중에서 추천합니다. 호스트 Claude/Codex 또는 Codex
  제공자는 문서 전체를 판단하며, Laya·Kev·Jev·ko-decision은 문단별 판단과 충돌 표시를
  유지합니다. 분류 명령은 노트를 수정하지 않습니다.
- 검토할 수 있는 변경 계획으로 vault 초기화·기존 vault 채택, 로컬 원문 수집,
  선택한 초안 저장, 메타데이터·링크 추가, 발췌형 개요 작성을 제공합니다.
- 정확히 승인한 계획을 적용하고 트랜잭션을 기록하며, 파일이 기록된 상태와
  일치할 때 실행 취소·중단 복구를 수행합니다.
- 링크·지원 메타데이터 검사, 정답이 있는 질문 평가,
  `127.0.0.1`의 읽기 전용 BM25 검색 화면을 제공합니다.
- 선택적으로 로컬 Markdown 대화 아카이브를 `Inbox/Conversations/`에
  보관합니다. 아카이브는 기본적으로 꺼져 있습니다.

제품 체크아웃과 실제 vault는 별도 디렉터리입니다. 검색·분류는 원본 노트를 읽고
인덱스는 파생 캐시에 저장합니다. 선별한 지식을 노트로 정리하는 작업은 먼저 변경 계획을 만들며,
명시적으로 적용한 계획을 통해서만 노트를 씁니다.

**대화 아카이브는 기본적으로 꺼져 있습니다.** 보관함을 명시적으로 선택해
활성화하면 로컬 Markdown 아카이브의 갱신을 허용하게 됩니다. 아카이브 작업은
모델을 사용하거나 네트워크 요청을 하지 않지만, 호스트 대화는 유료 호스팅 모델을
사용할 수 있습니다. 상태 확인, 활성화·비활성화 명령, 호스트 설정과 현재 검증의
한계는 [대화 아카이브 가이드](docs/conversation-archive.ko.md)를 참고하세요.
Claude Code와 Codex CLI는 작업 중인 소스로 OFF·ON·세션 재개 검사를 통과했습니다.
Codex Desktop의 수집 동작은 미검증입니다. 최종 배포 파일과 CI 결과는
[릴리스 증거](docs/release-0.2.0a4.ko.md)에 별도로 기록합니다.

Obsidian 1.13.4에서 합성 보관함의 저장 결과, 본문·태그 검색, 링크·백링크,
그래프와 되돌리기 반영을 확인했습니다. 화면 9장과 검증 범위는
[한국어 앱 검증 보고서](docs/obsidian-app-verification-2026-10-05.ko.md)에서 확인할 수 있습니다.

## 소스에서 설치

macOS에서 **Python 3.11 이상**이 필요합니다. 다음 명령은 `v0.2.0a4` 태그로
버전을 고정합니다. 계속되는 개발은 `main`에서 진행합니다.

~~~bash
git clone --branch v0.2.0a4 --depth 1 https://github.com/hyeondata/brain-openkit.git
cd brain-openkit
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m brain_openkit --help
brain-openkit --version
~~~

CLI에는 외부 런타임 의존성이 없지만 설치 중 빌드 도구를 다운로드할 수 있습니다.
로컬 Laya·Kev·ko-decision 서버는 각각 별도 선택적 환경을 사용합니다.

[GitHub 프리릴리스](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4)에서
다음 릴리스 파일을 내려받을 수 있습니다.

| 파일 | 용도 |
| --- | --- |
| [brain_openkit-0.2.0a4-py3-none-any.whl](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4-py3-none-any.whl) | Python 환경에 CLI만 설치합니다. |
| [brain_openkit-0.2.0a4.tar.gz](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4.tar.gz) | 전체 소스 배포본입니다. 압축을 풀어 CLI 소스와 호스트 플러그인을 사용합니다. |
| [SHA256SUMS](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/SHA256SUMS) | 릴리스 파일의 SHA-256 체크섬입니다. |

CLI만 필요하다면 내려받은 wheel을 활성화한 Python 환경에 설치합니다.

~~~bash
python -m pip install ./brain_openkit-0.2.0a4-py3-none-any.whl
~~~

**호스트 플러그인에는 태그 체크아웃이나 압축을 푼 전체 소스 배포본이 필요합니다.**
`skills/`, `scripts/`, `src/`, `hooks/`와 호스트 manifest 파일을 함께 유지하세요.
wheel이나 소스 압축 파일을 pip로 설치하면 Python CLI가 설치되며,
Claude·Codex 플러그인이 등록되지는 않습니다. 아래 예제는 합성 예제 vault를 포함한
전체 체크아웃을 기준으로 합니다. PyPI 패키지는 배포하지 않았습니다.

모든 vault 작업에는 명시적으로 지정한 vault가 필요합니다. 기존 노트 작업은
**`--vault` 또는 JSON 설정의 `vault`를 받으며**, `conversations` 명령에는
`--vault`를 직접 지정해야 합니다.
노트의 부모 디렉터리에서 vault를 추정하지 않습니다.
제공자를 확인하는 `doctor`만 vault 없이 실행할 수 있습니다.

## Claude Code·Codex에서 사용

태그 체크아웃이나 압축을 푼 전체 소스 배포본의 루트에서 사용할 호스트에
로컬 마켓플레이스를 등록합니다.

~~~bash
# Claude Code
claude plugin marketplace add "$PWD"
claude plugin install brain-openkit@brain-openkit

# Codex
codex plugin marketplace add "$PWD"
codex plugin add brain-openkit@brain-openkit
~~~

설치 후 호스트를 다시 시작합니다. 포함된 Python 실행기는 editable 패키지 설치 없이
플러그인 캐시에서도 작동합니다. Python 3.11 이상과 호스트의 정상적인 인증·모델 사용
권한은 별도로 필요합니다.
이 안내는 로컬 제품 디렉터리를 사용합니다. 현재 검증 범위는
[0.2.0a4 검증](docs/release-0.2.0a4.ko.md)을 참고하세요.
[0.2.0a3 검증](docs/release-0.2.0a3.ko.md)은 이전 릴리스의 기록이며
대화 아카이브 기능을 검증하지 않습니다.

| 스킬 | 용도 |
| --- | --- |
| `brain-init` | 기존 노트를 대체하지 않고 vault를 초기화하거나 채택합니다. |
| `brain-search` | vault 범위의 질문에 실제 원문 인용으로 답합니다. |
| `brain-ingest` | 제공된 원문을 보존하고 연결된 노트를 만듭니다. |
| `brain-save` | 선택한 지식을 출처 링크와 함께 저장합니다. |
| `brain-organize` | 호스트가 문서의 분류·태그를 추천하고 메타데이터·링크를 검토·적용합니다. |
| `brain-lint` | 자동 수정 없이 링크·메타데이터 문제를 보고합니다. |
| `brain-fold` | 원본 노트를 보존하면서 발췌형 개요를 만듭니다. |
| `brain-research` | 호스트 조사 도구를 사용하고 출처가 있는 조사 노트를 저장합니다. |

예를 들어 Claude Code에서는 `/brain-openkit:brain-search`, Codex에서는
`$brain-openkit:brain-search`를 호출하고 vault의 절대 경로를 전달합니다.
설치·호출·워크스페이스 스킬 대안·검증·제거의 기준 문서는
[에이전트 통합 안내](docs/agent-integration.ko.md)입니다.

분류·태그 추천을 요청하면 `brain-organize`는 별도 제공자를 선택하지 않은 경우 현재
Claude/Codex 호스트를 사용합니다. 노트 전체와 분류·태그 목록을 읽고 중심 주제와 주요
태그를 추천한 뒤 `classify --suggestions FILE`로 JSON을 검증합니다. 이 검증은 모델
프로세스를 추가로 실행하지 않으며, 호스트 대화의 통상 사용량은 발생합니다.
승인된 변경은 기존 미리보기·적용·되돌리기 절차로 처리합니다. Claude는 이 공용 스킬을
사용하며 `--provider claude` 옵션은 없습니다.

요청한 문장 작성과 웹 검색·자료 추출은 호스트가 담당합니다.
CLI 자체는 로컬 UTF-8 텍스트를 수집하며 웹 탐색·OCR·음성 전사를 하지 않습니다.
로컬 판단 모델을 사용해도 호스팅된 Claude·Codex 대화 전체가 오프라인이 되는 것은 아닙니다.

## 로컬 검색 실행

CLI 환경을 활성화한 상태에서 체크아웃 루트에서 실행합니다.

~~~bash
brain-openkit index --vault examples/vault
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault
brain-openkit search "reading journal comets" --vault examples/vault --json
brain-openkit lint --vault examples/vault --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --json
brain-openkit web --vault examples/vault --port 8765
~~~

마지막 명령은 `http://127.0.0.1:8765`에서 확인하고 Ctrl+C로 종료합니다.
웹 화면은 루프백 주소에만 연결되며 읽기 전용 BM25 검색을 제공합니다.
Obsidian 플러그인은 아닙니다.

검색·평가는 기본적으로 `--provider none`을 사용하고 인덱스를 갱신합니다.
기본 캐시는 현재 디렉터리의 `.cache/brain-openkit`이며 `--cache-dir`로 바꿉니다.
[노트 4개 예제](examples/README.md)는 실행 확인용이며 검색 품질을 입증하지 않습니다.

## 노트 변경 미리 보기와 적용

먼저 일회용 vault에서 실행하세요. 계획은 **vault 외부의 새 파일**에 저장해야 하며,
저장할 디렉터리는 이미 존재해야 합니다. 계획에는 변경 후 본문과 diff가 포함됩니다.

~~~bash
mkdir -p ../brain-openkit-demo ../brain-openkit-review
brain-openkit init --vault ../brain-openkit-demo --plan ../brain-openkit-review/init.json --json
~~~

JSON의 `changes`, 각 `diff`, `id`를 확인합니다.
아래 자리표시자는 검토한 계획의 정확한 ID로 바꿉니다.

~~~bash
brain-openkit apply ../brain-openkit-review/init.json --vault ../brain-openkit-demo --approve PASTE_REVIEWED_PLAN_ID --json
~~~

다음은 순차적으로 계획을 만드는 예제입니다. **각 계획을 검토·적용한 다음
다음 계획을 만드세요.** 위 apply 명령에서 파일 이름과 정확한 ID를 바꿔 사용합니다.
미리 보기 명령만으로는 vault 노트를 수정하지 않습니다.

~~~bash
brain-openkit ingest examples/vault/local-search.md --title local-search --vault ../brain-openkit-demo --plan ../brain-openkit-review/ingest.json --json
brain-openkit save examples/vault/local-search.md --path Notes/search-decision.md --source Notes/local-search.md --vault ../brain-openkit-demo --plan ../brain-openkit-review/save.json --json
brain-openkit organize Notes/local-search.md --category research --tag local --link Notes/search-decision.md --vault ../brain-openkit-demo --plan ../brain-openkit-review/organize.json --json
brain-openkit fold Notes/local-search.md Notes/search-decision.md --path Notes/search-overview.md --title "Search overview" --vault ../brain-openkit-demo --plan ../brain-openkit-review/fold.json --json
~~~

`ingest`는 원본 바이트를 `Sources/`에 보존하며, `--draft FILE`로 호스트가 작성한
본문을 연결 노트에 사용할 수 있습니다. `--source-url URL`은 출처를 기록하고 URL을
가져오지는 않습니다. `save`는 전달된 초안을 저장하고, `fold`는 요약문을 생성하지
않고 문단·인용을 발췌합니다. `organize`는 제한된 frontmatter 형식에서 요청한 태그를
합치고 관계없는 본문을 보존합니다. 지원하지 않는 구조는 거절합니다.
모델 점수가 메타데이터 변경 권한이 되지는 않습니다.

적용 성공 시 트랜잭션 ID를 반환합니다. 실행 취소에는 이 ID를,
중단 복구에는 중단된 트랜잭션의 ID를 사용합니다.

~~~bash
brain-openkit undo TRANSACTION_ID --vault ../brain-openkit-demo --json
brain-openkit recover INTERRUPTED_TRANSACTION_ID --vault ../brain-openkit-demo --json
~~~

적용은 변경 전 본문을, 실행 취소는 기록된 변경 후 본문을 확인합니다.
충돌하는 편집이 있으면 중단합니다. 개별 파일 교체는 원자적으로 처리하며,
여러 파일에 걸친 트랜잭션은 journal로 복구합니다.
도구 내부 잠금이 외부 편집기까지 잠그지는 않습니다.

**계획과 `VAULT/.brain-openkit/transactions/`에는 변경 전후의 비공개 노트 본문이
포함됩니다.** 동기화·공유할 때도 비공개 vault 데이터로 취급하세요.
복구를 위해 journal을 보관하며, 플러그인을 제거해도 journal은 제거되지 않습니다.

## 제공자

| 제공자 | 역할과 현재 근거 |
| --- | --- |
| `none` | 검색·평가 기본값. 로컬 BM25이며 모델 키·추론이 필요 없습니다. |
| `laya` | 선택적 로컬 다국어 판단. 실제 가중치로 실행했습니다. |
| `kev` | 분류·상태 확인 기본값. 포함된 서버 실행 스크립트가 Hugging Face의 고정된 Kev 0.8B 가중치를 선택하며, [실제 CLI 검증](docs/kev-08-verification-2026-10-05.md)을 통과했습니다. |
| `jev` | TypeSafe 호스팅 어댑터. 계약 fixture 테스트를 통과했으며 실제 키로 추론은 미검증입니다. |
| `ko-decision` | 미릴리스 소스에서 제공하는 선택적 한국어 RoBERTa 판단. 고정된 외부 체크포인트를 사용합니다. [설정](docs/local-models.ko.md#ko-decision-미릴리스-소스)과 [검증 기록](docs/ko-decision-verification-2026-10-05.ko.md)을 참고하세요. |
| `codex` | 미릴리스 소스에서 제공하는 선택적 클라우드 판단. 로그인한 Codex CLI를 사용하며, 현재 설정 기본값은 `gpt-6-astra`와 `ultra` 추론입니다. |

`classify`·`doctor`는 설정이나 옵션으로 바꾸지 않으면 Kev를 사용하며, 포함된
서버 실행 스크립트는 0.8B를 선택합니다. Laya는 `--provider laya`로 지정합니다.
검색·평가 기본값은 로컬 BM25(`--provider none`)를 유지합니다.
공통 계약은 현재 `choose`를 구현했으며 일반 `score`·`noul` 연산은 후속 범위입니다.
원격 제공자를 명시적으로 선택하면 선택한 텍스트가 전송되며 클라우드로 자동 전환하지 않습니다.

Laya와 Kev는 모두 Hugging Face의 공개 가중치를 내려받아 로컬에서 실행합니다.
각 모델의 공식 서버를 사용하되 Brain OpenKit에서는 같은 명령으로 교체합니다.
이 구성에서 Hugging Face는 다운로드 저장소이며, 추론은 사용자 컴퓨터에서 실행됩니다.
공개 가중치 다운로드에 Hugging Face 토큰은 필요하지 않습니다.
고정 버전과 가중치·API 모델 이름의 차이는 [로컬 모델 안내](docs/local-models.ko.md)에 있습니다.
Kev 0.8B의 추론, 검색 재정렬, 분류·태그 추천, 평가, 실패 시 fallback,
원문 보존을 [실제 CLI로 확인](docs/kev-08-verification-2026-10-05.md)했습니다.
제공자 옵션 없이 실행한 `doctor`·`classify`도 Kev를 선택했습니다.
[이전 Laya·0.5B 결과](docs/model-verification-2026-10-05.md)는 별도로 보존합니다.
0.8B에서도 태그 오탐이 있었으므로 기능 실행 성공이 품질 동등성이나 전반적인 개선을 뜻하지는 않습니다.

### 선택적 Laya 서버

**별도 환경과 터미널**에서 확인한 런타임을 설치합니다.

~~~bash
python3.12 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=0 \
LAYA_REVISION=7b928d828b7b0e022f929d9bd2e44165aa270148 \
laya-serve
~~~

첫 추론 때 모델을 적재하는 설정입니다. `LAYA_MODELS`는 사전 적재 대상이며
접근 제한이 아닙니다. 클라이언트가 `multilingual`을 명시적으로 요청하므로
첫 추론 때 해당 가중치를 다운로드·적재합니다. 최초 설치·가중치 다운로드에는
네트워크·디스크 공간이 필요하며 실행 중 추가 메모리를 사용합니다.

`.venv`가 활성화된 **CLI 터미널**로 돌아와 실행합니다.

~~~bash
brain-openkit doctor --provider laya --json
brain-openkit doctor --provider laya --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider laya --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --json
~~~

`doctor`는 상태 확인만 하고 **`--probe`가 합성 추론을 실행**하며 필요한 다운로드를
시작할 수 있습니다. 첫 적재에는 기본 10초 대신 `--timeout 120`을 사용하세요.
서버 인증을 설정했다면 두 터미널의 `LAYA_API_KEY`에 같은 키를 넣습니다.
이 공개 가중치에는 Hugging Face 토큰이 필요하지 않습니다.

### 선택적 Kev 서버

별도 터미널에서 [Kev 0.8B 설정](docs/local-models.ko.md#kev-08b-기본값)으로 서버를 시작합니다.
런타임 설치 후 `scripts/serve-kev.py`를 실행하면 `--run` 없이 고정된 0.8B 가중치를
불러옵니다. 이후 CLI 환경에서 실행합니다.

~~~bash
brain-openkit doctor --provider kev --json
brain-openkit doctor --provider kev --probe --timeout 120 --json
brain-openkit search "reading journal comets" --vault examples/vault --provider kev --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider kev --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider kev --timeout 120 --json
~~~

기본 주소는 `http://127.0.0.1:8009`, API 모델 이름은 `kev-latest`입니다.
서버 실행 스크립트는 기본으로 Kev 0.8B를 선택하며 `--run`으로 다른 Hugging Face
가중치를 지정할 수 있습니다. `--model`은 API 모델 이름을
선택하며 가중치를 다운로드하거나 교체하지 않습니다. 로컬 Kev는 서버 인증을 켠
경우에만 키가 필요하며, 이때 CLI 환경의 `KEV_API_KEY`에 같은 키를 설정합니다.
Kev는 TypeSafe의 호스팅 서비스 Jev와 별개 프로젝트입니다.
[0.8B 검증 기록](docs/kev-08-verification-2026-10-05.md)은 이전 0.5B 결과와 구분합니다.

### 선택적 ko-decision 서버 (미릴리스 소스)

[별도 런타임 설정](docs/local-models.ko.md#ko-decision-미릴리스-소스)에 따라
`.[ko-decision]`을 설치하고 `brain-openkit-serve-ko-decision`을 실행합니다.
서버는 `mmetamong/ko-decision-roberta-large`의
`dfd606fff30d52963c0073659ff9a8f6bf1fce6d` 리비전을 내려받으며
`127.0.0.1:8010`에서 요청을 받습니다.

~~~bash
brain-openkit doctor --provider ko-decision --prompt-language ko --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider ko-decision --prompt-language ko --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider ko-decision --prompt-language ko --timeout 120 --json
~~~

`--prompt-language ko`는 내장 지시문과 레이블을 한국어로 바꿉니다. 검색 질문,
노트, 분류·태그 설명을 번역하지는 않습니다. 모든 제공자의 기본값은 영어입니다.
지시문·선택지와 문단으로 만든 입력 쌍은 특수 토큰을 포함해 512토큰 이하여야 합니다.
초과하면 HTTP 413을 반환하며, 검색은 BM25로 복귀하고 분류는 오류를 반환합니다.
점수는 보정되지 않은 선택지 간 상대 확률이며, 이 모델은 요약문을 생성하지 않습니다.
실제 동작과 한계는 [검증 기록](docs/ko-decision-verification-2026-10-05.ko.md)에 있습니다.
기존 Kev·BM25 기본값은 유지합니다.

선택적 가중치는 게시자의
[CC BY-SA 4.0 라이선스](https://huggingface.co/mmetamong/ko-decision-roberta-large/blob/dfd606fff30d52963c0073659ff9a8f6bf1fce6d/README.md)에
따라 별도로 내려받습니다. 독립 구현한 Brain OpenKit 연동 코드는 MIT이며,
저장소에는 가중치를 포함하지 않습니다. [출처·라이선스](ATTRIBUTION.md)를 참고하세요.

### 선택적 TypeSafe Jev

CLI 환경에 `TYPESAFE_API_KEY`를 비공개로 설정합니다. 기본 변수가 없거나 비었을 때만
별칭인 `JEV_API_KEY`를 사용합니다. 키를 JSON·노트·저장소 스크립트에 넣지 마세요.

~~~bash
brain-openkit doctor --provider jev --json
brain-openkit search "reading journal" --vault examples/vault --provider jev --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider jev --json
~~~

기본 주소는 `https://api.typesafe.ai`, 모델은 `jev-latest`이며
`--model`로 모델을 바꿉니다. Jev 상태 확인은 추론 없이 모델 목록을 조회합니다.
`doctor --provider jev --probe`는 추론 요청을 보내므로 검색·분류와 마찬가지로
서비스 비용이 발생할 수 있습니다. 실제 키로 서비스 동작은 아직 검증하지 않았습니다.

### 선택적 Codex CLI (미릴리스 소스)

호환되는 Codex CLI를 설치하고 `codex login`으로 별도 로그인합니다. 별도 실행 파일은
`/path/to/codex login`을 사용합니다. Brain OpenKit은 기존 로그인을 이용하며 인증
정보를 직접 읽지 않습니다. 아래 `/path/to/codex`는 실제 CLI 경로로 바꾸세요.
`--codex-executable`을 생략하면 `PATH`의 `codex`를 사용합니다.

~~~bash
brain-openkit doctor --provider codex --json
brain-openkit doctor --provider codex --model gpt-6-astra --reasoning-effort ultra --codex-executable /path/to/codex --probe --json
brain-openkit search "로컬 검색" --vault examples/vault --provider codex --model gpt-6-astra --reasoning-effort ultra --codex-executable /path/to/codex --codex-timeout 600 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider codex --codex-executable /path/to/codex --json
~~~

Codex 분류는 노트 전체와 분류·태그 목록을 한 요청에 담습니다. 분류 하나, 선택한 태그,
추천 이유와 검토 필요 여부를 반환하며, 모든 문단의 분류 일치나 문단별 태그의 합집합을
요구하지 않습니다. 입력이 너무 크면 노트를 조용히 자르지 않고 오류를 반환합니다.
검색은 기존 문단 재정렬 방식을 유지합니다.

`--probe` 없는 `doctor`는 실행 파일·버전만 확인하며 로그인이나 모델 접근을 검증하지
않습니다. `--probe`는 실제 추론을 실행하여 사용량을 소모하거나 비용이 발생하며,
Codex 검색·분류 요청도 마찬가지입니다. 이 제공자를 선택하면 검색 대상 문단 또는 분류
대상 노트 전체와 질문·선택지
설명이 클라우드로 전송됩니다. 제공자는 읽기 전용으로 판단을 반환하며, 확률·신뢰도는
보정된 분류 점수가 아닌 모델의 자체 평가입니다. 검색 재정렬에 실패하면
`rerank_status: "unavailable"`과 함께 BM25 결과를 반환하므로 이를 Codex 추론 성공으로
보면 안 됩니다. 분류 실패는 오류로 반환합니다.

`--model`·`--reasoning-effort`로 위 기본 설정을 바꿀 수 있으며 모델을 자동 변경하지
않습니다. `--codex-timeout`은 기본 600초이고 HTTP의 `--timeout`과 별개입니다.
2026-10-09 로컬 확인에서 CLI 0.149.0은 `gpt-6-astra` 요청을 서버가 거절했고,
CLI 0.162.0은 실제 구조화 출력 probe를 완료했습니다. 이는 해당 환경의 호환성 확인이며
모델의 전반적인 품질 순위를 뜻하지 않습니다.

### 호스트 추천 검증 (미릴리스 소스)

호스트가 만든 JSON을 vault 밖에 저장합니다. 분류·태그 이름은 사용자의 목록에 있어야 합니다.

~~~json
{"category":"research","tags":["local"],"rationale":"로컬 검색 방법이 문서의 중심 주제입니다.","review_required":false}
~~~

~~~bash
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --suggestions /path/to/suggestions.json --json
~~~

JSON에는 위 네 필드만 있어야 합니다. 분류와 중복 없는 태그는 허용된 이름이어야 하며,
추천 이유는 공백뿐인 내용을 제외한 1–2,000자 문자열, `review_required`는 불리언입니다.
결과에는 `provider: "host"`, `classification_scope: "document"`가 표시됩니다.
`--suggestions`는 `classify` 전용이며, 이 호출에서 저장된 제공자 설정을 덮어쓰고 해당
제공자를 호출하지 않습니다. `none` 이외의 명시적 `--provider`와 함께 사용할 수 없습니다.
노트는 바뀌지 않습니다. 검증 통과가 추천의 정확성이나 쓰기 승인을 뜻하지는 않으며,
적용할 때는 기존 `organize` 계획·적용 절차를 사용합니다.

## 설정과 출력

노트·제공자 명령은 `--config settings.json`과 `--json`을 받습니다.
`conversations` 명령에는 `--vault`를 직접 지정하며 `--json`을 사용할 수 있습니다.
이 명령은 해당 보관함의 `.brain-openkit/conversations.json`을 별도로 관리합니다.
다음은 체크아웃 루트에 저장할 노트·제공자 설정 예시입니다.

~~~json
{
  "vault": "examples/vault",
  "cache_dir": ".cache/brain-openkit",
  "provider": "none",
  "laya_base_url": "http://127.0.0.1:8000",
  "kev_base_url": "http://127.0.0.1:8009",
  "kev_model": "kev-latest",
  "jev_base_url": "https://api.typesafe.ai",
  "jev_model": "jev-latest",
  "timeout": 10,
  "max_tokens": 1024,
  "limit": 5,
  "candidates": 20
}
~~~

명령 옵션이 JSON 설정보다, JSON 설정이 기본값보다 우선합니다. JSON의 `vault`,
`cache_dir`는 설정 파일 기준입니다. 선택적인 `base_url` 설정이나 `--base-url`은
선택한 HTTP 제공자의 주소를 덮어쓰며 Codex에서는 이 옵션을 거절합니다. HTTP API 키는 환경 변수로만 전달합니다.
`--model`은 선택한 Kev·Jev·ko-decision의 서버 모델 이름 또는 Codex 모델을 덮어쓰며, Laya는 다국어 모델을 명시적으로 사용합니다.
분류·정리·원본 노트 경로는 vault 기준이며, 입력 초안·분류 목록·평가 자료·계획 파일은
현재 디렉터리 기준입니다.

미릴리스 소스는 JSON에서 `ko_decision_base_url`(기본값
`http://127.0.0.1:8010`), `ko_decision_model`(기본값
`mmetamong/ko-decision-roberta-large`), `prompt_language`(`en` 또는 `ko`,
기본값 `en`)도 받습니다. `--model`은 서버가 이미 제공하는 모델 이름을 선택하며,
가중치를 내려받거나 교체하지 않습니다.

파일·파이프로 연결할 때도 UTF-8을 출력합니다. 재정렬 상태는 `disabled`,
`not_needed`, `complete`, `unavailable`이며, 불가능하면 BM25 결과와 이유를 반환합니다.
분류 실패 시 추천을 만들어 반환하지 않습니다.
정확한 옵션은 `brain-openkit <command> --help`에서 확인하세요.

## 품질 근거와 제약

[고정된 한국어·영어 합성 평가](benchmarks/bilingual-v1/README.md)는 노트 24개,
검색 질문 36개, 분류 평가용 holdout 노트 18개를 포함합니다. 추론 전에 정답을 작성하고
다른 에이전트가 독립 검토했으며, 사용자가 검토한 자료는 아닙니다.
Holdout 검색 질문은 개발 자료와 같은 문서에 대한 다른 표현입니다.

| Holdout 검색 질문 24개 | BM25 | Laya |
| --- | ---: | ---: |
| Recall@3 | 0.7500 | 0.7500 |
| MRR@3 | 0.7500 | 0.6042 |

Laya는 모든 재정렬 요청을 완료했지만 이번 실행에서 **역순위 지표가 낮아졌습니다.**
Holdout 분류 정확도는 0.6667, 태그 micro F1은 0.4691이며 태그 오탐 39개·누락 4개가
발생했습니다. 따라서 BM25를 기본으로 유지하고 추천을 검토합니다.
[실제 실행 결과와 한계](benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md)를 참고하세요.

- 모델 확률·신뢰도는 보정된 값을 보장하지 않으며 메타데이터 자동 적용을 위한
  보편적인 임계값도 없습니다.
- Laya 요청에는 바이트 제한과 입력 예산이 있습니다(`--max-tokens`, 기본 1024).
  **Laya의 정확한 토크나이저 사전 검증은 미구현입니다.** 보고된 입력 잘림·누락·선택지 충돌은
  거절합니다.
- ko-decision은 추론 전에 완전한 입력 쌍을 토큰화하고 512토큰 초과 입력을 거절합니다.
  선택지 간 상대 점수는 보정된 정답 확률이 아닙니다.
- BM25 후보에 없는 정답 노트는 재정렬로 찾을 수 없습니다.
  대규모 vault 성능과 일반적인 한국어·영어 품질은 아직 입증하지 않았습니다.
- 검색 평가 JSONL은 `{"query":"...","relevant":["note.md"]}` 형식이며,
  정답은 실제 vault 내부 Markdown 경로입니다. BM25·제공자 지표, 시간, fallback을
  구분해 보고합니다.
- 별도 설계 목표인 실제 vault의 사용자 검토 검색 질문 30개와
  분류·태그 예제 50개를 통한 수용 검증은 아직 남아 있습니다.

호스트 실행·런타임 버전·검증 상태는 [구현·검증 기록](docs/implementation-notes.md)에 있습니다.
[기존 설계서](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)와
[에이전트 작업 설계서](docs/superpowers/specs/2026-10-04-agent-workflows-design.md)에는
검증을 완료한 범위 이외의 의도한 동작도 포함됩니다.

## 로드맵

- [x] 원문을 보존하는 BM25 검색과 선택적 Laya 판단
- [x] Jev 어댑터·제공자별 설정과 계약 테스트
- [x] Laya·Kev 로컬 어댑터 교체와 Hugging Face 모델 설정 안내
- [x] 검토한 노트 계획·메타데이터·링크 변경, 트랜잭션, 실행 취소·복구
- [x] 원문 수집·기존 위키 채택·호스트 기반 초안 작성·조사 스킬
- [x] Claude Code·Codex 공용 스킬 8개와 읽기 전용 로컬 웹 화면
- [x] Holdout 정답을 포함한 더 넓은 한국어·영어 합성 평가
- [ ] Jev 실제 서비스 검증
- [ ] 실제 vault의 사용자 검토 검색·분류·태그 수용 검증
- [ ] Laya의 정확한 토크나이저 사전 검증과 추가 제공자 질문 형식
- [ ] Obsidian 플러그인 화면

각 기존 항목의 구현·검증 근거·남은 수용 조건은
[로드맵 근거 표](docs/roadmap-evidence.md)에 정리했습니다.

## 기여와 라이선스

CLI 환경에서 `python -m unittest discover -s tests -v`로 테스트합니다.
테스트는 임시 vault·로컬 HTTP fixture를 사용하며 실제 모델 검증은 별도입니다.
[CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

자체 코드·문서는 [MIT 라이선스](LICENSE)를 따릅니다. 외부 코드·가중치·호스팅 서비스는
각자의 라이선스·약관을 따릅니다.
[AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)에서
영감을 받아 코드·템플릿을 복사하지 않고 독립 구현했습니다.
Obsidian, Laya, Kev, TypeSafe, claude-obsidian과 제휴한 프로젝트가 아닙니다.
[ATTRIBUTION.md](ATTRIBUTION.md)를 참고하세요.
