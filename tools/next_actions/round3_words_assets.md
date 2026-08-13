# Round 3 새 동작 단어 에셋 감사 보고서

## 감사 범위와 판정 규칙

- 확인한 폴더: `assets/characters/motion_sheets`, `assets/characters/motion_sheets/generated`, `assets/characters/motion_sheets/generated_v2`
- 기준 캐릭터: `male_01`. 원본 및 generated 에셋은 실제 PNG를 열어 셀의 자세, 투명 배경, 발 위치를 확인했고, generated/generated_v2의 manifest와 contact sheet도 대조했다.
- 새 후보에서 제외: `walk/run`, `jump`, `investigate`, `magic`, `wave`, `sit`, `stand`, `stop`, `kneel`, `bow`, `crouch`, `stretch`, `clap`, `point`, `nod`, `dance`, `crawl`, `climb`, `slide`, `hide`, `fall_roll`.
- `재사용 가능`은 원본 셀을 그대로 런타임에 연결한다는 뜻이 아니라, 새 cycle의 기준 포즈로 가져와도 의미 충돌과 identity/grounding 문제가 관리되는 경우를 뜻한다.
- 에셋 수는 캐릭터 전용 산출물 기준으로 `1 motion sheet + 1 contact sheet`를 1세트로 계산한다. 일반적인 신규 cycle은 4x2, 8 key pose를 기준으로 한다.

## 실제 폴더 감사 결과

### 기존 원본 시트

| 파일 | 실제로 읽히는 포즈 | Round 3 활용 판정 |
|---|---|---|
| `male_01_action_sheet_v21.png` | cell 0 중립, cell 1 wave, cell 2 손을 이마에 댄 경례형 실루엣, cell 3 양손을 앞으로 내밈, cell 4 가슴 앞 손 모음, cell 5 열린 손 내밈, cell 6~7 검을 든 전투 자세 | 새 의미의 완성 cycle은 아님. cell 0/3/4/5는 참고용, cell 2는 `investigate`의 손-이마 해석과 충돌하므로 단독 재사용 금지 |
| `male_01_motion_sheet_v3.png` | 중립, 이동, 도약/달리기 계열, magic, 전투, 입을 벌리고 팔을 뻗은 강한 표현, wave | 새 후보의 neutral/recovery 참고용. `외치다`나 `말하다`를 solo로 확정할 만큼 입·청자·음성 단서는 없음 |
| `male_01_interaction_cycle_v22.png` | 시선 전환, 한 손 설명 제스처, 양손 내밈, 받는 듯한 양손, 가슴 앞 손 모음, 끈/가슴 쪽 손 | 물체·상대 없는 solo 동작의 완성 근거로 쓰면 안 됨. `기도하다`의 손 모음 참고 정도만 가능 |
| `male_01_sit_cycle_v1.png` | 낮은 squat, 한쪽 무릎 접촉, 앉은 hold | 제외 목록의 sit/kneel/crouch와 의미가 겹치므로 Round 3 새 단어에는 사용하지 않음 |
| `male_01_target_journey_sheet_v4.png` 및 run sheets | 후면 이동/달리기 | 새 후보의 후면 identity 참고만 가능. 독립 동작으로 재사용하지 않음 |

### generated / generated_v2

| 팀 | 실제 포함 동작 | 셀/단계 | 감사 결론 |
|---|---|---|---|
| `team_a_posture` | kneel, bow, crouch, stretch | 각 동작 4x2, `prepare -> act -> hold -> recover`, 8 cells | 모두 제외 목록에 포함. 새 후보에 바로 쓸 미사용 전신 cycle 없음 |
| `team_b_gestures` | clap, point, nod, dance | 각 동작 4x2, 8 cells. v2는 손 접촉, 검지 방향, 턱 하강, 좌우 발 디딤을 명시 | 모두 제외 목록에 포함. gesture language는 참고할 수 있으나 새 동작 완성본은 아님 |
| `team_c_scene_actions` | crawl, climb, slide, hide, fall_roll | 각 동작 4x2, 8 cells. v2에는 지면/벽/가림막 기준선이 review용으로 표시됨 | 모두 제외 목록에 포함. 장면 의존성이 강해 새 solo 후보로 전용할 수 없음 |

