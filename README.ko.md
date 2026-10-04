<h1 align="center">Brain OpenKit</h1>

<p align="center">
  <strong>Obsidian을 위한 오픈소스 세컨드 브레인 도구 모음.</strong><br>
  판단 제공자를 교체할 수 있도록 구성한 Obsidian 로컬 검색·정리 도구.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2563eb" alt="MIT 라이선스"></a>
  <img src="https://img.shields.io/badge/status-alpha-d97706" alt="알파">
  <a href="https://huggingface.co/convaiinnovations/laya-multilingual"><img src="https://img.shields.io/badge/optional%20model-Laya-0f766e" alt="선택적 모델: Laya"></a>
</p>

<p align="center">
  <a href="README.md">English</a> · 한국어<br>
  <a href="#현재-기능">소개</a> · <a href="#소스에서-설치">설치</a> ·
  <a href="#선택적-laya-서버">Laya</a> · <a href="#로드맵">로드맵</a> ·
  <a href="CONTRIBUTING.md">기여하기</a>
</p>

> **소스에서 설치하는 알파 버전(0.1.0a1)입니다.** 읽기 전용 CLI, BM25 검색,
> Laya 어댑터와 테스트를 구현했습니다. Laya는 합성 예제로 확인했으며 실제 vault의
> 검색 품질은 아직 검증하지 않았습니다. PyPI 배포 패키지는 없습니다.
> CLI 코드가 포함된 소스 체크아웃에서 설치하세요.

