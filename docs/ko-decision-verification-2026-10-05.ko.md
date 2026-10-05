# ko-decision 연동·실측 검증 — 2026-10-05

[English](ko-decision-verification-2026-10-05.md) | 한국어

선택적 `ko-decision` 제공자는 실제 CPU·MPS 모델과 Brain OpenKit CLI에서
동작했습니다. 다만 이번 소규모 한국어 holdout에서는 Kev 0.8B의 태그 F1이
더 높았고, ko-decision의 검색 MRR은 BM25보다 낮았습니다. 따라서
`doctor`·`classify`의 기본 제공자는 **Kev 0.8B**, `search`·`evaluate`의
기본값은 **BM25**로 유지합니다. ko-decision은 선택해서 비교할 수 있는 제공자입니다.

이 문서는 **미릴리스 소스 변경**을 검증합니다. `v0.2.0a4` 태그나 기존 릴리스
파일에 이 기능이 포함되었다는 뜻이 아닙니다. 테스트한 소스·wheel에 표시되는
버전 문자열이 `0.2.0a4`여도 기존 배포 파일과 구분해야 합니다.

## 모델과 실행 환경

| 항목 | ko-decision | 비교 대상 Kev 0.8B |
| --- | --- | --- |
| 체크포인트 | `mmetamong/ko-decision-roberta-large` | `jaredpalmer/kev-0.8b` |
| 고정 리비전 | `dfd606fff30d52963c0073659ff9a8f6bf1fce6d` | `bf75a6a8848ea6960ff2ed108d9ed44c2941174f` |
| 실행 방식 | Torch CPU 및 Torch/MPS, float32 | MLX, bfloat16 |
| Python | 3.13.1 | 3.12.11 |
| 주요 라이브러리 | Torch 2.14.1, Transformers 5.18.0 | MLX 0.32.2, mlx-lm 0.31.3 |
| 점수 temperature | 1.0 | 2.3510958125672174 |
| 배치·스레드 | 선택지 배치 4, CPU 스레드 4 | 고정 체크포인트의 공식 런타임 설정 |

하드웨어는 Apple M1 Max, 메모리 64 GiB, 논리 CPU 10개입니다.
ko-decision의 파라미터 수는 336,657,409개입니다. 모델 입력은
`(지시문 + 선택지, 상태 입력)` 쌍이며, 각 스칼라 점수에 같은 질문 내 softmax를
적용합니다. 선택지 확률과 신뢰도는 보정된 정답 확률이 아니며 자동 판단 보류
임계값을 두지 않았습니다. 일반 `score`·`noul` 연산이나 문장 생성은 이번
Brain OpenKit 연동 범위에 포함하지 않습니다.

Kev의 기본 모델은
`Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`,
서버 소스는 `fe64b1274ea7f80d4095866df90666abb03e9cf6`입니다.
자세한 버전과 파일 해시는 [CPU 환경](../benchmarks/ko-decision/2026-10-05/runtime.json),
[MPS 환경](../benchmarks/ko-decision/2026-10-05/runtime-mps.json),
[Kev MLX 환경](../benchmarks/ko-decision/2026-10-05/runtime-kev-mlx.json)에 있습니다.

Brain OpenKit 서버·어댑터는 독립 구현한 MIT 코드입니다. 체크포인트는 게시자의
CC BY-SA 4.0에 따라 별도로 내려받으며 저장소나 wheel에 가중치를 포함하지
않습니다. 프로젝트 MIT 라이선스가 외부 모델의 라이선스를 대체하지 않습니다.
[출처·라이선스](../ATTRIBUTION.md)를 참고하세요.

## 평가 자료와 방법

[고정된 bilingual-v1 자료](../benchmarks/bilingual-v1/README.md)의 원문·정답·분류표를
사용했습니다. 합성 노트 24개는 한국어 12개와 영어 12개로 구성되며, 검색 질문은
개발 12개·holdout 24개입니다. 분류 holdout은 개발 노트와 다른 18개로,
한국어 8개·영어 10개입니다. 아래 한국어 표는 **분류 노트 8개와 검색 질문
12개**만 집계합니다. 한국어 질문이 반드시 한국어 문서를 대상으로 하지는 않습니다.

검색은 BM25 후보 문단 최대 8개에서 상위 노트 3개를 반환합니다. Recall@3과
3위까지의 MRR을 계산하며, BM25 후보에 없는 문서는 재정렬로 복구할 수 없습니다.
태그 micro F1은 네 태그의 TP·FP·FN을 합산합니다. 범주 정답과 태그 정답은
모델 실행 전에 작성했으며, 결과를 본 뒤 정답·임계값·프롬프트를 튜닝하지 않았습니다.

