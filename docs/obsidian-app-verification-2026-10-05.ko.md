# Obsidian 데스크톱 앱 검증 — 2026-10-05

[English](obsidian-app-verification-2026-10-05.md) | 한국어

Brain OpenKit이 만든 Markdown이 실제 Obsidian 데스크톱 앱에서 정상적으로 동작했습니다.
한국어·영어 본문과 속성이 표시되었고, 앱 내 검색으로 노트를 찾았으며, 링크와 백링크로
이동할 수 있었습니다. CLI에서 실행 취소한 뒤 그래프도 갱신되었습니다.
실행 취소 후에는 fold 노트 생성 전의 파일 5개가 모두 복원되었으며 SHA-256 해시와
바이트 수가 일치했습니다. 마지막 CLI lint 검사에서는 노트 5개에 문제가 없었습니다.

이번 검증은 Brain OpenKit `0.2.0a3`의
[`129143902919a6960cbd817f0582ee633bf55991`](https://github.com/hyeondata/brain-openkit/tree/129143902919a6960cbd817f0582ee633bf55991)
커밋, Obsidian **1.13.4**, arm64 환경의 **macOS 15.3.2**, Python **3.13.1**에서
수행했습니다. 기록된 CLI 명령 16개가 모두 성공했고, 앱 UI 확인 항목 11개를 통과했습니다.
합성 자료만 담은 일회용 vault `Brain OpenKit Verification`을 사용했습니다.

## 검증 방법과 근거

CLI로 vault를 초기화하고 합성 원문을 수집한 뒤, 미리 준비한 결정문 초안을 저장했습니다.
각 변경 계획을 확인하고 정확한 계획 ID로 적용하여 분류, 태그, 기존 노트 링크를
추가했습니다. 이어서 여러 노트를 발췌해 모은 fold 노트를 만들었습니다.
앱 UI 자동화로 해당 vault를 Obsidian에서 열고 읽기 화면, 검색, 속성, 링크, 백링크,
그래프를 확인했습니다. 앱을 열어 둔 상태에서 CLI로 fold를 실행 취소한 뒤,
앱 UI와 독립적인 읽기 전용 파일시스템 검사로 결과를 확인했습니다.

개별 확인 내용은 [공개용 보고서](../benchmarks/obsidian-app/2026-10-05/report.json),
[CLI 명령 기록](../benchmarks/obsidian-app/2026-10-05/cli-commands.json),
[앱 UI 기록](../benchmarks/obsidian-app/2026-10-05/native-ui-evidence.json),
[실행 취소 후 검사](../benchmarks/obsidian-app/2026-10-05/post-undo-verification.json)에
정리했습니다. 공개 스크린샷에는 이 합성 vault만 표시됩니다.
화면 확인의 주된 근거는 스크린샷입니다. 접근성 정보에는 본문 검색, 저장한 노트 표시,
최종 결정문 화면의 전체 트리가 포함되며, 나머지 항목은 변경분이나 상태 변화가 없다는
메시지일 수 있습니다. 공개 JSON에서는 로컬 컴퓨터 경로를 자리표시자로 바꿨습니다.
해시와 바이트 수는 경로를 바꾸기 전 임시 vault의 원본 파일을 기준으로 합니다.

## 앱에서 확인한 동작

| 확인 항목 | 확인 결과 |
| --- | --- |
| 저장한 노트 표시 | `Notes/검증 결정.md`에 한국어 결정문과 영어 문단이 표시되었습니다. 속성에는 분류 `research`와 태그 `brain-openkit`, `app-verification`이 표시되었습니다. |
| 앱 내 본문 검색 | 따옴표로 감싼 검색어 `"청록나침반 검증 결정"`은 실행 취소 전 파일 2개에서 4곳, 실행 취소 후 파일 1개에서 2곳이 일치했습니다. 이 수치는 텍스트가 일치한 횟수이며 검색 정확도 점수가 아닙니다. |
| 앱 내 태그 검색 | `tag:#app-verification` 검색 결과로 저장한 결정문 1개가 나왔습니다. |
| 관련 노트 링크 | 결정문의 `Related` 링크를 클릭하면 `Notes/별빛도서관-검증-기록.md`가 열렸습니다. |
| 원문 링크 | `Sources`를 클릭하면 보존된 원문인 `Sources/174f06b011a4242d-별빛도서관-검증-기록.md`가 열렸습니다. |
| 원문 백링크 | 보존된 원문의 백링크 패널에 결정문과 수집한 노트의 참조가 표시되었습니다. 결정문 항목을 클릭하면 결정문으로 돌아갔습니다. |
| Fold 표시 | `Notes/되돌림 검증.md`에 원문 줄 번호를 포함한 발췌 블록이 읽을 수 있는 형태로 표시되었고, `Index.md`에서 연결된 백링크가 보였습니다. |
| 실행 취소 전 그래프 | fold 노트를 포함한 노드 6개와 연결선이 화면에 표시되었습니다. |
| 실행 취소 즉시 반영 | CLI 실행 취소로 fold를 제거하자 열려 있던 해당 탭이 그래프 화면으로 돌아갔습니다. 이후 그래프에는 노드 5개가 남았으며 fold 노드는 사라졌습니다. |
| 앱 내 삭제 확인 | 실행 취소 후 `file:"되돌림 검증"` 검색 결과는 0개였습니다. |
| 복원된 인덱스와 백링크 | `Index.md`에서 fold 링크가 제거되었으며, 결정문 링크는 계속 정상적으로 열렸습니다. 결정문 화면의 백링크·링크된 언급 수는 6에서 1로 바뀌었습니다. |

최종 결정문 화면에는 본문, 속성, 원문·관련 노트 링크, 앱 내 검색의 일치 항목 2곳,
인덱스에서 연결된 언급 1개가 유지되었습니다.

![실행 취소 후 Obsidian에 표시된 최종 결정문](../benchmarks/obsidian-app/2026-10-05/screenshots/native-final-decision.jpg)

실행 취소 전 그래프에는 여섯 번째 노드인 `되돌림 검증`이 포함되어 있습니다.

![Fold 실행 취소 전 연결된 노드 6개](../benchmarks/obsidian-app/2026-10-05/screenshots/native-graph-before-undo.jpg)

실행 취소 후에는 원래 노드 5개가 남습니다.

![Fold 실행 취소 후 연결된 노드 5개](../benchmarks/obsidian-app/2026-10-05/screenshots/native-graph-after-undo.jpg)

추가 스크린샷에서
[본문 검색](../benchmarks/obsidian-app/2026-10-05/screenshots/native-content-search.jpg),
[저장한 노트 표시](../benchmarks/obsidian-app/2026-10-05/screenshots/native-saved-note.jpg),
[태그 검색](../benchmarks/obsidian-app/2026-10-05/screenshots/native-tag-search.jpg),
[원문 백링크](../benchmarks/obsidian-app/2026-10-05/screenshots/native-source-backlinks.jpg),
[fold 표시](../benchmarks/obsidian-app/2026-10-05/screenshots/native-fold-before-undo.jpg),
[복원된 인덱스](../benchmarks/obsidian-app/2026-10-05/screenshots/native-index-after-undo.jpg)를
확인할 수 있습니다.

## 트랜잭션과 원문 보존

Fold 트랜잭션 `0028e59180864735aa88c6a6ee8e5794`는
`Notes/되돌림 검증.md`와 `Index.md`를 변경했습니다. 정확히 이 트랜잭션을
실행 취소하자 상태 `undone`이 반환되었고, fold가 제거되면서 인덱스가 복원되었습니다.
실행 취소 후의 읽기 전용 검사는 vault에 쓰기 작업을 하지 않았으며, fold 생성 전
모든 파일의 해시와 길이가 복원되었는지 독립적으로 확인했습니다.

| Fold 생성 전 파일 | 복원된 바이트 수 | SHA-256 일치 |
| --- | ---: | --- |
| `Index.md` | 144 | 일치 |
| `Notes/검증 결정.md` | 579 | 일치 |
| `Notes/별빛도서관-검증-기록.md` | 815 | 일치 |
| `Sources/174f06b011a4242d-별빛도서관-검증-기록.md` | 375 | 일치 |
| `기존 보존 노트.md` | 133 | 일치 |

입력 원문과 보존된 사본은 바이트 단위로 동일했으며, 미리 넣어 둔 기존 노트의
CRLF 줄바꿈도 그대로 유지되었습니다. 마지막 lint 검사에서는 깨진 링크, 모호한 링크,
연결 없는 노트, 메타데이터 오류가 없었습니다. 마지막 BM25 검색에서도
`Notes/검증 결정.md`가 원문 경로·줄 번호와 함께 첫 번째 결과로 나왔습니다.

## 발견 사항과 한계

인덱스에 항목을 차례로 추가하면서 `Notes` 제목이 반복해서 표시되었습니다.
링크는 동작했으며, 실행 취소 후에는 이전 인덱스가 바이트 단위로 정확히 복원되었습니다.
이는 이번 실행에서 확인한 표시상의 문제이며, 검증 과정에서 핵심 기능이나 화면 구성을
수정하지 않았습니다.

Fold는 원문을 줄 번호가 포함된 코드 블록 형태로 발췌해 보여 줍니다.
이번 화면 검증은 이 발췌 결과를 확인한 것이며, 새로 생성한 종합 요약이나
편집을 거친 개요의 품질을 검증한 것은 아닙니다.

이 근거는 macOS의 작은 합성 vault에서 CLI부터 Obsidian까지 이어지는 한 차례의
전체 흐름을 확인한 결과입니다. Windows·Linux 앱의 동작, 대규모 vault, 동시 편집,
중단 복구, 모든 Obsidian 설정은 검증 범위에 포함되지 않습니다.
UI 확인은 Obsidian의 기존 기능과 Markdown의 연동을 검증한 것이며,
별도의 Obsidian 플러그인 UI를 설치하거나 검증하지 않았습니다.

검색에는 `--provider none`으로 로컬 BM25를 사용했습니다. 초안은 미리 준비했고,
분류·태그 등 메타데이터 값도 검증 입력으로 직접 지정했습니다.
이번에는 유료 Claude·Codex 호스트 세션이나 Laya·Kev·Jev 추론을 다시 실행하지
않았습니다. 따라서 앱 검증만으로 모델 품질, 비용 절감, 모델 간 결과의 동등성을
입증할 수 없습니다. 이전 [호스트 실행 기록](implementation-notes.md),
[Laya·Kev 0.5B 검증](model-verification-2026-10-05.md),
[Kev 0.8B 검증](kev-08-verification-2026-10-05.md)은 각 기록의 검증 범위를 유지합니다.
