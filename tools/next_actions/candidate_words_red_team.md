# 추가 동사 후보 레드팀 판정

- 대상: `male_01`
- 목적: 후보를 늘리는 것이 아니라, 다음 구현 라운드에서 실패 가능성이 낮은 순서를 정한다.
- 근거: `candidate_words_language.md`, `candidate_words_assets.md`, `candidate_words_motion.md`, `candidate_words_implementation.md` 및 실제 motion sheet/contact preview 확인.
- 점수: 모든 항목 0~5점, 높을수록 좋다. `의존성`은 배경·소품 의존성이 낮을수록 높은 점수다. 총점은 참고용이며, 실제 실패가 확인된 후보는 총점과 관계없이 차단한다.

## 최종 추천 Top 3

1. **무릎 꿇다 (`kneel`)**: **1순위**. `male_01_sit_cycle_v1.png`의 무릎을 낮춘 포즈를 분리해 쓸 수 있고, 전신 실루엣과 지면 접점이 한 장면에서 읽힌다. 앉기와 섞이지 않도록 `한쪽/양쪽 무릎 접촉 -> 상체를 세운 hold -> stand 회복` 계약만 지키면 된다.
2. **절하다 (`bow`)**: **2순위**. 새 sheet가 필요하지만 상대·소품·배경이 없어도 성립하며, 발을 고정한 몸통 하강과 upright 회복만으로 의미가 완결된다. `stand` 재생으로 대체하지 말고 전용 cycle을 만든다.
3. **박수치다 (`clap`)**: **3순위**. `action_sheet`의 양손 모음 포즈를 접촉 키의 참고로 쓸 수 있고, 양손 벌림-손바닥 접촉-반동의 짧은 반복으로 판독 가능하다. 다만 손 접촉이 마법 준비나 건네기처럼 보이지 않도록 새 손 포즈가 필요하다.

`bow`와 `clap`은 동점이지만, `bow`가 정확한 손 접촉과 반복 주기를 요구하지 않아 먼저다. `dance`는 판독성은 높지만 반복 전신 cycle과 균형 검증 범위가 커서 Top 3에서 내렸다. `crawl`은 세 보고서의 낙관적인 정책 순위보다 실제 실패 preview를 우선해 내렸다.

## 후보별 점수와 판정

| 후보 | 혼자 | 판독 | 재사용 | 연속성 | 의존성 낮음 | 난이도 낮음 | 합계 | 레드팀 판정 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 무릎 꿇다 / kneel | 5 | 5 | 4 | 5 | 5 | 4 | **28** | **1순위**. sit 셀 보정 후 즉시 품질 렌더 |
| 절하다 / bow | 5 | 5 | 2 | 5 | 5 | 3 | **25** | **2순위**. 새 전용 cycle 필요 |
| 박수치다 / clap | 5 | 4 | 3 | 5 | 5 | 3 | **25** | **3순위**. 새 손 접촉 포즈 필요 |
| 웅크리다 / crouch | 5 | 3 | 3 | 5 | 5 | 3 | 24 | 보류. jump 준비·착지와 혼동 |
| 기지개를 켜다 / stretch | 5 | 4 | 1 | 5 | 5 | 3 | 23 | 보류. 직접 재사용 pose 없음 |
| 가리키다 / point | 5 | 4 | 2 | 5 | 4 | 3 | 23 | 보류. 검지와 정적 목표가 필요 |
| 춤추다 / dance | 5 | 5 | 1 | 5 | 4 | 2 | 22 | 보류. 전용 8~12 frame cycle 필요 |
| 기어가다 / crawl | 5 | 2 | 2 | 4 | 5 | 2 | 20 | **차단**. 기존 출력이 떠 보임 |
| 고개를 끄덕이다 / nod | 5 | 2 | 1 | 5 | 5 | 2 | 20 | 보류. 중경·얼굴 해상도 전용 |
| 넘어지다 | 5 | 4 | 1 | 4 | 3 | 2 | 19 | 보류. 낙상·부상 오독 위험 |
| 미끄러지다 / slide | 5 | 4 | 1 | 4 | 2 | 2 | 18 | 보류. 지면/회복 연출 의존 |
| 숨다 / hide | 3 | 5 | 1 | 5 | 1 | 2 | 17 | 보류. 가림막·occlusion 필수 |
| 구르다 | 5 | 4 | 1 | 4 | 2 | 2 | 18 | 보류. 경사·회전·회복이 필요 |
| 기어오르다 / climb | 3 | 2 | 1 | 4 | 1 | 1 | **12** | **차단**. 현재 preview가 실제 등반이 아님 |