`generated_v2`의 PNG는 각 팀 manifest에 기재된 대로 모두 `male_01`의 4x2 투명 RGBA 시트이며, 새 의미를 숨겨 둔 미사용 셀 묶음이 아니다. 특히 Team C의 contact sheet에 있는 wall/cover/ground guide는 캐릭터 셀이 아니라 장면 검수용 정보이므로 캐릭터 단독 동작의 에셋으로 세면 안 된다.

## 우선 검토할 새로운 solo 후보

| 후보 단어 | solo/판독성 | 현재 포즈 재사용 | 예상 에셋 수 | 권장 포즈 단계 | identity / grounding 위험 | 판정 |
|---|---|---|---:|---|---|---|
| **경례하다** (`salute`) | 혼자 가능. 성문, 기사단, 왕궁에서 한 컷만으로 의미가 강함 | action cell 2의 손-이마 자세와 cell 0 중립을 참고. 단 cell 2가 현재 `investigate`로도 읽혀 그대로 연결할 수 없음 | 1세트. 전용 cycle 1개 | `neutral -> 팔꿈치 상승 -> 손 이마 접근 -> 경례 hold -> 손 하강 -> neutral`의 6~8 cells | 손가락/이마 간격이 작으면 wave 또는 investigate로 오독. 발은 세워 두기 쉬워 grounding 낮음 | **1순위. 전용 6~8 pose 보강 후 채택** |
| **기도하다** (`pray`) | 혼자 가능. 성당, 달빛 유적, 마법 전환 장면에서 의미가 읽힘 | action cell 4와 interaction cell 6의 가슴 앞 손 모음을 참고. magic과 섞이지 않게 광원/마법 효과는 제외 | 1세트. 필요하면 중경용 변형 1세트 추가 | `중립 -> 손 모으기 -> 고개 숙임 -> 손 모은 hold -> 시선/고개 회복 -> 중립` 6~8 cells | 손 겹침이 clap/마법 준비와 비슷할 수 있음. 발 고정이 쉬워 grounding 낮음. 얼굴이 작으면 prayer 판독성 하락 | **2순위. 중경 화면 계약과 함께 추천** |
| **기다리다** (`wait`) | 혼자 가능하지만 정적 중립만으로는 한 컷 판독성이 약함. 문 앞, 길목, 약속 장소에서 유용 | action cell 0, stand neutral, interaction cell 0/1을 endpoint 참고로만 사용 | 1세트. 장면 시계/경로 표식은 별도 scene asset 1개가 있으면 좋음 | `중립 -> 주변/먼 길 응시 -> 몸무게 이동 -> 기다림 hold -> 작은 자세 전환 -> 중립` 6~8 cells | 변화가 작아 stand/stop으로 오독. 발은 안정적이나 시선과 시간 단서가 없으면 의미가 사라짐 | **보조 후보. 장면 단서 없이는 보류** |
| **한숨 쉬다** (`sigh`) | 혼자 가능. 모험 뒤 휴식, 실망, 안도의 장면에서 읽힘 | motion cell 0과 interaction cell 6의 가슴 쪽 손을 참고할 수 있으나 직접 재사용 불가 | 1세트. 얼굴/상체 중경 preview 1개 추가 권장 | `중립 -> 어깨/가슴 들숨 -> 고개와 어깨 하강 -> 숨 내쉼 hold -> 회복 -> 중립` 6~8 cells | 작은 얼굴에서는 감정이 약하고, 고개 숙임이 bow로 오독될 수 있음. 하체는 고정 가능 | **3순위. 중경 전용으로 조건부 추천** |
| **고개를 갸웃하다** (`tilt_head`) | 혼자 가능. 수수께끼, 낯선 소리, 요정의 질문에 반응하는 장면에서 읽힘 | 기존 nod v2는 상하 움직임이므로 좌우 기울기 참고로 재사용할 수 없음. action cell 0은 neutral endpoint만 제공 | 1세트. 얼굴 해상도 확인용 contact/중경 preview 1개 | `정면 -> 한쪽 어깨/고개 기울임 -> 눈 고정 hold -> 반대 방향 복귀 -> 중립` 5~6 cells | 전신 화면에서 차이가 작아 nod/neutral로 오독. grounding 자체는 낮은 위험 | **보조 후보. 중경 이상에서만 추천** |