`--prompt-language ko`는 내장 지시문과 고정 선택지 설명을 한국어로 바꿉니다.
**노트·검색 질문과 영어 분류표는 그대로 유지했습니다.** 따라서 이번 비교는
분류표까지 번역한 한국어 전용 설정을 평가한 결과가 아닙니다.

## 한국어 holdout 결과

아래 시간은 각 실행의 준비 요청 1개를 제외한 **전체 351개 판단 요청**의
클라이언트 경과 시간 중앙값입니다. 한국어 holdout만의 시간이나 검색 한 번의
응답 시간이 아닙니다. 검색 재정렬·범주 선택·태그 판단과 양 언어의 개발·holdout
요청을 모두 포함합니다.

| 모델·장치 | 프롬프트 | 범주 정답 | 태그 micro F1 | 태그 FP / FN | 검색 Recall@3 | 검색 MRR@3 | 요청 중앙값 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 해당 없음 | — | — | — | 0.6667 | 0.6667 | — |
| Kev 0.8B · MLX | 영어 | 7/8 | 0.8333 | 1 / 3 | 0.7500 | 0.6667 | 123.30 ms |
| Kev 0.8B · MLX | 한국어 | 8/8 | 0.8462 | 2 / 2 | 0.6667 | 0.6111 | 127.81 ms |
| ko-decision · MPS | 영어 | 7/8 | 0.4828 | 9 / 6 | 0.7500 | 0.5278 | 182.65 ms |
| ko-decision · MPS | 한국어 | 7/8 | 0.5714 | 12 / 3 | 0.6667 | 0.5694 | 176.81 ms |

ko-decision은 한국어 지시문에서 태그 누락이 6개에서 3개로 줄었지만,
오탐은 9개에서 12개로 늘었습니다. 두 프롬프트 언어 모두 이번 태그 평가에서는
Kev보다 낮은 F1을 기록했습니다. 영어 지시문의 ko-decision은 BM25보다
Recall@3이 높았지만 MRR@3은 낮았습니다. 한국어 지시문에서는 두 모델 모두
BM25와 Recall@3이 같고 MRR@3은 낮았습니다. 이 결과로 기본 검색을 모델
재정렬로 바꾸거나 메타데이터를 자동 적용할 근거는 얻지 못했습니다.

GPU 네 실행은 순차 수행했습니다. 다만 Torch/MPS float32와 MLX bfloat16은
런타임·정밀도·temperature가 다릅니다. 위 수치는 해당 컴퓨터의 실제 배치
구성을 비교한 관측값이며, 모델 구조만의 속도 우열이나 통계적 성능 차이를
증명하지 않습니다.

## 영어 holdout 결과

영어 분류 노트 10개와 영어 검색 질문 12개의 결과도 함께 보존합니다. 한국어
프롬프트가 영어 자료에서도 유리하다고 가정할 근거는 없습니다.

| 모델·장치 | 프롬프트 | 범주 정답 | 태그 micro F1 | 태그 FP / FN | 검색 Recall@3 | 검색 MRR@3 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 해당 없음 | — | — | — | 0.8333 | 0.8333 |
| Kev 0.8B · MLX | 영어 | 9/10 | 0.6667 | 0 / 5 | 0.9167 | 0.8750 |
| Kev 0.8B · MLX | 한국어 | 9/10 | 0.5333 | 1 / 6 | 0.8333 | 0.8333 |
| ko-decision · MPS | 영어 | 8/10 | 0.3889 | 19 / 3 | 0.9167 | 0.8333 |
| ko-decision · MPS | 한국어 | 8/10 | 0.3200 | 11 / 6 | 0.7500 | 0.5556 |

## CPU 재현과 실행 완료 여부

ko-decision CPU의 영어·한국어 프롬프트 요청 중앙값은 각각 **386.03 ms**와
**415.12 ms**였습니다. CPU 영어 실행은 Kev 시작 과정과 잠시 겹쳤으므로
해당 시간은 탐색적 관측값으로 취급합니다. 같은 입력에 대해 CPU와 MPS의
선택 결과는 두 프롬프트 언어 모두 일치했고, 전체 선택지 확률의 최대 절대
차이는 약 **0.00000321**로 0.00000322 미만이었습니다.