### 판정 메모

- **crawl**: `male_01_crawl_cycle_v1.png`를 직접 보면 몸통·손·무릎 아래에 분리된 그림자가 있고 지면 접촉이 약하다. `male_01_crawl_v1_contact.png`에서도 프레임이 떠 있거나 낮게 돌진하는 모습으로 보여, 기어가기의 핵심인 네 지지점 교대가 안정적으로 읽히지 않는다. 기존 파일이 있다는 이유로 재사용 점수를 높이지 않는다.
- **climb**: `male_01_climb_cycle_v1.png`에는 손잡이를 잡고 몸이 상승하는 연속 포즈가 없다. 실제 `male_01_climb_v1_contact.png`는 벽 앞에서 달리거나 점프하는 장면에 가깝다. 과거 실패를 반영해, 벽·손·발 접점·수직 높이 변화가 모두 확인되기 전에는 구현 후보로 채택하지 않는다.
- **kneel**: sit sheet의 관련 셀은 유용하지만 그대로 반복하면 sit으로 합쳐질 수 있다. 엉덩이가 좌면에 내려가지 않고 무릎 접촉 뒤 상체가 세워져야 한다.
- **crouch**: jump sheet의 낮은 자세는 재사용 가능성이 있으나 jump prepare/landing과 구분되지 않는다. `hide`의 준비 포즈로 먼저 쓰는 편이 안전하다.
- **dance**: 혼자 수행하고 시각성도 높지만, wave/magic/battle 셀을 반복하면 의미가 왜곡된다. 새 전신 cycle과 좌우 중심 유지 검증 없이는 만들지 않는다.
- **hide**: 상대는 불필요하지만 나무·바위·덤불·기둥 같은 가림막이 행동의 원인이다. 캐릭터가 사라지는 효과만으로는 채택하지 않는다.
- **slide**: 혼자 가능하지만 설원·젖은 바닥·갑판 같은 지면과 균형 회복이 함께 있어야 한다. 넘어지다로 오독되지 않는 회복이 필요하다.
- **point**: 열린 손은 기존 시트에서 참고할 수 있지만 검지 방향성이 없다. 성문·빛·바위 같은 정적 목표를 넣지 않으면 손 내밀기와 구분이 약하다.
- **nod**: 의미는 solo지만 전신 원경에서 머리 변화가 너무 작다. 중경 전용 후보로만 보류한다.
- **stretch**: 발 고정과 머리 위 팔의 최대 신장이 핵심인데 직접 재사용할 기존 pose가 없다. 점프처럼 보이지 않게 두 발 이탈을 금지해야 한다.
- **넘어지다/구르다**: 보고서에 근거는 있으나 접지·회복·안전한 동화풍 연출의 실패 비용이 높다.

## 다음 단계 실행 범위

### 바로 렌더할 단어

1. **무릎 꿇다**: 기존 `sit` sheet의 관련 셀을 분리한 진단용 preview를 먼저 만든다. 새 motion sheet를 대량 제작하기 전에 sit과의 실루엣 차이, 무릎 접점, ground shadow를 확인한다.
2. **절하다**: kneel 진단이 통과하면 새 `bow` sheet를 만들고 바로 전용 cycle preview를 렌더한다. `stand` fallback은 금지한다.
3. **박수치다**: bow의 stationary 전용 cycle 검증이 통과한 뒤 새 `clap` sheet를 렌더한다. 손바닥 접촉 hold와 두 번째 반복까지 확인한다.

### 아직 에셋을 만들지 말아야 할 단어