Brain OpenKit은 Markdown 문단을 찾고 원문 경로, 줄 번호, 발췌를 표시합니다.
**기본 검색은 모델이나 API 키가 필요 없는 BM25입니다.** 로컬
[Laya](https://github.com/NandhaKishorM/laya) 서버를 선택하면 재정렬과
기존 분류·태그 목록에 따른 추천을 사용할 수 있습니다.

## 현재 기능

- 수정·삭제된 노트를 반영하고 1부터 시작하는 시작·끝 줄 번호와 원문을 반환합니다.
- Laya 다국어 모델로 재정렬하며 후보 하나라도 실패하면 전체 BM25 순서를 유지합니다.
- 최대 10개 분류 중 하나를 고르고 최대 30개 태그를 각각 판단합니다.
  문단 사이의 분류 충돌도 표시합니다.
- 서버 상태 확인, 선택적인 합성 추론, 정답이 있는 검색 사례 평가를 제공합니다.

원본 노트는 읽기만 하고 SQLite 인덱스는 별도 캐시에 저장합니다.
제공자 계약은 현재 **choose만 구현**했습니다. Jev, 일반 score·noul 질문,
노트 수정, 생성형 기능, Obsidian 화면은 후속 범위입니다.

~~~mermaid
flowchart LR
    A[Markdown vault] --> B[로컬 인덱스]
    B --> C[BM25 후보 검색]
    C --> D[기본 BM25 결과]
    C -. 직접 선택 .-> E[Laya 로컬 서버]
    E --> F[모든 판단 검증]
    F --> G[원문 발췌·추천]
    D --> G
    F -. 모델 실패 .-> D
~~~

## 소스에서 설치

**Python 3.11 이상**이 필요합니다. CLI 코드가 포함된 체크아웃 루트에서 다음
macOS/Linux 명령을 실행하세요. 필요하면 설치된 더 최신 Python 실행 파일로 바꿉니다.

~~~bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
brain-openkit --version
~~~

Windows는 PowerShell에서 `.venv\Scripts\Activate.ps1`로 활성화합니다.
CLI에는 외부 런타임 의존성이 없지만 설치 중 빌드 도구를 다운로드할 수 있습니다.
Laya는 별도로 설치하는 선택적 런타임입니다.

## 포함된 노트로 실행

CLI 환경을 활성화한 상태에서 체크아웃 루트에서 실행합니다.

~~~bash
brain-openkit index --vault examples/vault
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault
brain-openkit search "reading journal comets" --vault examples/vault --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --json
~~~

검색과 평가는 기본적으로 `--provider none`을 사용하고 인덱스를 갱신합니다.
모델 서버가 필요하지 않습니다. 기본 캐시는 현재 디렉터리의 `.cache/brain-openkit`이며
`--cache-dir`로 바꿉니다. [합성 노트 4개](examples/README.md)는 실행 확인용입니다.

## 선택적 Laya 서버

**별도 환경과 터미널**을 사용합니다. 확인한 런타임은 Laya **0.3.26**,
Python **3.12**, CPU 추론입니다.

~~~bash
python3.12 -m venv .venv-laya
source .venv-laya/bin/activate
python -m pip install "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=0 \
laya-serve
~~~

첫 추론 때 모델을 적재하는 설정입니다. `LAYA_MODELS`는 미리 적재할 모델 목록이며
접근 제한이 아닙니다. Brain OpenKit은 `multilingual`을 명시적으로 요청하므로
첫 추론 때 해당 가중치를 다운로드·적재합니다. 최초 의존성·가중치 다운로드에는
네트워크와 디스크 공간이 필요하며 모델 런타임은 추가 메모리를 사용합니다.

`.venv`가 활성화된 **CLI 터미널**에서 실행합니다.

~~~bash
brain-openkit doctor
brain-openkit doctor --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --json
~~~

`doctor`는 상태 확인만 하며 `--probe`는 합성 추론과 필요한 다운로드를 수행합니다.
분류는 기본적으로 Laya를 사용합니다. 상대 노트 경로는 **--vault 내부 기준**이므로
위 명령에서는 `local-search.md`를 씁니다. 분류 목록·평가 파일 경로는 현재 디렉터리 기준입니다.

첫 적재가 기본 제한 시간 10초를 넘으면 적재 후 재시도하거나 `--timeout 120`을 지정합니다.
다른 서버는 `--base-url`로 선택합니다. 서버 인증을 설정했다면 두 터미널의
`LAYA_API_KEY`에 같은 키를 넣습니다. 이 공개 가중치에는 Hugging Face 토큰이나 Jev 키가 필요하지 않습니다.

## 설정과 출력

각 하위 명령은 `--config settings.json`, `--json`을 받습니다.
체크아웃 루트에 저장할 설정 예시입니다.

~~~json
{
  "vault": "examples/vault",
  "cache_dir": ".cache/brain-openkit",
  "provider": "none",
  "base_url": "http://127.0.0.1:8000",
  "timeout": 10,
  "max_tokens": 1024,
  "limit": 5,
  "candidates": 20
}
~~~

~~~bash
brain-openkit search "reading journal" --config settings.json --json
brain-openkit classify local-search.md --config settings.json --provider laya --taxonomy examples/taxonomy.json --json
~~~

명령 옵션이 JSON 설정보다, JSON 설정이 기본값보다 우선합니다.
JSON의 `vault`, `cache_dir`는 설정 파일 기준입니다.
키는 JSON이나 vault 대신 `LAYA_API_KEY`에 보관합니다.
제공자는 `none`, `laya`이며 모델 경로는 `multilingual`로 고정합니다.

재정렬 상태는 `disabled`, `not_needed`, `complete`, `unavailable`입니다.
불가능하면 BM25 결과와 실패 이유를 반환하며 분류 실패 시 추천을 만들어 반환하지 않습니다.
JSON은 원문 위치, 판단, 처리한 실행 오류를 보존합니다.
옵션은 `brain-openkit <command> --help`에서 확인하세요.

## 제약과 평가

- 모델 확률은 순위를 정하는 신호이며 보정된 확률을 보장하지 않습니다.
  신뢰도 임계값에 따라 노트를 자동 변경하지 않습니다.
- 요청 바이트 크기와 입력 예산을 제한합니다(`--max-tokens`, 기본 1024).
  **정확한 토크나이저 기반 사전 검증은 미구현입니다.**
  응답에 입력 누락, 질문 잘림, 선택지 충돌이 표시되면 거절합니다.
- 기본 주소에서는 로컬 서버가 추론합니다. 원격 `--base-url`을 선택하면 문단이
  해당 서버로 전송됩니다. 클라우드로 자동 전환하지 않습니다.
- 평가 JSONL 형식은 `{"query": "...", "relevant": ["note.md"]}`입니다.
  정답은 vault 내부의 실제 Markdown 경로여야 합니다.
  BM25와 요청한 제공자의 recall@k, k개 결과 내 MRR, 시간, fallback 횟수를 구분합니다.
  포함된 4개 질문은 한국어·영어 품질이나 BM25 대비 개선을 입증하지 않습니다.

[구현·검증 기록](docs/implementation-notes.md)에 확인한 버전과 결과를 정리했습니다.
[기존 설계서](docs/superpowers/specs/2026-10-04-obsidian-laya-design.md)에는 후속 기능도 포함되며
현재 CLI 사용법은 이 README를 기준으로 확인하세요.

## 로드맵

- [x] 원문 위치를 보존하는 읽기 전용 인덱싱과 BM25 검색
- [x] 선택적 Laya 다국어 재정렬 및 분류·태그 추천
- [x] 소스 설치 CLI, 자동 테스트, 실행 확인용 평가 기능
- [ ] 별도 정답 자료로 더 넓은 한국어·영어 평가
- [ ] Jev 어댑터와 제공자별 설정
- [ ] 검토한 메타데이터·링크 변경 반영과 복구
- [ ] 자료 수집, 위키 생성, 선택적 생성형 모델
- [ ] Obsidian 플러그인 또는 로컬 웹 화면

## 기여하기

CLI 환경에서 `python -m unittest discover -s tests -v`로 테스트합니다.
테스트는 임시 vault와 로컬 HTTP fixture를 사용하며 Laya 가중치가 필요하지 않습니다.
실제 모델 검증은 별도입니다. [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
비공개 노트와 키를 기여 자료에 포함하지 마세요.

## 라이선스와 출처

자체 코드·문서는 [MIT 라이선스](LICENSE), 외부 코드·가중치는 각자의 라이선스를 따릅니다.

[AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)의
원문과 연결된 흐름에서 영감을 얻어 독립 구현했습니다.
Obsidian, Laya, TypeSafe, claude-obsidian과 제휴한 프로젝트가 아닙니다.
참조 버전과 라이선스 구분은 [ATTRIBUTION.md](ATTRIBUTION.md)에 있습니다.