### 우선순위 해석

1. `경례하다`는 사용 장면과 포즈 상징성이 가장 강하고, 기존 cell 2를 활용할 수 있어 신규 제작량이 가장 작다. 다만 `investigate`와의 의미 충돌을 해결하는 새 팔 상승/이마 hold가 필수다.
2. `기도하다`는 손 모음 셀이 이미 있어 identity 유지가 쉽지만, `magic`과 분리하는 시각 계약이 없으면 같은 손 제스처로 합쳐진다.
3. `기다리다`, `한숨 쉬다`, `고개를 갸웃하다`는 solo이지만 정지/표정 중심이라 전신 와이드 화면에서 판독성이 낮다. 새 단어를 늘리는 것보다 중경용 슬롯으로 제한하는 편이 안전하다.

## 상대·물체·장면 의존 후보

| 후보 단어 | 필수 조건 | 재사용 가능한 참고 | 예상 에셋 수 | 필요한 단계/추가물 | 판정 |
|---|---|---|---:|---|---|
| **귀 기울이다** (`listen`) | 들을 소리, 소리의 방향 또는 말하는 상대가 필요. 캐릭터 단독 투명 시트만으로 의미가 완결되지 않음 | 명확한 hand-to-ear 셀은 없음. action cell 0 중립과 motion cell 6의 열린 입/팔 뻗음은 endpoint 참고일 뿐 | 1 character set + 1 scene/audio-cue composite set | `중립 -> 소리 방향 전환 -> 손을 귀로 가져감 -> 귀 기울임 hold -> 소리 쪽 시선 hold -> 회복` 6~8 cells. 손-귀 pose 전용 제작 필요 | 손이 귀가 아니라 이마/가슴에 붙으면 salute/investigate로 오독. 머리와 손의 작은 차이를 위해 중경 필요 | **조건부. hand-to-ear 신규 시트 없이는 채택 금지** |
| **말하다 / 외치다** (`talk/shout`) | 대화 상대, 말풍선, 음성 또는 명확한 외침 맥락이 필요 | motion cell 6의 입 벌림/팔 뻗음은 참고 가능하지만 대화 동작으로 확정할 수 없음 | 1 character set + 상대/말풍선 scene asset 1세트 | `호흡 준비 -> 입 열기/손짓 -> 발화 hold -> 손 회수 -> neutral`; shout는 별도 강한 상체 arc 필요 | 입 모양이 작고 한 장면에서 talk/explain/shout 구분이 약함. grounding은 낮지만 partner/context risk가 높음 | **조건부. solo 핵심 후보에서 제외** |
| **건네다 / 받다** (`offer/receive`) | 물체와 받는 상대가 모두 필요 | action cell 3/5, interaction cell 2~5에 손 내밈/받침 pose가 있음 | 1 character set + 물체 1개 + 상대 composite 1세트 | `물체 인지 -> 손 뻗기 -> 물체 전달/접촉 -> 손 회수` 6~8 cells. 상대의 접근/수령 timing 필요 | 빈손이면 point/talk로 보임. 손-물체 접점과 두 캐릭터 identity/grounding을 동시에 검수해야 함 | **조건부. 상호작용 트랙으로 분리** |
| **줍다** (`pick_up`) | 바닥의 열쇠, 보물, 단서 같은 물체가 필수 | sit/crouch 계열은 제외 목록이고, action cell 0은 서기 endpoint뿐 | 1 character set + 1 prop + 1 ground-composite set | `대상 발견 -> 무릎/허리 굽힘 -> 손-물체 접촉 -> 들어 올림 -> 확인 hold -> 회복` 6~8 cells | crouch/kneel과 겹치며 손과 작은 물체가 가려질 위험. ground contact와 prop anchor가 핵심 | **조건부. 새 전용 pickup pose와 prop anchor 필요** |
| **열다** (`open`) | 문, 상자, 책 등 열릴 대상이 필수 | interaction cell 2~5의 내밈/받침만 참고. 실제 회전·문짝 변화는 없음 | 1 character set + 대상 prop 1개 + scene composite 1세트 | `대상 접근 -> 손잡이 접촉 -> 당기기/밀기 -> 열린 상태 hold -> 뒤로 물러남` 6~8 cells | 손이 빈 공간에 닿으면 의미가 사라짐. 대상의 pivot과 캐릭터 발 고정을 별도 검수 | **조건부. 물체 필수 동작** |
| **읽다** (`read`) | 책, 지도, 문서가 필수 | interaction cell 6의 가슴 앞 손 모음은 참고만 가능. 시선 고정과 페이지는 없음 | 1 character set + 문서 prop 1개 + scene composite 1세트 | `문서 들기 -> 시선 하강 -> 읽기 hold -> 페이지 전환 -> 놀람/확인 -> 닫기` 6~8 cells | 손·문서·얼굴 시선이 모두 작아 와이드 화면에서 약함. prop occlusion 위험 | **조건부. 소품 트랙으로 분리** |
| **먹다 / 마시다** (`eat/drink`) | 음식, 컵, 병 등 소품이 필수 | 직접 재사용할 입-손 pose 없음. interaction cell 6은 가슴 쪽이라 입 접촉이 아님 | 동작별 1 character set + 소품 1개 + scene composite 1세트 | `소품 집기 -> 입으로 이동 -> 접촉 hold -> 내려놓기` 5~6 cells | 입과 소품 접점, 손가림, 액체/음식 상태가 필요. 빈손 재생 시 의미가 완전히 무너짐 | **조건부. 이번 라운드 solo 후보에서 제외** |
| **껴안다** (`hug`) | 안을 상대 또는 큰 물체가 필요 | interaction의 양손 내밈은 접근 참고만 가능. 포옹 hold는 없음 | 1 character set + 상대/대형 prop 1세트 | `팔 벌림 -> 접근 -> 양팔 감싸기 -> hold -> 이완` 5~6 cells | 상대가 없으면 팔 벌림/마법으로 보임. 두 캐릭터의 팔·몸 겹침과 grounding 위험 높음 | **조건부. 상대 필수** |