- **기어가다**: 기존 crawl sheet/preview의 ground contact와 지면 anchor를 먼저 고치는 별도 수리 테스트가 필요하다. 수정 전 새 에셋을 만들지 않는다.
- **기어오르다**: 현재 climb sheet를 폐기하지는 않지만, 새 벽 접점·상승 경로가 없는 상태에서 추가 에셋 제작을 시작하지 않는다.
- **춤추다, 기지개를 켜다, 가리키다, 고개를 끄덕이다, 웅크리다**: 후보 정의와 구도는 남기되 Top 3 preview의 실패 기준이 확정될 때까지 새 sheet를 만들지 않는다.
- **미끄러지다, 숨다, 넘어지다, 구르다**: 지면·가림막·경사 같은 scene-dependent 트랙으로 분리하고, solo action에 섞지 않는다.

## 기존 에셋 재사용과 신규 에셋

| 구분 | 후보 | 사용할 수 있는 기존 근거 | 필요한 보정/제약 |
|---|---|---|---|
| 재활용 가능성이 가장 높음 | `kneel` | `male_01_sit_cycle_v1.png`의 row-major cell 2, 6 | 셀 추출, 하강·회복 연결, 무릎 접촉 hold, sit과 다른 엉덩이 높이 |
| 진단용으로만 재활용 | `crouch` | `male_01_jump_cycle_v19.png` cell 0, 6 | jump prepare/landing과 분리된 hold가 먼저 필요 |
| 수리 후 재평가 | `crawl` | `male_01_crawl_cycle_v1.png` 및 기존 crawl preview | 손·무릎 접촉, body-root anchor, 그림자 위치, 수평 이동을 모두 보정 |
| 파일은 있으나 재사용 승인 불가 | `climb` | `male_01_climb_cycle_v1.png` 및 climb preview | 현재 포즈는 실제 등반이 아니므로 벽 접점과 상승 cycle을 새로 확보 |
| 참고 포즈만 재사용 | `clap`, `point` | `action_sheet`의 양손 모음·손 내밈, `interaction_cycle`의 열린 손 | 박수 손바닥 접촉·반동, point 검지 포즈는 신규 제작 |
| 새 에셋 필요 | `bow`, `dance`, `stretch`, `nod`, `slide`, `hide` | 기존 sheet에 완성 cycle 없음 | 각 후보의 prepare-act-recover와 전후 hold를 가진 전용 sheet 필요 |

엄격한 의미의 “기존 에셋만으로 즉시 승인” 후보는 **없다**. 이번 라운드의 재사용은 `kneel`을 검증용으로 재구성하는 수준이며, 기존 파일이 있다는 사실만으로 crawl/climb을 승인하지 않는다.

## 실제 테스트용 짧은 프롬프트

### Top 3

- **kneel**: `male_01, blue tunic and red cape, full body 3/4, stand -> lower one knee to the ground -> upright kneel hold -> stand recovery, fixed feet and ground shadow, no chair, no jump, transparent 4x2 motion sheet`
- **bow**: `male_01, full body 3/4, both feet planted, torso and head bow forward, deepest bow hold, return upright, keep face costume and cape consistent, no partner, no object, no waving`
- **clap**: `male_01, stationary full body 3/4, arms open -> palms meet at chest -> rebound -> second clap -> neutral recovery, clear hand contact, no magic glow, no sword, fixed ground anchor`

### 실패 원인 확인용 재테스트

- **crawl 수리 gate**: `male_01 crawling through a low forest passage, hands and knees visibly touch the ground, body stays grounded, shadow directly under body, alternating opposite hand and knee, horizontal motion only, no jumping or floating`
- **climb 보류 gate**: `male_01 climbing a fixed stone wall, one hand grips a visible hold, opposite foot presses a visible foothold, torso rises vertically across frames, continuous wall contact, no running or jumping`

모든 테스트에서 `male_01`의 얼굴·파란 튜닉·붉은 망토·부츠·비율을 유지하고, `prepare -> act -> recover`와 의미가 결정되는 hold를 확인한다. 이 보고서는 해당 레드팀 파일만 추가하며 공용 provider, 기존 에셋, 다른 보고서는 수정하지 않는다.
