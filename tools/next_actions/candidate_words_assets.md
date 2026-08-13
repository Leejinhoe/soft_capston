# male_01 추가 동사 후보 에셋 감사

- 감사 대상: `assets/characters/motion_sheets/male_01*`
- 감사 기준: 다른 인물 없이 수행 가능하고, 한 장면의 영상만으로 동작 의미가 읽히며, 현재 `male_01`의 동화풍 스타일과 어울리는가
- 현재 구현으로 제외한 동작: `walk`, `run`, `jump`, `investigate`, `magic`, `sit`, `stand`, `wave`, `stop`
- `turn`은 전용 회전 에셋 부족으로 이미 거절된 상태이므로 재추천하지 않음
- 실제 확인 방법: 원본 시트 직접 확인 및 아래 기존 preview contact sheet 대조
  - `assets/characters/motion_sheets/male_01_action_sheet_v21.png`
  - `assets/characters/motion_sheets/male_01_motion_sheet_v3.png`
  - `assets/characters/motion_sheets/male_01_jump_cycle_v19.png`
  - `assets/characters/motion_sheets/male_01_sit_cycle_v1.png`
  - `assets/characters/motion_sheets/male_01_battle_cycle_v22.png`
  - `assets/characters/motion_sheets/male_01_magic_cycle_v22.png`
  - `assets/characters/motion_sheets/male_01_interaction_cycle_v22.png`
  - `assets/characters/motion_sheets/male_01_climb_cycle_v1.png`
  - `assets/characters/motion_sheets/male_01_crawl_cycle_v1.png`
  - `output/video_previews/male_01_asset_motion_demo_v2_contact.png`
  - `output/video_previews/male_01_climb_v1_contact.png`
  - `output/video_previews/male_01_crawl_v1_contact.png`

## 결론 요약

엄격한 조건을 모두 통과해 **기존 에셋으로 즉시 추천할 후보는 없음**. `action_sheet`의 손 이마 포즈는 이미 `investigate`에 사용되고, 나머지 미사용 포즈는 전투·상호작용에 속하거나 단독 동작으로 의미가 고정되지 않는다. 아래 보정 후보 중에서는 `무릎 꿇다`가 가장 현실적이다.

## 추천 순위

| 순위 | 후보 동사 | 실제 근거 | 분류 | 난이도 | 판단 |
|---:|---|---|---|---|---|
| 1 | **무릎 꿇다** | `male_01_sit_cycle_v1.png`의 row-major cell 2, 6에 한쪽 무릎을 낮춘 자세가 반복됨 | 보정 필요 | 낮음 | 기존 sit 시트에서 해당 셀을 분리해 짧은 내려가기 + hold로 만들 수 있음. 앉기와 구별되도록 무릎과 상체를 유지해야 함. 혼자 수행 가능하고 동화 장면에서 맹세·간청·휴식으로 읽힘. |
| 2 | **웅크리다** | `male_01_jump_cycle_v19.png` cell 0, 6에 낮은 무게중심과 굽힌 무릎이 보임 | 보정 필요 | 낮음~중간 | 점프 사이의 전환 프레임을 그대로 반복하면 점프 준비로 오인될 수 있음. cell hold와 작은 호흡 움직임을 별도로 설계하면 단독 자세로 읽힐 가능성이 높음. |
| 3 | **기어가다** | `male_01_crawl_cycle_v1.png` 전 셀이 몸을 수평으로 낮춘 이동 포즈임. `male_01_crawl_v1_contact.png`에서는 캐릭터가 지면 위로 떠 보임 | 보정 필요 | 중간 | 혼자 수행 가능하고 후보 의미는 분명하지만, 손·무릎의 지면 접촉과 진행 방향이 약하다. 지면 기준점, 크기, 팔·다리 교대감 보정 없이는 날아가거나 엎드려 돌진하는 동작으로 읽힘. |
| 4 | **뛰어넘다** | `male_01_climb_cycle_v1.png`는 이름과 달리 손으로 벽을 잡는 프레임 없이 달리기·도약·착지 포즈를 포함함. `male_01_asset_motion_demo_v2_contact.png`에서 장애물 앞 도약 장면으로 조합 가능 | 조건부 보정 | 중간 | 캐릭터 에셋만으로는 부족하고, 화면에 명확한 낮은 장애물과 도약 전후 타이밍이 필요하다. 물체/장애물 의존 동작이므로 solo 후보의 본순위보다 낮춤. `오르다/기어오르다`로 부르면 실패. |

## 기존 에셋으로 바로 만들 수 있는 후보

### 없음: 엄격 판정

- `male_01_action_sheet_v21.png` cell 0~7은 현재 또는 별도 분류 동작으로 모두 의미가 배정되어 있다.
  - cell 0: idle
  - cell 1: `wave` (현재 구현)
  - cell 2: `investigate` (현재 구현; 손을 이마에 대는 포즈를 `경례하다`로 재사용하면 의미 충돌)
  - cell 3: 손을 앞으로 내미는 `handoff` 계열
  - cell 4~5: `magic` (현재 구현)
  - cell 6~7: 칼을 든 `battle` 계열
- `male_01_motion_sheet_v3.png`의 battle/rescue/talking 셀도 실제 장면에서는 칼, 도움 받을 대상, 대화 상대 같은 맥락이 필요하다.
- 따라서 “새 동작이면서 무상대·무필수 물체·한 장면 판독 가능” 기준의 즉시 통과 항목은 비워 두는 것이 정확하다.