## 새 전용 시트가 필요한 이유

- 원본 action sheet의 cell 2는 시각적으로 경례에 가깝지만, 프로젝트의 기존 `investigate` 해석과 충돌한다. 한 셀을 두 canonical action의 production asset으로 공유하면 분류 결과가 장면 맥락에 따라 흔들린다.
- `hand-to-ear`는 실제 PNG에서 확인되지 않았다. 따라서 `귀 기울이다`는 “재사용 가능”이 아니라 “neutral만 재사용 가능한 신규 전용 sheet”로 기록한다.
- `neutral`은 모든 cycle의 시작/종료에 재사용 가능한 identity anchor지만, 그 자체는 새 동작이 아니다. `기다리다`처럼 neutral hold에 의존하는 단어는 장면 시간 단서가 별도여야 한다.
- generated_v2의 Team A/B/C 시트는 이미 제외 목록의 동작으로 의미가 고정되어 있다. 해당 시트의 빈 셀이나 contact guide를 새 단어에 돌려 쓰지 않는다.

## Round 3 권고

1. **채택 후보:** `경례하다`를 먼저 새 전용 6~8 pose cycle로 검증한다. action cell 2는 identity/손 위치 참고 및 초기 hold 후보로만 사용한다.
2. **다음 후보:** `기도하다`를 중경 화면 전용으로 검증한다. magic effect, 검, 대상 소품을 제거해 손 모음의 의미를 고정한다.
3. **보조 후보:** `기다리다`, `한숨 쉬다`, `고개를 갸웃하다`는 전신 wide 동작 슬롯이 아니라 중경/표정 슬롯으로 제한한다.
4. **별도 트랙:** `귀 기울이다`, `말하다/외치다`, `건네다/받다`, `줍다`, `열다`, `읽다`, `먹다/마시다`, `껴안다`는 소리·상대·물체·장면을 포함한 조건부 동작으로 관리한다.
5. **현 단계에서 만들지 않을 것:** 기존 제외 목록의 action sheet를 새 이름으로 재라벨링하거나, 경례 셀을 그대로 investigate와 공유하는 것.

## 변경 범위

이번 감사에서는 공용 코드, 기존 PNG, generated/generated_v2 에셋을 수정하지 않았다. 새로 작성한 파일은 이 보고서 하나다.