완료된 평가 실행은 CPU 2개와 GPU 4개입니다. 각 실행에서 준비 요청 1개와
측정 요청 351개, 합계 352개를 기록했습니다. **총 2,112개 요청에서 오류는
0개**, 검색의 BM25 복귀도 0건이었으며 여섯 실행 모두 원문 입력 해시가
전후 동일했습니다. 이 집계에는 별도 기능·경계 검사 요청은 포함하지 않습니다.

Kev의 서버 미기동 시도는 추론 전에 실패했고, 별도의 CPU 시도는 느린 요청을
확인한 뒤 조기에 중단했습니다. 완료된 품질 결과가 없어 위 비교에서 제외했으며
[요약의 미완료 시도 기록](../benchmarks/ko-decision/2026-10-05/summary.json)에 남겼습니다.

## 기능·입력 경계·파일 보존

| 검사 | 확인한 결과 | 근거 |
| --- | --- | --- |
| 실제 CPU 모델 실행 | 고정 체크포인트를 적재하고 모델 카드 예제 선택 재현 | [직접 실행](../benchmarks/ko-decision/2026-10-05/direct-smoke.json) |
| 실제 CLI `doctor`, `search`, `classify`, `evaluate` | 모델 식별·한국어 추론·재정렬·분류·평가 완료, 모의 서비스 오류 시 fallback 확인 | [기능 검사](../benchmarks/ko-decision/2026-10-05/functional.json) |
| 실제 MPS 토크나이저·모델 경계 | 특수 토큰 포함 511·512토큰 입력 쌍 통과, 513토큰은 `http_413` | [경계 검사](../benchmarks/ko-decision/2026-10-05/actual-boundaries.json) |
| 소스 CLI의 긴 입력 | 검색은 전체 BM25 순서로 복귀, 분류는 종료 코드 2와 `http_413`, 원문 해시 유지 | [소스 검사](../benchmarks/ko-decision/2026-10-05/limits-source.json) |
| 설치한 wheel의 긴 입력 | 별도 설치 환경에서 같은 fallback·오류·원문 보존 확인 | [wheel 검사](../benchmarks/ko-decision/2026-10-05/limits-wheel.json) |
| 한국어 메타데이터 preview → apply → undo | 미리보기는 파일을 바꾸지 않음; 검토한 정확한 계획을 적용해 `기술`·`백업` 저장; CRLF 원문 보존 및 undo 후 원본 바이트 복원 | 위 소스·wheel 검사의 `reviewed_write` |

512토큰 제한은 상태 입력만이 아니라 지시문·선택지·특수 토큰을 포함한
**전체 입력 쌍**에 적용됩니다. 입력을 조용히 잘라내지 않습니다. 단일 선택지로
만든 511·512토큰 경계 검사에서 확률 1.0은 경계 처리 결과이며 판단 품질의
근거가 아닙니다. 한국어 메타데이터 검사는 합성 노트 하나의 파일·frontmatter
저장 경로를 확인한 것이며, 이번 변경으로 **Obsidian 앱 UI를 다시 검증하지는 않았습니다.**

Python 3.11·3.13은 각각 테스트 288개를 실행해 **284개 통과·플랫폼 관련
4개 건너뜀·실패 0개**를 기록했습니다. [3.11 로그](../benchmarks/ko-decision/2026-10-05/tests-311.txt)와
[3.13 로그](../benchmarks/ko-decision/2026-10-05/tests-313.txt)를 참고하세요.
핵심 wheel은 Torch가 없는 별도 환경에서도 CLI를 실행했으며, 모델 런타임은
선택적 `ko-decision` extra로 분리했습니다. 모델 추론 결과와 HTTP 계약 fixture
테스트 결과는 구분해서 해석해야 합니다.

## 사용·재현