## 보정이 필요한 후보

### 무릎 꿇다

- **재활용 에셋:** `male_01_sit_cycle_v1.png` cell 2, 6
- **필요 작업:** 해당 셀 추출, sit과 겹치지 않는 짧은 하강 구간 구성, 무릎이 지면에 닿은 뒤 hold
- **판독성:** 높음. 한 장면에서도 앉은 자세가 아니라 무릎을 꿇은 자세로 구별 가능
- **적합성:** 주인공이 성·숲·마법 공간에서 맹세하거나 간청하는 동화 장면과 잘 맞음
- **탈락 위험:** 셀을 오래 보간하면 sit 동작으로 합쳐질 수 있음

### 웅크리다

- **재활용 에셋:** `male_01_jump_cycle_v19.png` cell 0 또는 6
- **필요 작업:** 점프 cycle에서 독립된 낮은 자세로 추출하고, 발 위치와 그림자 고정, 짧은 hold 추가
- **판독성:** 중간. 손이 지면에 닿는 cell을 쓰면 `착지`와 혼동되므로 피해야 함
- **적합성:** 숲에서 숨을 죽이거나 마법을 피하는 장면에 어울림
- **탈락 위험:** 점프의 시작/착지로 보이면 동사 분류가 불안정함

### 기어가다

- **재활용 에셋:** `male_01_crawl_cycle_v1.png`
- **필요 작업:** ground contact 강화, shadow와 발·손의 기준점 재조정, 지면을 따라 이동하는 속도 조정
- **판독성:** 현재 preview에서는 낮음. `male_01_crawl_v1_contact.png`에서 몸통이 지면에 닿지 않아 `날다` 또는 `돌진하다`처럼 보임
- **적합성:** 동화풍 숲길 장면에는 맞음
- **탈락 위험:** 보정 없이 바로 채택하면 행동 의미가 오독됨

## 새 에셋이 필요한 후보

| 후보 | 근거와 필요한 에셋 | 난이도 | 탈락/보류 이유 |
|---|---|---|---|
| **오르다 / 기어오르다** | `male_01_climb_cycle_v1.png`에 실제 손잡이·발 디딤·상승 연속성이 없음. 벽을 잡고 몸이 위로 이동하는 전용 8-frame cycle 필요 | 높음 | 현재 시트는 climb이라는 파일명과 실제 포즈가 불일치하므로 재사용 불가 |
| **엎드리다** | 지면에 가슴·팔·다리가 닿는 정지 포즈와 엎드려 일어나는 전환 필요 | 중간 | crawl 시트는 공중에 뜬 수평 자세라 엎드리기로 확정하기 어려움 |
| **숨다** | 나무·바위 뒤로 몸이 가려지는 위치 관계와 고개를 내밀었다 숨기는 포즈 필요 | 중간~높음 | 캐릭터 단독 시트만으로는 성립하지 않고 가림막 장면이 필수 |

## 상대·물체 필수라 별도 표시한 후보

이 항목들은 에셋은 확인됐지만 이번 solo 우선순위에서는 제외한다.

| 후보 | 확인한 에셋 | 필수 조건 | 판단 |
|---|---|---|---|
| **건네다 / 내밀다 / 받다** | `male_01_action_sheet_v21.png` cell 3, `male_01_interaction_cycle_v22.png` cell 2~6 | 상대 또는 전달할 물체 | 손을 내미는 형태만 있고 실제 물체 전달·수령의 전후 관계가 없다. 별도 상호작용 동사로 보류 |
| **말하다** | `male_01_motion_sheet_v3.png` talking cell, `action_sheet`의 열린 손 포즈 | 대화 상대 또는 음성 맥락 | 입 모양과 청자 반응이 없어 한 장면에서 `설명하다`, `손짓하다`, `말하다`를 안정적으로 구별하기 어렵다 |
| **공격하다 / 칼을 휘두르다** | `male_01_battle_cycle_v22.png`, `action_sheet` cell 6~7 | 칼 등 무기, 보통 표적/전투 맥락 | 전투 동작은 읽히지만 사용자가 지정한 상대·전투 제외 범주에 해당. 동화풍에는 맞지만 solo 핵심 후보로는 제외 |
| **구하다 / 구조하다** | `male_01_motion_sheet_v3.png` rescue cell, `interaction_cycle` | 도움 받을 상대 또는 구조 대상 | 손을 뻗는 포즈만으로 구조 의미가 완결되지 않는다 |

## 최종 권고

1. 첫 추가 동작은 `무릎 꿇다`를 선택한다. 기존 `sit` 시트 재활용 비용이 가장 낮고, solo·판독성·동화 적합성 세 기준을 모두 만족시킬 가능성이 가장 높다.
2. 다음은 `웅크리다`를 독립 포즈로 보정한다. 점프/착지와 혼동되지 않는 hold가 핵심이다.
3. `기어가다`는 ground contact를 먼저 고친 뒤 재평가한다.
4. `오르다`, `건네다`, `공격하다`, `말하다`는 이번 범위의 즉시 추천에서 제외하고, 각각 전용 climb sheet, 상호작용 물체·상대, 전투 표적, 대화 연출이 확보될 때 별도 검토한다.
