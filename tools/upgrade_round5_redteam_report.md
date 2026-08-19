# v24-v28 5-Round Upgrade Red-Team Report

검증일: 2026-08-19

## 최종 판정

**기술 게이트는 PASS, 행동 의미 게이트는 조건부 PASS입니다.**

v24~v28은 더 이상 파일명만 바꾼 복제본이 아닙니다. 현재 생성기로 다시 만든 결과는 320개 파일 모두 서로 다른 SHA-256을 가지며, v28은 16명 전체에 승격되었습니다. 다만 원본 `motion_sheet_v3`에 없는 새로운 신체 포즈를 AI로 재생성한 것은 아니므로, male_01을 제외한 battle은 전용 무기 동작보다 방어·돌진 포즈에 가깝습니다. “전투라는 의미가 반드시 읽혀야 한다”는 제품 기준으로는 완전 승인할 수 없습니다.

## 통과한 게이트

| 항목 | 결과 |
|---|---|
| v24~v28 파일 | 5 x 16명 x 4종 = 320개 |
| 버전 간 중복 SHA-256 | 0개 중복, 320개 고유 |
| v28 canonical 파일 | 16명 x 4종 = 64개, 누락 0개 |
| PNG 계약 | 1536x1024, RGBA, 4x2, 8셀 |
| 알파/빈 프레임 | 320개 전부 통과 |
| partner/object manifest | battle은 partner, interaction은 partner+object 요구 |
| 실제 대표 전투 영상 | 960x480, 180프레임, 30fps, 6초 |
| 실제 전투 fallback | `motion_asset_version=v28`, `motion_fallback_used=false` |
| 백엔드 핵심 테스트 | 108개 통과, provider 테스트 76개 통과 |
| Flutter 테스트 | 34개 통과 |

## 발견된 위험과 처리

### 1. 중복 산출물

초기 매트릭스는 v24~v35가 동일 해시를 반복했습니다. 생성기에는 버전별 `scale`, `motion`, `rotation` 프로필과 v26 전투 궤적, v27 상호작용 물체, v28 착지 효과를 적용했고 v24~v28을 단일 프로세스로 재생성했습니다. 현재는 320개 논리 산출물의 SHA-256이 모두 다릅니다.

### 2. partner/object

`action_cycle_v28_manifest.json`에 다음 계약을 고정했습니다.

- battle: `requires_partner=true`, `requires_object=false`
- interaction: `requires_partner=true`, `requires_object=true`

파트너가 없는 battle/interaction은 백엔드에서 idle로 전환합니다. 대표 battle 영상은 `co_star_included=true`, `secondary_motion_sheet_character_key=male_06`입니다. interaction은 작은 golden key cue를 primary 시트에 넣고, 파트너는 별도 레이어로 합성합니다.

### 3. fallback

기존에는 v28 파일이 없고 v23/v22 legacy asset이 선택되어도 `motion_fallback_used=false`로 보일 수 있었습니다. `hf_video_provider.py`에 `legacy_action_asset_version` 판정을 추가해 canonical v28이 아닌 legacy 버전이 선택되면 fallback을 명시하도록 수정했습니다.

### 4. 남은 semantic 품질 문제

현재 v28 battle은 모든 캐릭터에 대해 정체성은 유지하지만, 15명은 원본 시트에 검·활·주먹 전용 포즈가 없어 달리기/방어 포즈와 궤적 효과를 조합합니다. 따라서 기술상 영상은 생성되지만, 최종 제품 기준의 `anticipation -> strike -> follow-through`를 캐릭터 신체만으로 보장하지 않습니다.

## 재현 명령

```powershell
cd D:\capstone\soft_capston-main
python -B tools\build_action_asset_version_matrix.py

cd "D:\capstone\soft_capston-main\DB연결 테스트"
python -B -m unittest test_character_assets test_character_catalog test_generated_character_assets test_hf_video_provider
```

대표 영상:

```text
D:\capstone\soft_capston-main\output\action_previews_v28_round5_final\female_02_battle_v29.mp4
```

최종 개선에 필요한 최소 작업은 15명에 대해 실제 battle 전용 원본 포즈를 추가로 제작하고, 각 캐릭터의 weapon/defense semantics를 manifest와 함께 등록하는 것입니다. 그 전까지는 v28을 **기술적으로는 승인하되, 전투 동작 품질은 조건부 승인**으로 유지합니다.
