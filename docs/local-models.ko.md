# 로컬 판단 모델

[English](local-models.md) | 한국어

Laya·Kev·ko-decision은 동일한 Brain OpenKit 검색, 분류, 평가 명령을 사용합니다.
`--provider laya`, `--provider kev`, `--provider ko-decision`으로 선택합니다. 모두
Hugging Face에서 공개 가중치를 내려받아 컴퓨터에서 추론을 실행할 수 있으며,
호스팅 추론 서비스 구독이나 Hugging Face 토큰이 필요하지 않습니다.

Laya·Kev는 공식 런타임을, ko-decision은 Brain OpenKit의 선택적 로컬 서버를
사용합니다. Hugging Face는 공통 모델
레지스트리이고, Brain OpenKit은 공통 CLI를 제공합니다. 일반적인 텍스트 생성
엔드포인트로는 이 의사결정 모델 서버들을 대체할 수 없습니다. 핵심 CLI는
Python 3.11+ 표준 라이브러리만 사용하는 런타임을 유지하므로, 모델 의존성은 별도로 설치하세요.

**ko-decision과 `--prompt-language`는 미릴리스 소스 기능입니다.**
`v0.2.0a4` 태그와 릴리스 파일에는 없습니다. 이 변경이 포함된 체크아웃에서
설치하세요. 이 프로젝트는 PyPI에 배포하지 않았습니다.

