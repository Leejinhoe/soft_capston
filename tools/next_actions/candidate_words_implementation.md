# 추가 한국어 동사 후보 구현/정책 검토

- 대상 캐릭터: `male_01`
- 검토 범위: `DB연결 테스트/motion_policy.py`, `hf_video_provider.py`, `visual_vocabulary.py`, 기존 preview renderer 및 현재 에셋
- 기준: 혼자 수행 가능, 한 장면에서 동작 의미가 읽힘, 현재 캐릭터/동화 장면 적합성
- 제한: 공용 provider, 정책, 어휘, 기존 preview renderer와 기존 에셋은 수정하지 않음

## 구조 조사 결과

1. `motion_policy.py:8-16`의 `SOLO_ANIMATION_ACTIONS`는 `journey`, `jump`, `magic`, `investigate`, `wave`, `sit`, `stand`만 허용한다. `is_solo_action_semantics`는 canonical `animation_action`, `participant_count == 1`, `requires_partner/object == false`, 비환경 동작을 함께 검사한다.
2. `visual_vocabulary.py:122-181`에는 `crawling`, `climbing`이 이미 action tag로 있고, `:213-237`의 기본 semantic은 둘 다 `animation_action: journey`로 보낸다. `crawling`은 `interaction_kind: crawl`, `pace: crawl`, `climbing`은 `interaction_kind: climb`, `requires_target: true`, `pace: climb`이다.
3. `hf_video_provider.py:438-552`의 action 선택기는 `journey`를 walk/run 중심으로만 알고 있다. `:600-620` 부근의 pace 정규화도 `walk`/`run` 외 값은 walk 또는 run으로 치환하므로 현재 `crawl`/`climb` semantic만으로는 전용 동작이 선택되지 않는다.
4. provider의 `ACTION_SHEET_ACTIONS`/`ACTION_SHEET_TIMELINES`는 wave, magic, battle, rescue, investigate, interaction에 한정된다(`hf_video_provider.py:132-204`). 전용 cycle 렌더 경로는 jump, battle, magic, interaction/rescue와 journey(run)에만 연결되어 있다(`:2239-2365`).
5. `character_assets.py:4-22`와 `character_seed.py:114-133`의 등록 quality tier에는 battle/magic/interaction만 전용 action cycle로 등록되어 있다. 파일이 있어도 DB profile/provider payload에 자동 연결되는 구조는 아니다.
6. `tools/render_action_video_previews.py`는 현재 jump/wave/magic/investigate와 walk/run만 공용 provider preview로 만들고, `tools/next_actions`의 sit/stand/stop/wave 품질 renderer는 일부 독립 검증기다. 따라서 신규 후보는 반드시 공용 경로 preview와 독립 품질 검증을 분리해 확인해야 한다.
7. `stop`과 `turn`은 어휘 semantic상 `animation_action: idle`인 상태 전환이다. `stop`은 이미 별도 검토된 동작이므로 신규 canonical action 허용 목록에 무조건 넣지 않고 상태 전환 계층으로 유지한다. `turn`은 전용 회전 에셋 부족으로 계속 보류한다.

## 추천 순위

| 순위 | 동사 | 제안 canonical action | solo 판정 | 구현 난이도 | 결론 |
|---:|---|---|---|---|---|
| 1 | 기어가다 | `crawl` | 적합 | 중 | 우선 구현 |
| 2 | 절하다 | `bow` | 적합 | 중상 | 신규 cycle 확보 후 구현 |
| 3 | 춤추다 | `dance` | 적합 | 상 | 후순위 구현 |
| 별도 | 기어오르다/오르다 | `climb` | 조건부 | 중상 | 표면/경로 포함 트랙으로 분리 |
| 별도 | 숨다 | `hide` | 조건부 | 상 | 가림막 포함 트랙으로 분리 |

### 1. 기어가다: 최우선

