# 대화 아카이브

[English](conversation-archive.md) | 한국어

`0.2.0a4`부터 제공됩니다. 실제 CLI 검사와 소스·최종 배포 파일의 검증 범위는
[아래](#검증-범위)에 정리합니다.

대화 아카이브는 **기본적으로 꺼져 있습니다**. 보관함을 명시적으로 선택해
활성화하면 지원되는 호스트의 대화를 로컬 Markdown 사본으로
`Inbox/Conversations/`에 보관할 수 있습니다. 아카이브를 활성화하면 이러한
자동 갱신을 허용하게 됩니다. 선별한 지식 노트에는 기존의 검토 후 저장
워크플로가 계속 적용됩니다.

아카이브 작업은 모델을 사용하지 않으며 네트워크 요청도 하지 않습니다.
Claude나 Codex는 대화 중에 평소 사용하는 호스팅 모델을 계속 사용할 수 있습니다.
이 기능은 요약을 생성하거나 대화를 분류하거나 바이너리 첨부 파일을 복사하지
않습니다. 호스트 통합이 제공하는 대화 기록 내용만 보존할 수 있습니다.

## 저장되는 내용

호스트와 세션의 조합마다 Markdown 파일 하나를 만듭니다. 파일명은 호스트
이름과 세션 ID의 SHA-256 해시를 조합합니다. 저장 위치는 선택한 보관함 안의
`Inbox/Conversations/`로 고정되며, 설정은
`.brain-openkit/conversations.json`에 저장됩니다.

기본 보관 내용은 사용자와 어시스턴트에게 보이는 텍스트입니다. 대화 기록 안에 포함된
도구 출력의 보관은 선택 사항이며 기본적으로 꺼져 있습니다. 별도의 외부
파일에 저장된 도구 출력은 읽지 않습니다. 시스템·개발자 메시지, 삽입된 문맥,
thinking·analysis, 도구 호출 인자와 이미지·바이너리 내용은 제외합니다. 아카이브는 검증된 답변이 아닌
대화 기록입니다. 오류, 출처 인용문, 지시처럼 보이는 문구도 대화 내용으로
남습니다. 도구 출력을 제외해도 메시지에 민감한 정보가 포함될 수 있으므로,
해당 내용을 보관하기에 적절한 보관함을 선택하세요.

## 기본값과 제한

| 설정 | 기본값 | 의미 |
| --- | --- | --- |
| `enabled` | `false` | 명시적으로 활성화하기 전에는 아무것도 보관하지 않습니다. |
| `max_bytes` | `104857600` (100 MiB) | 아카이브 저장 공간의 합산 한도입니다. |
| `include_tool_output` | `false` | 명시적으로 활성화하지 않으면 도구 출력을 제외합니다. |
| `retention_days` | `0` | 보관 기간에 따른 만료를 사용하지 않습니다. |
| `auto_prune` | `false` | 만료된 관리 대상 아카이브를 자동으로 삭제하지 않습니다. |

세션 노트 하나의 크기 제한은 **2 MiB**로 고정됩니다. 합산 한도에는
`Inbox/Conversations/`의 모든 일반 파일, 설정 파일, 아카이브 잠금용 1바이트가
포함됩니다. 파일시스템의 디렉터리 메타데이터나 다른 Brain OpenKit 트랜잭션
저널은 포함하지 않습니다. 직접 추가한 파일도 관리 대상 아카이브는 아니지만
아카이브 저장 한도에 산입됩니다.
원자적 교체 중에는 이전 노트를 유지하면서 일시적으로 최대 2 MiB를 더 사용할
수 있습니다. 입력 대화 기록 파일의 크기 제한은 **64 MiB**입니다.
이 한도는 Brain OpenKit이 만든 사본에만 적용됩니다. Claude·Codex 자체 대화
로그의 용량을 제한하거나 삭제하지 않으며, 호스트의 저장 공간과 모델 사용은
별도로 계속됩니다.

어느 한도든 초과하게 되면 수집 작업은 차단된 결과를 보고하고 기존 아카이브를
보존합니다. 대화 기록을 알리지 않고 잘라내거나 한도를 늘리지 않습니다.
세션 노트가 한도에 도달하면 호스트에서 새 세션을 시작해 별도 아카이브를
만드세요. 같은 세션의 기록을 추가 파일로 나누어 이어 쓰지는 않습니다.
비활성화하면 기존 파일을 삭제하지 않고 수집을 중단합니다.
수집이 비활성화된 상태에서는 메시지를 살펴보거나 아카이브 파일을 만들지 않습니다.

## 편집 내용 보존과 보관 기간 관리

직접 편집한 아카이브는 자동으로 교체되지 않도록 보호됩니다. 이후 수집은
`edited`를 보고하며, 대화 이력이 충돌하면 `history_conflict`를 보고합니다.
원래 대화 아카이브가 계속 갱신되도록 하려면 정리·편집한 내용은 별도 노트에
보관하세요.
호스트가 대화를 압축하거나 기록 형식을 바꾸어 기존 메시지의 앞부분이 사라지면
갱신이 차단될 수도 있습니다. 도구 출력 포함 여부는 새 세션을 시작하기 전에
선택하는 편이 좋습니다. 세션 중간에 바꾸면 이전 기록의 앞부분이 달라져
`history_conflict`가 발생할 수 있으며, 기존 내용은 보존됩니다.

정리(prune)는 기본적으로 삭제할 항목을 미리 보여 줍니다. 정리를 적용하려면
명시적인 요청이 필요합니다. 자동 정리에는 추가로 `auto_prune: true`와
0보다 큰 `retention_days`가 모두 필요하며, 명시적인 대화 기록 가져오기를 포함한
수집 작업 중에 실행됩니다.
도구가 소유한 노트 중 보관 기간이 지났고 소유권 메타데이터와 본문 해시가
일치하는 노트만 삭제할 수 있습니다. 직접 추가한 파일과 사용자가 편집한
아카이브는 보존됩니다. 크기 한도를 낮추는 것만으로는 이러한 파일의 삭제를
허용한 것으로 간주하지 않습니다.

## 활성화, 상태 확인, 중지

각 명령에 같은 보관함을 명시적으로 지정하세요. 상태 확인은 읽기 전용이며
설정, 현재 저장 용량과 한도 초과 여부를 보여 줍니다. 수집을 활성화하기 전에
확인하세요.

```bash
brain-openkit conversations status --vault /absolute/path/to/MyVault --json
brain-openkit conversations configure --enable --vault /absolute/path/to/MyVault --json
```

수집을 일시 중지하거나 중단하려면 `configure --disable`을 사용하세요.
기존 아카이브는 유지됩니다. 다시 시작하려면 `configure --enable`을 실행하세요.
별도의 일시 중지 명령은 없습니다.

```bash
brain-openkit conversations configure --disable --vault /absolute/path/to/MyVault --json
```

각 설정은 독립적으로 변경할 수 있습니다. 예를 들어 다음 명령들은 대화 기록
안에 포함된 도구 출력의 보관을 활성화한 뒤, 보관 기간을 30일로 설정하고
자동 정리를 활성화합니다.

```bash
brain-openkit conversations configure --include-tool-output --vault /absolute/path/to/MyVault --json
brain-openkit conversations configure --retention-days 30 --auto-prune --vault /absolute/path/to/MyVault --json
```

해당 옵션을 끄려면 `--no-include-tool-output` 또는 `--no-auto-prune`을
사용하세요. `--no-auto-prune --retention-days 0`은 만료를 비활성화하며,
`--max-bytes INTEGER`는 합산 바이트 한도를 설정합니다. 보관 기간이 0일이면
자동 정리를 활성화한 상태로 둘 수 없습니다. 보관 기간이나 도구 출력 설정을
변경하는 것만으로 수집이 활성화되지는 않습니다.

정리를 명시적으로 적용하기 전에 삭제 미리보기를 검토하세요.

```bash
brain-openkit conversations prune --vault /absolute/path/to/MyVault --json
brain-openkit conversations prune --apply --vault /absolute/path/to/MyVault --json
```

보관함에서 수집을 활성화한 후에는 대화 기록을 명시적으로 가져올 수도 있습니다.
지원되는 호스트의 대화 기록 파일과 세션 ID를 지정하세요. 이 작업은 다른
호스트 세션을 찾아보거나 훑어보지 않습니다.

```bash
brain-openkit conversations capture --host claude --session-id example-session --transcript /absolute/path/to/session.jsonl --vault /absolute/path/to/MyVault --json
```

지원되는 Codex 대화 기록에는 `--host codex`를 사용하세요. 수집 결과는
`disabled`, `saved`, `unchanged`, `blocked`, `pending_transcript` 중 하나입니다.
차단된 결과에는 `size_limit`, `session_limit`, `history_conflict`, `edited` 중
하나가 이유로 표시됩니다. CLI 종료 코드는 비활성화·저장·변경 없음일 때 `0`,
차단 또는 수집 대기일 때 `3`, 입력 검증 오류일 때 `2`입니다. 반면 자동 훅은
호스트를 차단하지 않도록 항상 `0`으로 종료합니다. 수동 가져오기 성공만으로
자동 호스트 콜백의 동작을 입증할 수는 없습니다.

## 호스트 지원 범위

| 호스트 | 통합 상태 |
| --- | --- |
| Claude Code | `2.1.220`: 실제 `Stop`·`SessionEnd` 이벤트를 관찰하고, OFF·ON·세션 재개, 보이는 텍스트의 정확한 보관과 재전달 시 변경 없음을 확인했습니다. |
| Codex CLI | `0.149.0`: 기본 훅 수집을 확인했습니다. OFF에서는 보관함 파일이 생성되지 않았고, ON에서는 메시지 2개, 같은 세션 재개 후에는 같은 파일에 4개를 저장했으며 재전달은 변경 없음으로 처리했습니다. |

전체 플러그인 소스 배포본에는 `hooks/hooks.json`과 해당 실행기가 포함되어야
합니다. CLI 전용 wheel로도 수동 가져오기는 가능하지만 호스트 훅은 설치되지
않습니다. 보관함 설정을 활성화하는 것만으로 호스트 콜백이 설치되거나
활성화되지는 않으며, 호스트의 전역 설정도 변경되지 않습니다.

[에이전트 통합 가이드](agent-integration.ko.md)에 따라 전체 플러그인을 설치하세요.
기록에는 Python 3.11 이상이 필요합니다. 호스트의 명령 경로에 있는 `python3`을
사용하거나, 확인한 호환 실행기의 절대 경로를 `BRAIN_OPENKIT_PYTHON`으로
지정할 수 있습니다. 기록이 꺼져 있으면 시스템 Python이 오래된 경우에도 훅은
아무 작업 없이 조용히 종료합니다.
앞서 설명한 대로 대상 보관함을 활성화한 뒤 호스트 세션을 다시 시작하세요.
플러그인이 이미 설치되어 있다면 다음 POSIX 셸 예제로 보관함을 명시적으로
선택할 수 있습니다.

```bash
BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault claude
```

```bash
BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault codex
```

예를 들어 오래된 시스템 Python 대신 다른 실행기로 Claude Code를 시작하려면:

```bash
BRAIN_OPENKIT_PYTHON=/absolute/path/to/python3.13 BRAIN_OPENKIT_VAULT=/absolute/path/to/MyVault claude
```

같은 실행기 변수는 Codex에도 적용됩니다. 훅의 실행 환경만 선택하며 Python을
설치하거나 호스트의 전역 설정을 바꾸지는 않습니다.

Codex CLI에서는 `/hooks`를 열어 Brain OpenKit의 훅 정의를 검토하고 신뢰를
승인합니다. 설치만으로 신뢰가 승인되지는 않으며, 정의가 바뀌면 다시 검토해야
합니다. `0.149.0`의 프로브에서는 별도 기능 플래그 없이 훅이 활성화되어
있었습니다. 다른 버전에서도 지원되는 인터페이스가 제공되는지 확인해야 합니다.

콜백은 명시적으로 지정한 `BRAIN_OPENKIT_VAULT`를 사용하거나, 이벤트의 작업
디렉터리에 이미 활성화된 보관함 아카이브 설정이 있으면 그 디렉터리를
사용합니다. 보관함을 찾기 위해 관련 없는 디렉터리를 검색하지 않습니다.

두 CLI 검사는 합성 세션에서 작업 중인 소스의 제품 콜백을 실제로 실행했습니다.
최종 배포 파일과 CI 결과는 [릴리스 증거](release-0.2.0a4.ko.md)에 별도로 기록합니다.
Claude의 대화 기록 저장은 `Stop` 이벤트보다
늦어질 수 있습니다. 어댑터는 잠시 재시도한 뒤에도 마지막 텍스트가 없으면
수집 대기로 보고하며, 이후 `Stop`이나 `SessionEnd`에서 다시 시도할 수 있습니다.
임시 최종 답변을 만들어 저장하지 않습니다. 마지막 JSONL 줄이 완성되지 않은
경우도 나중으로 미룹니다. `SessionEnd` 이벤트만으로 완전한 아카이브가
보장되지는 않습니다.

훅은 호스트 대화를 차단하지 않습니다. 잘못된 입력, 용량 제한, 수집 대기는
로컬 경로 없는 경고로 알리고 종료 상태 0을 반환하며, 대화에 지시를 삽입하지
않습니다. 모의 대화 기록 테스트나 플러그인 설치 성공만으로는 실제 호스트
세션에서 자동 수집이 동작한다고 볼 수 없습니다. Codex 데스크톱의 자동 수집은
검증하지 않았습니다.

통합은 공식 [Claude 훅](https://code.claude.com/docs/en/hooks)과
[Codex 훅](https://developers.openai.com/codex/hooks/) 인터페이스를 따릅니다.

## 검증 범위

릴리스 검증에서는 코어·CLI 테스트 데이터,
패키지에 포함된 훅, 실제 호스트 콜백, 그 결과로 생성된 보관함 파일을
구분해야 합니다. 기존 `0.2.0a3` 검색·모델·호스트 워크플로 보고서는 대화
아카이브 기능을 검증하지 않습니다. 로컬 아카이브를 추가했다는 이유로
품질 동등성, 비용 절감, 운영 규모에서의 신뢰성을 주장하지 않습니다.

기존의 검토 후 노트 작업 흐름은 [에이전트 통합 가이드](agent-integration.ko.md)를
참조하세요. 현재 아카이브 검사, 최종 배포 파일·CI 증거와 한계는
[0.2.0a4 검증 기록](release-0.2.0a4.ko.md)에 정리합니다.
