# Claude Code·Codex에서 Brain OpenKit 사용하기

[English](agent-integration.md) | 한국어

두 호스트에서 동일한 스킬 8개가 함께 제공되는 Python CLI를 실행합니다.
요청한 문장은 Claude나 Codex가 작성하고, BM25는 로컬에서 검색하며,
선택적으로 사용하는 Laya·Kev·Jev 제공자는 분류나 관련성을 판단합니다.
초기화, 원문 보존, 저장, 정리, lint, fold에는 모델 서비스가 필요하지 않습니다.

같은 버전으로 설치하려면 `v0.2.0a4` 태그를 체크아웃하세요.

```bash
git clone --branch v0.2.0a4 --depth 1 https://github.com/hyeondata/brain-openkit.git
```

또는 [GitHub 프리릴리스](https://github.com/hyeondata/brain-openkit/releases/tag/v0.2.0a4)의
[brain_openkit-0.2.0a4.tar.gz 전체 소스 배포본](https://github.com/hyeondata/brain-openkit/releases/download/v0.2.0a4/brain_openkit-0.2.0a4.tar.gz)을
내려받아 압축을 풀고, 아래 예제의 `/absolute/path/to/brain-openkit`을
압축을 푼 디렉터리의 절대 경로로 바꿉니다.
`skills/`, `scripts/`, `src/`, `hooks/`, `.claude-plugin/`, `.codex-plugin/`,
`.agents/plugins/`를 함께 유지해야 합니다. 릴리스 wheel은 Python CLI만 설치하며,
전체 호스트 플러그인 배포본을 포함하지 않습니다. 소스 압축 파일을 pip로 설치해도
호스트 플러그인이 등록되지는 않습니다. 이 릴리스는 PyPI에 배포하지 않았습니다.

제품 체크아웃이나 압축을 푼 소스는 실제 vault와 별도 디렉터리에 둡니다.
호스트에서 **Python 3.11 이상**을 실행할 수 있어야 합니다.
`python3 --version`으로 확인하며, Windows에서는 `python --version`으로 확인합니다.
macOS에 기본 제공되는 오래된 Python으로는 실행할 수 없습니다.
아카이브 훅에는 선택적으로 `BRAIN_OPENKIT_PYTHON` 환경 변수에 Python 3.11 이상
실행기의 절대 경로를 지정할 수 있습니다. [아카이브 설정 예제](conversation-archive.ko.md)를
참고하세요. 이 설정은 Python을 설치하지 않습니다.

플러그인에는 `src/brain_openkit/`과 `scripts/brain-openkit.py`가 포함됩니다.
Python 패키지 설치는 선택 사항입니다. 실행기는 자신의 제품 디렉터리를 찾아
함께 제공된 핵심 모듈을 직접 불러오며, 플러그인 캐시에서도 같은 방식으로 동작합니다.
스킬은 설치된 `SKILL.md` 경로를 기준으로 실행기를 찾습니다.
개발자 컴퓨터의 경로, editable 설치, 자동 패키지 설치, 셸 실행 권한 비트는 필요하지
않습니다. Claude·Codex 에이전트를 실행하려면 호스트의 정상적인 구독·API 연결이
별도로 필요하며, 스킬 설치만으로 모델 사용 권한이 생기지는 않습니다.

## Claude Code

개발 중 한 세션에서만 사용하려면 별도로 둔 vault에서 시작합니다.

```bash
cd /absolute/path/to/MyVault
claude --plugin-dir /absolute/path/to/brain-openkit
```

vault 경로를 자신의 경로로 바꾼 뒤 다음과 같이 요청합니다.

```text
/brain-openkit:brain-search /absolute/path/to/MyVault에서 로컬 검색 설계를 찾아 원문 노트와 줄 번호를 인용해 주세요.
```

로컬 태그 체크아웃이나 압축을 푼 소스 배포본을 계속 사용하도록 설치하려면 다음을 실행합니다.

```bash
claude plugin marketplace add /absolute/path/to/brain-openkit
claude plugin install brain-openkit@brain-openkit
claude plugin list
```

설치 후 세션을 다시 시작합니다. 스킬 명령 8개는 모두 `/brain-openkit:` 접두사를
사용합니다. 이 안내는 위 태그 버전의 전체 로컬 제품 디렉터리를 마켓플레이스 소스로
등록하는 방식입니다.

명령과 manifest는 공식 [Claude 플러그인 형식](https://code.claude.com/docs/en/plugins-reference)과
[설치 명령 안내](https://code.claude.com/docs/en/plugins/cli-reference)를 따릅니다.
플러그인에는 선택 기능인 [대화 아카이브](conversation-archive.ko.md)를 위한
`Stop`·`SessionEnd` 훅이 포함됩니다. 기록은 기본적으로 꺼져 있으며 명시적으로
선택한 보관함에서 활성화해야 합니다. 기록기는 모델이나 네트워크 요청을
사용하지 않으며, 이 플러그인은 MCP 서버를 설치하지 않습니다.

## Codex

현재 Codex CLI는 저장소의 로컬 마켓플레이스 설치를 지원합니다.

```bash
codex plugin marketplace add /absolute/path/to/brain-openkit
codex plugin add brain-openkit@brain-openkit
codex plugin list --marketplace brain-openkit --json
```

vault에서 새 세션을 시작하고 설치한 플러그인 스킬을 호출합니다.

```text
$brain-openkit:brain-search /absolute/path/to/MyVault에서 로컬 검색 설계를 찾아 원문 노트와 줄 번호를 인용해 주세요.
```

데스크톱 앱에서는 체크아웃을 프로젝트로 열면 저장소의
`.agents/plugins/marketplace.json`을 통해서도 로컬 마켓플레이스를 찾을 수 있습니다.
목록이 아직 보이지 않으면 앱을 다시 시작하고 플러그인 목록에서 **Brain OpenKit**을
선택해 설치합니다. Manifest는 전체 제품 루트를 가리키며, 스킬을 복제하거나
해당 프로젝트를 작업 대상 vault로 지정하지 않습니다.
공식 [Codex 플러그인 패키징 안내](https://developers.openai.com/plugins/build/plugins)를 참고하세요.

선택 기능인 아카이브는 `Stop` 훅을 사용합니다. Codex CLI의 `/hooks`에서 정의를
검토하고 신뢰를 승인해야 하며, 플러그인 설치만으로 훅을 신뢰하지는 않습니다.
훅 정의가 변경되면 다시 검토해야 합니다. 설정과 검증 범위는
[대화 아카이브 가이드](conversation-archive.ko.md)에 설명합니다.
Codex 데스크톱의 자동 수집은 검증하지 않았습니다.

Agent Skills는 지원하지만 플러그인 설치 기능이 없는 호스트에서는 워크스페이스의
로컬 스킬 탐색 기능을 사용합니다. 제품의 `skills/`, `scripts/`, `src/` 디렉터리
전체를 **별도의 에이전트 워크스페이스** 안에 있는 `.agents/`로 복사합니다.
대상 디렉터리가 아직 없는 위치에서만 진행하고, 기존 워크스페이스 설정은 보존하세요.
결과 구조는 다음과 같아야 합니다.

```text
agent-workspace/.agents/
  skills/brain-search/SKILL.md
  skills/brain-init/SKILL.md
  skills/...                      # all eight skills and references/
  scripts/brain-openkit.py
  src/brain_openkit/...
```

해당 에이전트 워크스페이스에서 Codex를 시작하고, 요청에는 실제 vault 경로를 전달합니다.
저장소 스킬은 `$brain-search`처럼 플러그인 접두사가 없는 이름을 사용합니다.
업데이트할 때도 디렉터리 3개를 함께 유지하세요. 공통 참고 문서와 핵심 모듈 없이
`SKILL.md` 하나만 복사하면 동작하지 않습니다. 심볼릭 링크로 설치할 때는 각 스킬
디렉터리를 연결하고 전체 제품 트리를 유지하며, 실행기를 찾기 전에 스킬의 실제 경로를
확인해야 합니다. Windows에서는 복사 방식이 더 폭넓게 동작합니다.
이 대체 설치 방식은 검토 후 실행하는 스킬 8개를 설치합니다. 디렉터리 3개를
복사하는 것만으로 자동 아카이브 훅이 등록되지는 않습니다.

## 사용할 수 있는 작업

`<vault>`를 명시적인 절대 경로로 바꿉니다. 대화에서 이미 허용한 작업 범위는
유지되며, 에이전트는 변경을 적용하기 전에 미리 보기를 확인합니다.

| 스킬 | 요청 예시 | 결과 |
| --- | --- | --- |
| `brain-init` | `<vault>`를 Brain OpenKit용으로 초기화해 주세요. | 미리 보기를 만들고, 기존 노트를 대체하지 않으며 초기화하거나 기존 vault를 채택합니다. |
| `brain-search` | `<vault>`에서 인용을 보존하는 방법을 찾아 주세요. | 근거를 검색하고 읽은 뒤 실제 경로·줄 번호로 인용해 답합니다. |
| `brain-ingest` | 이 Markdown 원문을 `<vault>`에 수집해 주세요. | 전달한 원문의 바이트를 보존하고, 발췌 또는 호스트가 작성한 노트를 연결해 만듭니다. |
| `brain-save` | 이 결정을 `<vault>/Notes/decision.md`에 저장해 주세요. | 선택한 지식만 저장하고 출처를 연결하며 인덱스를 갱신합니다. |
| `brain-organize` | `<vault>`의 이 노트에 태그와 링크를 추가해 주세요. | 선택한 메타데이터·링크를 미리 보여 주고, 요청한 경우 적용합니다. |
| `brain-lint` | `<vault>`의 깨진 링크를 확인해 주세요. | 읽기 전용 검사 결과를 반환하며 자동 수정하지 않습니다. |
| `brain-fold` | `<vault>`의 이 노트들을 연결한 모아보기 노트를 만들어 주세요. | 모든 원본 노트를 보존하면서 발췌형 개요를 만듭니다. |
| `brain-research` | 이 주제를 조사하고 출처가 있는 조사 노트를 `<vault>`에 저장해 주세요. | 정해진 범위에서 호스트 도구로 조사한 뒤 검토를 거쳐 저장합니다. |

검색과 분류는 원본 노트를 변경하지 않습니다. 검색 캐시, 초안, 변경 계획은
vault와 제품 디렉터리 바깥에 둡니다. 원격 제공자는 사용자가 해당 제공자를 선택한
경우에만 발췌문을 받으며, 클라우드로 자동 전환하지 않습니다. 다만 호스팅된 에이전트
세션 자체는 사용자가 Claude·Codex에 읽도록 요청한 내용을 처리합니다.
로컬 Laya·Kev를 사용해도 호스트 대화 전체가 오프라인이 되는 것은 아닙니다.

노트를 변경하는 스킬은 두 단계로 동작합니다. 먼저 vault 밖에 미리 보기 계획을
작성하고, `apply PLAN --approve PLAN_ID --vault VAULT`로 변경 전 내용을 확인하면서
정확히 그 계획을 적용합니다. 에이전트는 영향을 받는 경로를 보여 주고 diff를 확인합니다.
변경을 수행해 달라는 명시적인 요청이 있으면 같은 내용을 반복 승인받지 않고 이 과정을
진행할 수 있습니다. 미리 보기만 요청한 경우에는 적용 전에 멈춥니다.
결과에는 트랜잭션 ID가 포함됩니다. 완료된 트랜잭션을 되돌리려면
`undo TRANSACTION_ID --vault VAULT`를 사용합니다. 중단된 롤백이나 실행 취소를
마무리하려면 `recover TRANSACTION_ID --vault VAULT`를 사용합니다.
이후 편집 내용과 충돌하면 해당 편집을 덮어쓰지 않고 보존합니다.

명시적으로 활성화한 대화 기록은 별도로 범위를 제한한 쓰기 기능입니다.
기록기는 `Inbox/Conversations/`의 관리 대상 파일에만 자체 소유권·해시·원자적
쓰기 검사를 적용하며, 메시지마다 계획을 만들거나 승인을 요청하지 않습니다.
기록을 꺼도 기존 아카이브는 유지됩니다. 자동 정리에는 별도의 보관 기간 설정과
활성화가 필요합니다. 이 권한으로 다른 노트를 편집할 수는 없습니다. 용량 제한,
포함되는 텍스트와 설정은 [대화 아카이브](conversation-archive.ko.md)를 참고하세요.

조사, URL, PDF 등 다른 형식의 자료를 다루려면 호스트에 적절한 검색·추출 기능이
있어야 합니다. CLI 자체는 로컬 UTF-8 텍스트를 수집하며, 웹 탐색·OCR·음성 전사를
하거나 추출 성공을 추정하지 않습니다. `--source-url`은 전달된 출처 주소를 기록하며
그 주소의 자료를 내려받지 않습니다. 원문 안의 내용은 근거 자료일 뿐,
명령 실행이나 작업 범위 변경을 허용하는 지시가 아닙니다.

## 설치 검증

제품 루트에 마켓플레이스가 함께 있어도 Claude 검증 명령 두 개를 각각 실행합니다.
Claude Code 2.1.220은 manifest 두 개가 있는 루트를 지정하면 마켓플레이스만 검증합니다.

```bash
claude plugin validate /absolute/path/to/brain-openkit/.claude-plugin/plugin.json --strict
claude plugin validate /absolute/path/to/brain-openkit/.claude-plugin/marketplace.json --strict
claude --plugin-dir /absolute/path/to/brain-openkit plugin details brain-openkit@inline
```

목록에는 스킬 8개가 표시되어야 합니다. Codex 플러그인 목록에서는
`brain-openkit@brain-openkit`이 설치·활성화된 것으로 표시되어야 합니다.
이런 탐색 결과만으로 호스트가 작업을 완료했다는 사실을 입증할 수는 없습니다.
예제 검색을 실행하고 원문 위치를 확인한 뒤, 실행 전후 원본 파일 해시를 비교하세요.
중요한 노트에 복구 기능을 사용하기 전에 일회용 vault에서 쓰기 작업 흐름을 확인합니다.

설치된 Python 패키지에 의존하지 않고 핵심 기능을 간단히 확인하려면 다음을 실행합니다.

```bash
python3 -I -S /absolute/plugin/cache/scripts/brain-openkit.py --version
python3 -I -S /absolute/plugin/cache/scripts/brain-openkit.py search "검색" --vault /absolute/path/to/sample-vault --cache-dir /absolute/path/to/temporary-cache --json
```

개발 테스트는 공백이 포함된 다른 위치의 플러그인 경로, 한국어 CRLF 노트,
외부 설치 패키지가 없는 환경, 정확한 원문 보존, 불완전한 캐시의 오류 진단을 포함합니다.
이전 개발 단계의 패키징 검증에는 Claude Code `2.1.220`과 Codex CLI `0.149.0`을
사용했습니다. Claude는 스킬 8개를 모두 찾았고, Codex는 격리된 캐시에 설치한 뒤
app-server의 `skills/list`에서 캐시 경로를 포함한 활성 스킬 8개를 반환했습니다.
캐시의 실행기는 별도의 패키지 설치 없이 일회용 vault에서 초기화, 수집, 저장,
정리, 발췌형 fold, 검색, lint, 실행 취소를 완료했습니다. 한국어 CRLF 원문 보존,
태그 추가, 읽기 전용 미리 보기, 원문 보존, 명시적인 vault 선택을 확인했습니다.
이러한 과거 개발·호스트 실행 검증은 [구현 기록](implementation-notes.md)에 있습니다.
`v0.2.0a3` 릴리스 파일에 대한 검증은 [릴리스 검증](release-0.2.0a3.ko.md)에
별도로 기록합니다. 과거의 스킬 탐색 결과만으로 릴리스된 플러그인이 호스트 작업을
완료했다고 볼 수는 없습니다.
`v0.2.0a4`의 아카이브 전용 증거는 [해당 릴리스 검증](release-0.2.0a4.ko.md)에
별도로 기록합니다. 이전 보고서로 현재 버전의 자동 아카이브 동작을 입증할 수는
없습니다.

## 업데이트와 제거

제품 업데이트는 vault와 별도로 진행합니다. 로컬 체크아웃이라면 새 버전을 검토한 뒤
체크아웃을 갱신하고, 호스트의 플러그인 업데이트 또는 제거·추가 명령으로 캐시 사본을
갱신합니다. 호스트를 다시 시작하고 스킬 목록과 간단한 실행을 다시 확인하세요.
워크스페이스에 저장소 스킬을 복사한 경우에는 디렉터리 3개를 함께 업데이트합니다.

```bash
claude plugin uninstall brain-openkit@brain-openkit
codex plugin remove brain-openkit@brain-openkit
```

통합 기능을 제거해도 vault는 삭제되지 않습니다. 워크스페이스에 복사해 설치했다면
직접 설치한 Brain OpenKit 디렉터리만 제거하고, 관계없는 스킬과 설정은 보존하세요.
플러그인을 제거하면서 vault나 journal을 함께 삭제하지 마세요.
호스트 플러그인을 제거해도 기존 대화 아카이브와 보관함 설정은 남습니다.