- **판단 근거:** `participant_count=1`, 상대 불필요, 수평의 낮은 전신 이동이라 측면/3/4 한 장면에서 의미가 명확하다. 숲의 덤불, 낮은 동굴, 무너진 문틈은 동화 장면과 `male_01`의 모험/전사 설정에 자연스럽다.
- **현재 에셋:** `assets/characters/motion_sheets/male_01_crawl_cycle_v1.png`가 이미 있다. `output/video_previews/male_01_crawl_v1.mp4`와 contact도 존재해 별도 품질 검증의 출발점이 있다.
- **정책 설계:** `SOLO_ANIMATION_ACTIONS`에 `crawl`을 추가하는 방향이 가장 명확하다. semantic은 `motion_mode=locomotion`, `animation_action=crawl`, `interaction_kind=crawl`, `participant_count=1`, `requires_partner=false`, `requires_object=false`, `requires_target=false`, `locomotion_kind=crawl`로 고정한다. 현재 `journey + pace=crawl`은 walk로 축약되므로 유지하지 않는다.
- **timeline/renderer:** `prepare -> act -> recover`를 유지하되 8-cell cycle의 네 지지점 교대가 act의 핵심이다. run cycle, target journey route, 카메라 pan을 재사용하지 않고 crawl 전용 pose selector를 둔다. 지면 anchor는 손/무릎 alpha bbox가 아니라 body root 기준으로 별도 검증한다.
- **필요 에셋:** 현재 `male_01` cycle을 우선 연결한다. 품질 통과 후 다른 캐릭터 확장을 위해 `video_crawl_cycle_v1` quality tier, 4x2 metadata, `crawl` motion cell map을 표준화한다.
- **변경 범위:** 어휘 tag/semantic canonical 변경, 정책 허용 action, provider action score/tag/asset payload, 전용 cycle 선택기와 timeline, profile asset 등록. 공용 코드 수정 시 영향 범위는 중간이다.
- **테스트:** `기어가다/기어가/엎드려 기어` 및 활용형 분류, `crawl` solo 통과, partner/object 부여 시 거부, provider plan이 `crawl`로 유지되는지, crawl asset이 없을 때 idle/fallback이 아닌 명시적 미지원 결과인지, 25/50/75% frame의 낮은 자세·교대 접지·지면 고정·캐릭터 동일성을 검증한다. `climb`와 `crawl`이 서로 오분류되지 않는 회귀 테스트가 필수다.

### 2. 절하다: 신규 순수 solo 후보

- **판단 근거:** 상대가 화면에 없어도 자기 몸을 숙였다가 회복하는 행동으로 성립하며, 왕궁/성문/마을/숲의 예의를 표현하기 좋다. prepare-act-recover가 단일 장면에서 읽힌다.
- **현재 에셋:** 전용 bow cycle은 확인되지 않았다. `stand` cycle을 단순 재생하는 것은 허리/머리 중심의 굽힘이 없어 의미가 흐려지므로 권하지 않는다.
- **정책 설계:** `animation_action=bow`, `motion_mode=stationary`, `participant_count=1`, 양쪽 `requires_*` false, `interaction_kind=bow`, `body_focus=full_body`, `temporal_pattern=single`로 추가한다. `wave`나 `conversation`으로 보내지 않는다.
- **timeline/renderer:** stand hold -> torso/head lowering -> deepest bow hold -> upright recovery의 8-cell 전용 cycle. 고정 발/ground anchor, 무기와 스카프의 identity 유지, 과도한 90도 굽힘 방지를 검증한다.
- **필요 에셋:** `male_01_bow_cycle_v1.png` 4x2 이상, 전신 정면 또는 3/4, `prepare/act/recover`가 각각 읽히는 6~8 frame. 성문/궁전 배경 1종으로 clean preview를 만든다.
- **변경 범위:** 신규 vocabulary hint/override, 정책 action, provider action map/alignment/timeline, asset quality tier 및 payload, preview case 추가. 에셋 제작 때문에 중상 난이도다.
- **테스트:** `절하다/고개 숙이다/허리를 굽히다` 활용형 분류, `bow` solo 통과, 다른 인물/대상 없이도 plan 유지, action-sheet fallback 금지, 최저점 hold와 upright 회복, 발 미끄러짐/identity drift 검증.

### 3. 춤추다: 후순위 순수 solo 후보