[로컬 모델 안내](local-models.ko.md#ko-decision-미릴리스-소스)에 따라 이 변경을
포함한 체크아웃에서 선택적 환경을 설치합니다. 다음은 체크아웃 루트에서
MPS 서버를 시작하는 예입니다. 최초 실행은 고정 리비전의 가중치를 내려받습니다.

```bash
python3.13 -m venv ../brain-openkit-ko-decision-runtime
../brain-openkit-ko-decision-runtime/bin/python -m pip install '.[ko-decision]'
../brain-openkit-ko-decision-runtime/bin/brain-openkit-serve-ko-decision \
  --device mps --threads 4 --batch-size 4 --port 8010 \
  --cache-dir ../brain-openkit-ko-decision-cache
```

CPU에서는 `--device cpu`를 사용합니다. 이미 내려받은 동일 캐시로만 실행하려면
`--local-files-only`를 추가합니다. 다른 터미널에서 같은 설치 환경을 사용합니다.

```bash
../brain-openkit-ko-decision-runtime/bin/brain-openkit doctor \
  --provider ko-decision --prompt-language ko --probe --timeout 120 --json
../brain-openkit-ko-decision-runtime/bin/brain-openkit search "한국어 BM25 검색 후보" \
  --vault examples/vault --provider ko-decision --prompt-language ko --timeout 120 --json
../brain-openkit-ko-decision-runtime/bin/python benchmarks/run_bilingual.py \
  --provider ko-decision --prompt-language ko --base-url http://127.0.0.1:8010 \
  --output /tmp/brain-openkit-ko-mps-ko
../brain-openkit-ko-decision-runtime/bin/python benchmarks/check_local_providers.py \
  --provider ko-decision --prompt-language ko --output /tmp/brain-openkit-ko-functional.json
../brain-openkit-ko-decision-runtime/bin/python benchmarks/check_ko_decision_limits.py \
  --output /tmp/brain-openkit-ko-limits.json
```

평가 출력 디렉터리는 기존에 없어야 합니다. 영어 지시문 비교는
`--prompt-language en`과 새로운 출력 디렉터리를 사용합니다. GPU 비교 시
각 실행을 순차 수행하고 장치·라이브러리 버전을 별도로 기록하세요.
`--runtime-metadata`에는 해당 실행에서 직접 수집한 메타데이터를 제공할 수 있습니다.

Kev 비교는 [고정된 Kev 0.8B 서버](local-models.ko.md#kev-08b-기본값)를 시작한
뒤, 갱신된 CLI 환경에서 아래처럼 실행합니다. 이 실행은 별도 Kev 서버가
적재한 모델을 사용하며 `--model`로 Hugging Face 가중치를 다운로드하지 않습니다.

```bash
../brain-openkit-ko-decision-runtime/bin/python benchmarks/run_bilingual.py \
  --provider kev --prompt-language ko --base-url http://127.0.0.1:8009 \
  --output /tmp/brain-openkit-kev-mlx-ko
```

## 원시 결과와 해석 범위

| 실행 | 요청·결과 집계 | 모든 요청·판단 |
| --- | --- | --- |
| ko-decision CPU · 영어 | [report](../benchmarks/ko-decision/2026-10-05/ko-en-cpu/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/ko-en-cpu/decisions.jsonl) |
| ko-decision CPU · 한국어 | [report](../benchmarks/ko-decision/2026-10-05/ko-ko-cpu/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/ko-ko-cpu/decisions.jsonl) |
| ko-decision MPS · 영어 | [report](../benchmarks/ko-decision/2026-10-05/ko-en-mps/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/ko-en-mps/decisions.jsonl) |
| ko-decision MPS · 한국어 | [report](../benchmarks/ko-decision/2026-10-05/ko-ko-mps/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/ko-ko-mps/decisions.jsonl) |
| Kev MLX · 영어 | [report](../benchmarks/ko-decision/2026-10-05/kev-en-mlx/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/kev-en-mlx/decisions.jsonl) |
| Kev MLX · 한국어 | [report](../benchmarks/ko-decision/2026-10-05/kev-ko-mlx/report.json) | [decisions](../benchmarks/ko-decision/2026-10-05/kev-ko-mlx/decisions.jsonl) |

[전체 요약](../benchmarks/ko-decision/2026-10-05/summary.json)과
[검증 자료 SHA-256](../benchmarks/ko-decision/2026-10-05/sha256.json)도 제공합니다.
원시 보고서는 한국어 결과뿐 아니라 전체 holdout과 영어 결과를 보존합니다.

자료는 저자가 작성하고 다른 에이전트가 검토한 작은 합성 세트입니다. 실제 사용자
vault의 독립 표본이 아니며, 검색 holdout은 개발 질문과 같은 문서를 공유합니다.
한 컴퓨터에서 조건별 한 번 실행했고 신뢰구간·유의성·확률 보정을 평가하지
않았습니다. 실제 vault의 사용자 검토 검색 질문 30개·분류/태그 50개라는 별도
목표도 충족하지 않습니다. Claude/Codex 유료 모델과의 품질 동등성이나 총비용
절감은 이번 검사에 포함하지 않았습니다.
