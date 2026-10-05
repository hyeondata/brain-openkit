# Brain OpenKit — 프로젝트 이름과 공개 문서 구성

작성일: 2026-10-04

## 선택한 이름

- 프로젝트 표시명: **Brain OpenKit**
- 저장소 이름 및 CLI 명칭: **`brain-openkit`**
- 저작권 프로젝트명: **Brain OpenKit contributors**
- 영문 소개: **An open-source second-brain toolkit for Obsidian.**
- 한국어 소개: **Obsidian을 위한 오픈소스 세컨드 브레인 도구 모음.**

사용자는 동일한 이름을 사용하는 프로젝트가 발견되지 않으면 `brain-openkit`으로 확정하도록 요청했다.
2026-10-04 공개 검색에서 동일 프로젝트를 발견하지 못해 표시명 **Brain OpenKit**, 저장소와 CLI 이름 **`brain-openkit`**으로 확정했다.
`brain`은 노트를 연결하는 세컨드 브레인을, `openkit`은 오픈소스 도구 모음이라는 방향을 설명한다.
검색·분류로 시작해 위키 관리와 화면 연동까지 확장할 수 있고, Laya와 Jev 등 특정 모델에 이름이 종속되지 않는다.
Obsidian 커뮤니티를 위한 독립 프로젝트이며 Obsidian의 공식 제품이나 제휴 프로젝트를 뜻하지 않는다.

## 비교한 후보

| 후보 | 장점 | 선택 시 고려점 |
| --- | --- | --- |
| **brain-openkit** | 세컨드 브레인과 오픈소스 도구 모음이라는 목적을 전달 | Obsidian 기반이라는 점은 부제로 설명 |
| obsidian-openkit | Obsidian용 도구 모음이라는 대상이 선명함 | 세컨드 브레인이라는 목적은 소개 문구로 설명 |
| obsidian-openindex | 검색·인덱싱 목적이 선명함 | 정리·위키 기능까지 담기에는 범위가 좁음 |
| obsidian-local-kit | 로컬 실행을 강조함 | 후속 Jev API 연결과 오픈소스 성격은 별도 설명 필요 |

## 공개 이름 검색

2026-10-04에 저장소 생성 전 다음 범위를 확인했다.

| 확인 대상 | 확인 결과 |
| --- | --- |
| GitHub `brain-openkit in:name`, `brainopenkit in:name`, `brain openkit` 이름·설명 검색 | 결과 없음 |
| 일반 웹의 이름 정확 검색 | 동일 프로젝트 미발견 |
| PyPI·npm의 `brain-openkit`, `brainopenkit`, `brain_openkit`, `brain.openkit` 조회 | 각 API HTTP 404 |
| Hugging Face 모델·데이터셋·Spaces 이름 검색 | 빈 결과 |

확인 경로:

- [GitHub 이름 검색 API](https://api.github.com/search/repositories?q=brain-openkit%20in%3Aname)
- [GitHub 구분자 없는 이름 검색](https://api.github.com/search/repositories?q=brainopenkit%20in%3Aname)
- [PyPI 패키지 API](https://pypi.org/pypi/brain-openkit/json)
- [npm 패키지 API](https://registry.npmjs.org/brain-openkit)
- [Hugging Face 모델 검색](https://huggingface.co/api/models?search=brain-openkit&limit=100)
- [Hugging Face 데이터셋 검색](https://huggingface.co/api/datasets?search=brain-openkit&limit=100)
- [Hugging Face Spaces 검색](https://huggingface.co/api/spaces?search=brain-openkit&limit=100)

이는 조사 시점에 공개 검색으로 발견한 범위다. 비공개·미색인 프로젝트와 유사 상표 전체를 확인한 결과는 아니며,
이름 예약·패키지 소유권 확보·상표 권리 확인을 뜻하지 않는다. 패키지 배포 시점에는 이름 사용 가능 여부를 다시 확인한다.

## README 구성 원칙

[`claude-obsidian`](https://github.com/AgriciDaniel/claude-obsidian)의 소개·작업 흐름·사용 안내·기여·출처
구성을 참고하고 Brain OpenKit의 범위에 맞춰 새로 작성했다. 기존 문구와 이미지, 제품 기능 목록은 복제하지 않는다.

1. 이름과 한 문장 소개로 검색·정리 목적을 전달한다.
2. 현재 CLI alpha 단계임을 첫 화면에 표시한다.
3. 목표 기능과 Mermaid 흐름도로 구조를 설명한다.
4. 실행 가능한 명령과 후속 구현 범위를 구분한다.
5. Laya 우선 구현과 Jev 후속 어댑터를 명시한다.
6. 데이터 처리 조건과 아직 측정하지 않은 품질을 설명한다.
7. 로드맵, 기여 경로, 라이선스, 출처를 연결한다.

기본 README는 영어로 작성하고 [한국어판](../README.ko.md)을 같은 범위로 유지한다.
CI 성공, 릴리스 버전, 다운로드 수처럼 실제 근거가 필요한 배지는 해당 상태가 생긴 뒤 추가한다.
현재 배지는 구현 단계와 라이선스, 지원 모델을 나타낸다.

## 공개 저장소에 사용할 소개

GitHub repository slug: `brain-openkit`

권장 About 설명:

> An open-source second-brain toolkit for Obsidian. Local Markdown search and optional Laya decisions. CLI alpha.

권장 topics:

```text
obsidian markdown knowledge-management local-first information-retrieval
bm25 laya cli python open-source
```

GitHub는 소스·문서·이슈·릴리스의 기준 저장소로 사용한다. README의 저장소 링크와 설치 안내는
실제 공개 주소 및 구현 상태에 맞춰 관리한다.

Hugging Face에는 현재 사용할 상위 Laya 모델을 링크한다. 첫 CLI와 평가가 준비되면 합성 노트로
구성한 데모 Space나 공개 가능한 평가 데이터셋을 별도로 검토한다. Brain OpenKit을 자체 학습 모델인
것처럼 등록하거나 상위 모델 가중치를 다시 배포할 필요는 없다.

## 이번 단계의 산출물

- [README.md](../README.md): 영문 프로젝트 소개
- [README.ko.md](../README.ko.md): 한국어 프로젝트 소개
- [LICENSE](../LICENSE): 자체 작성 자료에 적용한 MIT 라이선스
- [CONTRIBUTING.md](../CONTRIBUTING.md): 현재 단계의 기여 방법
- [ATTRIBUTION.md](../ATTRIBUTION.md): 참고 프로젝트와 외부 구성 요소의 출처·라이선스 구분
- [설계서](superpowers/specs/2026-10-04-obsidian-laya-design.md): Laya를 기본으로 사용하는 CLI와 제공자 교체 설계

문서는 CLI alpha의 구현 범위와 기여 방향을 설명한다. 현재 소스 설치로 실행할 수 있으며,
패키지 발행과 Hugging Face 데모는 평가 결과에 맞춰 후속 단계에서 준비한다.