| 선택 | 가중치 | 기본 로컬 엔드포인트 | 서버 모델 이름 |
| --- | --- | --- | --- |
| `--provider laya` | [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya), `multilingual` 하위 폴더 | `http://127.0.0.1:8000` | `multilingual`, 명시적으로 전송 |
| `--provider kev` | [`jaredpalmer/kev-0.8b`](https://huggingface.co/jaredpalmer/kev-0.8b), 기본 체크포인트 | `http://127.0.0.1:8009` | `kev-latest` |
| `--provider ko-decision` | [`mmetamong/ko-decision-roberta-large`](https://huggingface.co/mmetamong/ko-decision-roberta-large/tree/dfd606fff30d52963c0073659ff9a8f6bf1fce6d), 고정된 선택적 체크포인트 | `http://127.0.0.1:8010` | `mmetamong/ko-decision-roberta-large` |

`kev-latest`는 서버에 로드된 체크포인트의 API 별칭입니다. Hugging Face의
최신 가중치를 뜻하지 않습니다. Brain OpenKit의 `--model`은 Kev/Jev/ko-decision의
서버 모델 이름을 재정의하며, 체크포인트를 내려받거나 교체하지 않습니다.
함께 제공되는 `scripts/serve-kev.py` 실행 스크립트의 기본값은 기록된
`v1.0` 리비전인
`jaredpalmer/kev-0.8b@bf75a6a8848ea6960ff2ed108d9ed44c2941174f`입니다.
가중치를 바꾸려면 다른 `--run` 값으로 다시 시작하세요.
분류와 `doctor`의 기본 제공자는 Kev이며, 검색과 평가의 기본값은
로컬 BM25(`--provider none`)입니다. Kev로 순위를 재정렬하려면
`--provider kev`를, Laya를 명시적으로 사용하려면 `--provider laya`를 선택하세요.

아래 명령은 macOS 기준 예제이며, Windows·Linux에서는 이번 변경을 검증하지 않았습니다.
Laya·Kev 설정에는
[uv](https://docs.astral.sh/uv/)와 Git을, ko-decision에는 Python의 `venv`와 pip를
사용합니다. 최초 설치·다운로드에는 네트워크 연결과 충분한 로컬 디스크 공간·메모리가
필요합니다. 서버는 루프백 주소에 바인딩됩니다. 사용을 마치면 Ctrl+C로 서버를 중지하세요.

## Laya 다국어 모델

별도 터미널에서 보관함 밖에 런타임 디렉터리를 만드세요.

```bash
mkdir -p ../brain-openkit-laya-runtime
cd ../brain-openkit-laya-runtime
uv venv --python 3.13 .venv-laya
uv pip install --python .venv-laya/bin/python "laya[serve]==0.3.26"
LAYA_HOST=127.0.0.1 LAYA_PORT=8000 \
LAYA_DEVICE=cpu LAYA_THREADS=4 \
LAYA_MODELS=multilingual LAYA_DEFAULT_MODEL=multilingual LAYA_PRELOAD=1 \
LAYA_REVISION=7b928d828b7b0e022f929d9bd2e44165aa270148 \
.venv-laya/bin/laya-serve
```

이 명령은 지정된 리비전의 다국어 체크포인트를 미리 로드합니다. 최초 다운로드
크기는 약 647 MiB입니다. `LAYA_MODELS`는 미리 로드할 모델을 제어하며,
접근을 제한하지는 않습니다. Brain OpenKit은 모든 추론 호출에서
`multilingual`을 명시적으로 요청합니다. 첫 요청 때까지 로드를 미루려면
`LAYA_PRELOAD=0`을 사용하고, 이 경우 클라이언트의 시간 제한을 더 길게 설정하세요.
서버 인증을 활성화하면 서버와 CLI 환경에 동일한 `LAYA_API_KEY`를 설정하세요.

## Kev 0.8B 기본값

별도 터미널에서 Brain OpenKit 체크아웃 루트부터 시작하세요. 보관함 밖,
체크아웃 옆에 공식 런타임을 설치합니다.

```bash
BRAIN_OPENKIT_ROOT="$PWD"
git clone https://github.com/jaredpalmer/kev.git ../brain-openkit-kev-runtime
cd ../brain-openkit-kev-runtime
git checkout --detach fe64b1274ea7f80d4095866df90666abb03e9cf6
uv sync --extra serve --no-dev --python 3.12
uv run --no-sync python "$BRAIN_OPENKIT_ROOT/scripts/serve-kev.py"
```

마지막 줄이 기본 시작 명령입니다. 지정된 리비전의 Kev 0.8B 체크포인트를
선택하고 `127.0.0.1:8009`에 바인딩합니다. 처음 시작할 때 의사결정 어댑터와
Qwen3.5-0.8B-Base 가중치를 내려받습니다. 이 스크립트는 해당 환경에 설치된
공식 Kev 런타임을 사용하며, 백엔드 선택은 런타임에 맡깁니다. 여기에는
호환되는 Apple Silicon 모델에서 MLX를 자동으로 선택하는 동작도 포함됩니다.

선택한 어댑터는 기본 모델도
`Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`로 고정하며,
temperature `2.3510958125672174`를 저장합니다. 이 설정에서는 두 모델의 리비전이 모두 고정됩니다.

실행 스크립트의 `--host`, `--port`, `--run`으로 시작 기본값을 재정의할 수 있습니다.
공식 런타임의 기본값은 `KEV_TRUNCATE_STATES=0`이므로 크기를 초과한 상태 입력은
거부됩니다. 출처에 근거한 판단을 위해 잘라내기 기능을 비활성화한 상태로 유지하세요.
이전 0.5B 실행에서는 `KEV_BACKEND=torch`와 `KEV_DTYPE=fp32`를 사용했을 수 있습니다.
기본 0.8B 설정에서는 이 재정의 값을 생략하세요.

로컬 Kev는 기본적으로 인증을 사용하지 않습니다. 서버에 `KEV_API_KEY`를 설정했다면
CLI 환경에도 동일한 값을 비공개로 설정하세요. Kev와 TypeSafe Jev는
별개의 프로젝트이며, 로컬 Kev에는 TypeSafe 서비스 키가 필요하지 않습니다.

[0.8B 검증 보고서](kev-08-verification-2026-10-05.md)에 체크포인트,
로드된 런타임, 개별 기능 검사 결과가 기록되어 있습니다. 오프라인에서 다시 사용하려면
먼저 온라인에서 정상적으로 시작되는 것을 확인하고, 전체 모델 캐시를 보존한 뒤,
이후 서버를 시작할 때 `HF_HUB_OFFLINE=1`을 추가하세요.

### 선택 사항: 기존 Kev 0.5B

이전 [0.5B 체크포인트](https://huggingface.co/jaredpalmer/kev-0.5b)는
명시적인 재정의를 통해 계속 사용할 수 있습니다. 같은 포트를 다시 사용한다면
먼저 0.8B 서버를 중지하고, Kev 런타임 디렉터리에서 다음을 실행하세요.

```bash
TORCH_FORCE_WEIGHTS_ONLY_LOAD=1 KEV_BACKEND=torch KEV_DTYPE=fp32 \
uv run --no-sync python "$BRAIN_OPENKIT_ROOT/scripts/serve-kev.py" \
  --run jaredpalmer/kev-0.5b@edf1dc6d7f8d983c0adfd251e80a686e5539fc61
```

[과거 0.5B 검사](model-verification-2026-10-05.md)에서는 Torch/MPS
float32, Qwen2.5-0.5B 기본 모델 리비전
`060db6499f32faf8b98477b0a26969ef7d8b9987`, 어댑터 temperature `1.0`을 사용했습니다.
이 어댑터의 메타데이터는 기본 모델 리비전을 고정하지 않으므로, 나중에 처음 설치하면
다른 기본 모델로 결정될 수 있습니다. 오프라인 재사용에는 가중치 파일뿐 아니라
캐시된 기본 브랜치 참조도 필요합니다. 이 기존 모델의 결과는 기본 0.8B 모델의
검증 근거와 구분해야 합니다.

## ko-decision (미릴리스 소스)

이 연동 기능을 포함한 Brain OpenKit 체크아웃에서 시작하세요. 보관함 밖,
체크아웃 옆에 별도 환경을 만듭니다.

```bash
python3.13 -m venv ../brain-openkit-ko-decision-runtime
../brain-openkit-ko-decision-runtime/bin/python -m pip install '.[ko-decision]'
../brain-openkit-ko-decision-runtime/bin/brain-openkit-serve-ko-decision \
  --device cpu --threads 4 --batch-size 4 --port 8010 \
  --cache-dir ../brain-openkit-ko-decision-cache
```

이 선택적 extra는 해당 환경에 Brain OpenKit과 함께 `torch>=2.6,<3`,
`transformers>=4.57,<6`을 설치합니다. 핵심 CLI에는 필수 모델 의존성이 없습니다.
소스 개발 중에는 같은 옵션을 붙여
`../brain-openkit-ko-decision-runtime/bin/python scripts/serve-ko-decision.py`로도
실행할 수 있습니다. 두 실행 방법 모두 체크아웃 루트 기준입니다.

서버는 `mmetamong/ko-decision-roberta-large`의
`dfd606fff30d52963c0073659ff9a8f6bf1fce6d` 리비전을 적재한 뒤 요청을 받습니다.
최초 실행은 Hugging Face에서 해당 체크포인트와 토크나이저를 내려받습니다.
기본 주소는 `127.0.0.1`이며 루프백 주소만 허용합니다. 옵션 기본값은
`--device auto`, `--threads 4`, `--batch-size 4`, `--port 8010`입니다.
`auto`는 사용 가능한 장치를 CUDA, MPS, CPU 순으로 선택하며, `cpu`, `mps`,
`cuda`를 명시할 수도 있습니다. Apple M1 Max·메모리 64 GiB에서 CPU와 MPS
float32를 모두 검증했으며, CPU 스레드 4개와 선택지 배치 크기 4를 사용했습니다.
Python 3.13.1, Torch 2.14.1, Transformers 5.18.0,
huggingface-hub 1.33.0 환경입니다. MPS 실행을 재현하려면 `--device cpu`를
`--device mps`로 바꾸세요. 영어·한국어 프롬프트 실행 모두 CPU와 MPS의 선택 결과가
같았고, 선택지 확률의 최대 차이는 0.00000322 미만이었습니다. 작업별 결과와
실행 환경별 시간 비교는 [검증 보고서](ko-decision-verification-2026-10-05.ko.md)에
있습니다. 이 실행에서 CUDA나 다른 의존성 버전까지 검증하지는 않았습니다.

첫 다운로드가 성공한 뒤 캐시를 보존하고, 같은 `--cache-dir`에
`--local-files-only`를 추가해 재시작하면 추가 모델 다운로드 없이 사용합니다.

```bash
../brain-openkit-ko-decision-runtime/bin/brain-openkit-serve-ko-decision \
  --device cpu --threads 4 --batch-size 4 --port 8010 \
  --cache-dir ../brain-openkit-ko-decision-cache --local-files-only
```

다른 터미널에서 갱신된 체크아웃의 CLI 또는 위 환경에 설치한 CLI를 실행하세요.

```bash
../brain-openkit-ko-decision-runtime/bin/brain-openkit doctor --provider ko-decision --prompt-language ko --json
../brain-openkit-ko-decision-runtime/bin/brain-openkit doctor --provider ko-decision --prompt-language ko --probe --timeout 120 --json
../brain-openkit-ko-decision-runtime/bin/brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider ko-decision --prompt-language ko --timeout 120 --json
../brain-openkit-ko-decision-runtime/bin/brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider ko-decision --prompt-language ko --timeout 120 --json
../brain-openkit-ko-decision-runtime/bin/brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider ko-decision --prompt-language ko --timeout 120 --json
```

`--prompt-language ko`는 모든 제공자에서 내장 지시문과 레이블을 한국어로 바꿉니다.
검색 질문, 노트 내용, 분류·태그 이름과 설명은 번역하지 않으므로 평가하려는 언어에
맞는 분류표를 사용하세요. 기본값은 `en`입니다. API 모델 이름은
`mmetamong/ko-decision-roberta-large`입니다. `--model`은 서버가 이미 제공하는
이름과 일치해야 하며 고정된 가중치를 바꾸지 않습니다. 서버 포트를 바꿨다면
CLI의 `--base-url`도 맞추세요.

각 선택지는 `(지시문 + 선택지, 상태 입력)` 쌍으로 점수를 매깁니다. 서버는
1–10개 선택지를 지원하며, 같은 질문의 점수에 temperature 1의 softmax를
적용합니다. 텍스트는 생성하지 않습니다. 선택지 확률과 균등 확률 대비 최상위
확률로 계산한 신뢰도는 보정된 값이 아니며, 자동 판단 보류 임계값은 없습니다.
모든 텍스트와 특수 토큰을 포함한 **입력 쌍당 512토큰** 제한이 있습니다.
서버는 입력을 자르지 않고 토큰화하며, 하나라도 제한을 초과하면 HTTP 413을
반환합니다. 검색은 전체 BM25 순서로 복귀하고 분류는 오류를 반환합니다.
기본 Markdown 문단 크기인 1,200자만으로 한국어 입력이 이 토큰 예산에 들어간다고
보장할 수 없습니다. `--max-tokens`는 Laya 전용이며 이 모델의 제한을 늘리지 않습니다.

체크포인트는 게시자의 **CC BY-SA 4.0** 라이선스에 따라 별도로 내려받습니다.
독립 구현한 Brain OpenKit 서버·어댑터는 MIT이며 가중치는 포함하지 않습니다.
[출처·라이선스](../ATTRIBUTION.md)와 실제 결과·한계를 기록한
[검증 보고서](ko-decision-verification-2026-10-05.ko.md)를 참고하세요.
이 제공자를 설치해도 `doctor`·`classify`의 Kev 기본값과
`search`·`evaluate`의 BM25 기본값은 유지됩니다.

## Laya·Kev 확인

CLI 환경을 활성화한 상태로 Brain OpenKit 체크아웃으로 돌아오세요. 시작한
서버에 해당하는 줄을 각각 실행하세요. 컴퓨터에 메모리가 충분하면 두 서버를
모두 실행해 둘 수 있습니다.

```bash
brain-openkit doctor --provider laya --json
brain-openkit doctor --provider laya --probe --timeout 120 --json
brain-openkit search "한국어 BM25 검색 후보" --vault examples/vault --provider laya --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider laya --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider laya --timeout 120 --json

brain-openkit doctor --provider kev --json
brain-openkit doctor --provider kev --probe --timeout 120 --json
brain-openkit search "reading journal comets" --vault examples/vault --provider kev --timeout 120 --json
brain-openkit classify local-search.md --vault examples/vault --taxonomy examples/taxonomy.json --provider kev --timeout 120 --json
brain-openkit evaluate examples/evaluation.jsonl --vault examples/vault --provider kev --timeout 120 --json
```

상태 확인은 서비스가 응답하는지 확인하며, `--probe`는 합성 질문도 보냅니다.
검색 출력의 재정렬 상태를 확인하세요. `complete`는 선택한 제공자가 실행되었다는
뜻이고, `unavailable`은 Brain OpenKit이 이유와 함께 BM25 결과를 반환했다는 뜻입니다.
BM25로 대체된 상태에서 종료 코드가 0이라고 해서 모델 추론이 정상 동작했다고
볼 수는 없습니다. 분류 오류가 발생하면 제안을 임의로 만들어 반환하지 않습니다.
이 명령들은 원본 노트를 수정하지 않습니다.

실패 시 동작을 확인하려면 선택한 서버를 중지하고 검색을 다시 실행하세요.
결과는 사용 불가 이유와 함께 BM25 순서를 유지해야 합니다. 분류를 확인하기
전에는 서버를 다시 시작하세요. 다른 포트를 선택했다면 `--base-url`을 사용하세요.
JSON 설정도 `laya_base_url`, `kev_base_url`, `kev_model`을 지원합니다.
미릴리스 소스는 `ko_decision_base_url`, `ko_decision_model`,
`prompt_language`(`en` 또는 `ko`)도 지원합니다.
JSON 설정에는 API 키를 넣지 마세요.

실행 중인 Laya·Kev 서버를 반복 가능한 방식으로 검사하려면 체크아웃 루트에서 실행하세요.

```bash
python benchmarks/check_local_providers.py --output ../brain-openkit-provider-check.json
```

기본 Kev 서버만 검사하려면 다음을 실행하세요.

```bash
python benchmarks/check_local_providers.py --provider kev --output ../brain-openkit-kev-check.json
```

이 스크립트는 합성 예제 보관함의 임시 복사본을 사용합니다. 상태 확인, 추론,
순위 재정렬, 분류, 평가, 모의 서비스 실패, 원본 바이트 보존 여부를 검사합니다.
다른 포트에는 `--laya-url`과 `--kev-url`을 전달하세요. 제안 내용을 보고하지만,
모델이 선택한 모든 태그를 올바른 것으로 간주하지는 않습니다.

## 검증 근거와 한계

선택적 ko-decision 연동에는 별도
[검증 보고서](ko-decision-verification-2026-10-05.ko.md)가 있습니다. 명시된 작업과
프롬프트 언어의 결과로 평가하세요. 요청 성공만으로 검색·태그·일반 한국어 판단
품질이 개선되었다고 볼 수는 없습니다.

기본 0.8B 모델에는 별도의
[검증 기록](kev-08-verification-2026-10-05.md)이 있습니다. 2026-10-05에
공식 런타임은 메모리 64 GiB의 Apple Silicon Mac에서 지정된 리비전의 가중치를
로드했으며, MPS에서 bfloat16으로 동작하는 MLX를 자동으로 선택했습니다.
한국어/영어 직접 스모크 테스트 질문 여섯 개 모두 유효한 응답을 반환했고,
예상 레이블과 일치했습니다. 함께 제공되는 실행 스크립트를 `--run` 없이
시작했을 때도 지정된 리비전의 0.8B 체크포인트가 로드되었으며, 서버의 모델
목록에서 이를 확인했습니다. 이 여섯 예제만으로 전반적인 품질이나
Claude/Codex와의 동등성을 입증할 수는 없습니다.

이 기본 실행 스크립트로 시작한 서버에 대한 실제 CLI 검사에서도 상태 확인,
합성 입력 추론, 검색 순위 재정렬, 한국어/영어 분류, 네 쿼리 평가를 모두
대체 동작 없이 통과했습니다. HTTP 503 응답을 주입했을 때는 BM25 결과의
전체 순서가 유지되었고 분류 오류가 반환되었습니다. 원본 노트 네 개의 해시도
모두 유지되었습니다. 별도로 `--provider` 없이 호출한 `doctor`와 `classify`도
Kev를 올바르게 선택했습니다.

Kev 0.8B는 `local-search.md`를 `research`로 분류하고 `evaluation` 및 `local`
태그를 붙였으며, `reading.md`는 `reading`으로 분류했지만 잘못된 `evaluation`
태그를 붙였습니다. 이전 0.5B의 `plants` 오탐은 사라졌지만, 이와 다른 오탐이
발생했으므로 전반적인 태그 품질이 개선되었다고 주장할 수는 없습니다.
BM25와 Kev 0.8B는 네 쿼리 테스트 데이터에서 Recall@3와 MRR@3 모두 1.0을 기록했습니다.
간단한 프로브 여섯 개의 레이블이 맞았다고 해서 모든 분류와 태그 판단이
올바르다는 뜻은 아닙니다. 전체 기능 검사 실행 결과는
[0.8B CLI 원시 검증 자료](../benchmarks/provider-smoke/2026-10-05-kev-08/report.json)를 참조하세요.

아래 결과는 이전 Laya/0.5B 실행에 관한 것이며, 0.8B 결과로 읽어서는 안 됩니다.

2026-10-05에 두 공식 런타임은 메모리 64 GiB의 Apple Silicon Mac에서
실제로 내려받은 가중치를 로드했습니다.

| 런타임 | 기록된 환경 | 직접 추론 검사 |
| --- | --- | --- |
| Laya 다국어 모델 | Laya 0.3.26, Python 3.13.1, Torch 2.14.1, Transformers 5.18.0, 스레드 4개의 CPU | 한국어/영어 선택 문제 네 개에 유효한 응답을 반환했으며, 세 개가 스모크 테스트 레이블과 일치했습니다. |
| Kev 0.5B | 위에서 지정한 Kev 소스 리비전, Python 3.12.11, Torch 2.8.0, Transformers 5.17.0, Torch/MPS float32 | 선택 문제 여섯 개에 유효한 응답을 반환했으며, 다섯 개가 스모크 테스트 레이블과 일치했습니다. |

서로 다른 소규모 프롬프트 집합으로는 실행 여부를 검증할 수 있을 뿐,
정확도를 비교할 수는 없습니다. 이 결과는 Kev가 Laya보다 우수하거나,
어느 모델이 Claude/Codex와 동등하거나, 하이브리드 워크플로가 총비용을
절감한다는 근거가 되지 않습니다. 로컬 연산도 메모리, 전력, 시간을 사용하며,
호스트가 작성하는 문장에는 여전히 유료 모델이 사용될 수 있습니다.
[기존 이중 언어 Laya 평가](../benchmarks/bilingual-v1/reports/2026-10-04/RESULTS.md)는
별도의 합성 품질 테스트이며 Kev와의 비교는 포함하지 않습니다.

Laya와 Kev 0.5B는 공통 CLI 기능 검사도 통과했습니다. 검색 순위 재정렬 완료,
분류, 대체 동작 없는 네 쿼리 평가, 실패 시 대체 동작, 한국어 텍스트와 CRLF
바이트를 포함한 원본의 완전한 보존을 확인했습니다. Kev 0.5B는 로컬 검색 노트에
관련 없는 `plants` 태그를 제안했습니다. BM25, Laya, Kev 0.5B의 세 검색 경로는
모두 네 쿼리로 구성된 매우 작은 테스트 데이터에서 1.0을 기록했습니다.
이는 모델의 이점에 대한 근거가 아닙니다.
[날짜가 명시된 검증 보고서](model-verification-2026-10-05.md)와
[CLI 원시 검증 자료](../benchmarks/provider-smoke/2026-10-05/report.json)를 참조하세요.

더 넓은 범위의 통합 및 회귀 검증 근거는 [구현 노트](implementation-notes.md)를
참조하세요. 공식 서버에서는 다른 Kev 체크포인트도 선택할 수 있습니다.
각 체크포인트의 동작은 해당 체크포인트의 검증 근거로 평가하세요. 코드, 가중치,
기본 모델에는 각각의 라이선스가 적용되며, Brain OpenKit의 라이선스가 이를 대체하지 않습니다.

1차 참고 자료: [Laya 모델](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148),
[기본 Kev 0.8B 가중치](https://huggingface.co/jaredpalmer/kev-0.8b/tree/bf75a6a8848ea6960ff2ed108d9ed44c2941174f),
[Kev 0.5B 가중치](https://huggingface.co/jaredpalmer/kev-0.5b/tree/edf1dc6d7f8d983c0adfd251e80a686e5539fc61),
[고정된 리비전의 Kev 서버](https://github.com/jaredpalmer/kev/blob/fe64b1274ea7f80d4095866df90666abb03e9cf6/kev/serve.py).