- **판단 근거:** 혼자 가능하고 한 장면에서 전신 리듬이 읽히며 축제/마법/마을 장면에 어울린다. 다만 춤은 동작의 반복성과 균형이 부족하면 걷기·흔들기·전투와 혼동되므로 현재 후보 중 asset 요구가 가장 크다.
- **현재 에셋:** 전용 dance cycle이나 action-sheet cell은 없다. 기존 `wave` cell을 반복하거나 magic cycle을 재사용하면 의미가 왜곡된다.
- **정책 설계:** `animation_action=dance`, `motion_mode=stationary`, `participant_count=1`, partner/object false, `interaction_kind=dance`, `body_focus=whole_body`, `temporal_pattern=repeated`로 별도 family를 둔다.
- **timeline/renderer:** prepare에서 중심을 잡고, act에서 좌우 step/팔 리듬을 2회 이상 반복, recover에서 neutral/stand로 돌아온다. action-sheet hard swap 대신 dedicated cycle과 optical-flow 인접 프레임을 사용한다.
- **필요 에셋:** `male_01_dance_cycle_v1.png` 8~12 frame, 발 위치가 지면에 고정되는 3/4 전신, 축제 또는 마법 배경. 무기/망토가 얼굴과 팔다리를 가리지 않아야 한다.
- **변경 범위:** 신규 어휘 family부터 asset tier, provider cycle selector, timeline, preview renderer까지 모두 필요하다. 상 난이도다.
- **테스트:** `춤추다/춤을 추다` 활용형, `dance` solo 통과, stationary 유지, 반복 주기와 좌우 중심 안정성, walk/run/wave/battle 오분류 방지, 프레임 간 silhouette IoU와 배경 불변을 검증한다.

## 별도 트랙: 조건부 또는 제외

### 기어오르다/오르다 (`climb`)

- **판단:** 캐릭터는 혼자 수행할 수 있지만 벽·나무·사다리 같은 수직 기준물과 높이 변화가 필수다. 현재 ensemble 자료도 `requires_object=true`로 보는 견해가 있어 핵심 solo action 목록에는 넣지 않는다.
- **근거/에셋:** `assets/characters/motion_sheets/male_01_climb_cycle_v1.png`와 별도 climb preview는 존재한다. 그러나 현재 semantic은 `requires_target=true`만 표현하고, provider는 `pace=climb`를 walk/run 밖 값으로 처리한다. 파일 존재만으로 앱 지원으로 판정할 수 없다.
- **구현 정책:** `climb`를 순수 solo가 아닌 `scene-dependent action`으로 별도 분류하고 `target_type=surface_or_route`와 `requires_object` 또는 동등한 환경 의존 flag를 명시한다. 수직 anchor/path와 배경 기준물 검증을 추가한 뒤에만 허용한다.
- **탈락/보류 이유:** 대상물 없는 단일 캐릭터 장면에서는 기어가기·걷기·점프로 오인될 수 있다. 우선순위는 crawl보다 낮다.

### 숨다 (`hide`)

- **판단:** 상대는 없어도 되지만 나무·바위·덤불·커튼 등 몸을 실제로 가릴 물체가 필수다. 따라서 사용자 기준의 “물체 필수 행동”으로 분리한다.
- **필요 에셋/구현:** `male_01_hide_cycle`뿐 아니라 전후 가림막, occlusion 순서, 부분 노출 frame, camera composition이 필요하다. 현재 provider의 object interaction과도 의미가 다르므로 interaction으로 억지 매핑하지 않는다.
- **탈락 이유:** 캐릭터가 사라지는 효과만으로는 숨다를 읽을 수 없고, 물체/레이어 합성 없이는 한 장면 판독성이 보장되지 않는다.

## 명시적 제외 목록

- **대화하다/말하다:** listener 또는 장면 상대가 의미를 완성하고 현재 provider는 `conversation`/secondary character 경로를 사용한다.
- **싸우다/공격하다/맞붙다:** 상대 또는 명확한 target이 필요하고 `battle` cycle은 전투 대상 의미를 전제로 한다.
- **건네다/건네받다/열다/닫다/먹다:** 물체 또는 handoff가 필요하며 `interaction`/object transfer 경로로 분류한다.
- **웃다/울다/기다리다/바라보다:** 현재 전신 motion 한 장면에서 독립 동작으로 읽히기보다 표정·정지 상태·investigate와 겹친다. 신규 canonical action으로 추가하지 않는다.
- **turn:** 전용 회전 시트가 없고 기존 검수에서 거절된 상태를 유지한다.

## 권장 실행 순서

1. 공용 파일을 수정하기 전에 `crawl`의 canonical contract와 asset payload 이름을 확정한다.
2. `male_01_crawl_cycle_v1.png`를 공용 provider preview 입력으로 연결하는 별도 검증을 만들고, crawl/climb/crawl-vs-run 회귀를 통과시킨다.
3. crawl이 통과한 뒤 `bow` 신규 cycle을 제작한다. dance는 bow의 stationary dedicated-cycle 패턴이 안정화된 후 진행한다.
4. climb/hide는 대상물·가림막을 포함한 scene-dependent 정책으로 별도 backlog에 둔다.

이 보고서 작성 중 기존 공용 코드와 기존 에셋은 수정하지 않았다.
