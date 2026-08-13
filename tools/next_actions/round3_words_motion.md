# Round 3 신규 동작 후보: 모션/품질 설계 보고서

- 역할: 모션/품질 설계자
- 작성일: 2026-08-10 (KST)
- 대상 캐릭터: `male_01`
- 목적: 다음 에셋·영상 제작팀이 신규 동작을 바로 테스트할 수 있도록 작은 화면 판독성, 정지/이동 구분, 기존 동작과의 오인 위험, `prepare -> act -> hold -> recover` 계약을 정의한다.

## 범위와 제외 목록

이번 라운드의 신규 후보에서는 이미 다룬 다음 단어를 제외한다.

`walk/run`, `jump`, `investigate`, `magic`, `wave`, `sit`, `stand`, `stop`, `kneel`, `bow`, `crouch`, `stretch`, `clap`, `point`, `nod`, `dance`, `crawl`, `climb`, `slide`, `hide`, `fall_roll`

기존 후보의 변형명으로 새 동작을 가장하지 않는다. 예를 들어 `몸을 숙여 살피다`는 `investigate`, `웅크리다`는 `crouch`, `미끄러져 넘어지다`는 `slide` 또는 `fall_roll` 계열로 처리한다.

## 공통 판독 규격

### 작은 화면 테스트

- 무라벨 영상으로 `320x180`과 `160x90` 두 크기를 만든다. 배경은 고정하고 카메라 팬·줌·화면 흔들림을 끈다.
- 0.8초 동안의 준비와 첫 의미 포즈만 본 뒤, 관찰자가 동작명을 고르게 한다. `3명 중 2명`이 맞히지 못하면 보류한다.
- 얼굴·손처럼 작은 부위가 핵심인 후보는 `160x90` 전신 단독 통과를 요구하지 않는다. `320x180` 중경에서 읽히고 전신 원경에서는 보조 동작으로만 사용한다.
- 의미가 결정되는 `hold`는 24fps 기준 최소 6프레임, 반복 동작은 첫 반복과 두 번째 반복 사이의 간격이 같은지 확인한다.

### 정지와 이동의 계약

- 정지 동작: 발바닥과 body root가 화면 폭의 3% 이상 옮겨가지 않는다. 움직임은 상체·머리·팔·호흡처럼 캐릭터 내부에서 발생해야 한다.
- 이동 동작: 발의 교대 또는 실제 root 이동이 있어야 한다. 배경만 움직여 이동처럼 보이게 만들지 않는다.
- 정지 후보에서 발이 미끄러지거나 shadow가 몸에서 떨어지면 실패다. 이동 후보에서 두 발이 계속 같은 위치에 남으면 정지 포즈의 흔들림으로 판정한다.
- 모든 후보는 neutral 상태에서 시작하고, 마지막에는 다음 행동으로 붙일 수 있는 recover 또는 안정된 neutral로 돌아온다.

### 공통 품질 gate

1. **실루엣 gate**: 단색 캐릭터 실루엣만 보아도 핵심 신체 변화가 확인된다.
2. **상태 gate**: `prepare`, `act`, `hold`, `recover` 네 구간이 프레임 순서상 분리된다.
3. **접지 gate**: 발·무릎·몸통·수면 등 실제 접촉점과 shadow가 일관된다.
4. **오인 gate**: 기존 제외 목록 중 가장 가까운 두 동작과 side-by-side로 비교해 2/3 이상 구별된다.
5. **정체성 gate**: 파란 튜닉, 붉은 망토, 부츠, 얼굴 비율과 무기 유무가 프레임 사이에서 유지된다.

## A. 엄격한 solo 후보

아래 후보는 상대나 특정 물체 없이 캐릭터 한 명만으로 수행할 수 있다. 배경은 분위기를 보탤 수 있지만, 동작 의미의 필수 조건으로 사용하지 않는다.

| 우선순위 | 동작 | 모션 모드 | 작은 화면 판독성 | 핵심 오인 위험 | 판정 |
|---:|---|---|---|---|---|
| 1 | **경례하다** | stationary | 높음. 이마와 팔의 삼각 실루엣 | `investigate`, `wave`, `magic` | 신규 제작 1순위 |
| 2 | **엎드리다** | stationary | 높음. 몸통의 수평 접지 | `crawl`, `fall_roll`, `hide` | 신규 제작 추천 |
| 3 | **비틀거리다** | locomotion | 중간~높음. 좌우 중심 이탈과 발 회복 | `walk/run`, `slide`, `fall_roll` | 이동 후보 추천 |
| 4 | **깨어나다** | stationary transition | 중간. 누운/낮은 시작 자세가 필요 | `sit`, `stand`, `jump` | 시작 상태 고정 시 추천 |
| 5 | **숨을 고르다** | stationary | 중간. 어깨·가슴의 반복이 핵심 | `stop`, `investigate`, `crouch` | 중경·전신 보조용 |
| 6 | **잠들다** | stationary | 중간. 눈보다 머리·상체 처짐을 크게 설계 | `sit`, `stop`, `hide` | 장면 전환용 |
| 7 | **하품하다** | stationary | 중간 이하. 얼굴 중심이라 전신 원경에서 약함 | `stretch`, `magic`, `먹다` | 중경 전용 보조 후보 |
| 8 | **재채기하다** | stationary | 중간 이하. 소리 없이도 어깨 반동이 보여야 함 | `bow`, `nod`, `magic` | 짧은 변주 후보 |

### 1. 경례하다

- **읽히는 핵심**: 한 손이 이마 옆에 닿고 팔꿈치가 옆으로 벌어진 채, 발은 고정된다. 손을 얼굴 앞에서 흔들지 않는다.
- **정지/이동**: stationary. 두 발과 body root를 고정하고 팔과 짧은 고개 방향만 움직인다.
- **단계**: `prepare` 중립에서 어깨와 팔꿈치를 올린다 -> `act` 손을 이마 옆으로 빠르게 가져간다 -> `hold` 6~10프레임 동안 팔꿈치와 손 위치를 유지한다 -> `recover` 손을 내리고 neutral로 돌아온다.
- **품질 gate**: 160x90에서도 팔꿈치와 손이 얼굴에 붙은 점이 보여야 한다. 팔이 머리 위로 올라가면 `stretch`, 손이 좌우로 반복되면 `wave`, 이마에서 시선이 좌우로 크게 움직이면 `investigate`로 오인되므로 실패다.
- **테스트 프롬프트**: `male_01, full body 3/4, stationary military salute, raise one hand to the temple, elbow clearly out, hold the salute, lower the hand, fixed feet and ground shadow, no waving, no scanning, no magic glow, transparent 4x2 motion sheet`

### 2. 엎드리다

- **읽히는 핵심**: 가슴과 배가 지면에 가까워지고 팔이 몸 앞 또는 옆에 놓인다. 네 발 교대나 구르기가 없어야 한다.
- **정지/이동**: stationary. 내려간 뒤에는 수평으로 이동하지 않는다.
- **단계**: `prepare` 서 있거나 낮은 neutral에서 무릎을 굽힌다 -> `act` 손을 먼저 짚고 상체를 낮춰 가슴을 지면 쪽으로 보낸다 -> `hold` 몸통·팔·다리의 낮은 수평 자세를 유지한다 -> `recover` 팔로 몸을 밀어 낮은 neutral 또는 upright neutral로 돌아온다.
- **품질 gate**: 옆면 또는 3/4에서 몸통의 최고점이 무릎보다 낮아야 하며, shadow는 몸통 아래에 붙어야 한다. 손·무릎 교대가 생기면 `crawl`, 등부터 닿거나 회전하면 `fall_roll`, 가림막 뒤로 사라지면 `hide`로 오인된다.
- **테스트 프롬프트**: `male_01, full body side 3/4, stand to lie face down on the ground, hands and torso visibly contact the ground, prone hold, push up and recover, no crawling, no rolling, no cover object, fixed camera and ground shadow`

### 3. 비틀거리다

- **읽히는 핵심**: 이동 중 중심이 좌우로 크게 흔들리고, 한 발이 늦게 따라와 균형을 회복한다. 완전히 넘어지지 않는 것이 핵심이다.
- **정지/이동**: locomotion. 짧은 구간이라도 root가 화면 폭의 8% 이상 옮겨지고 발 위치가 바뀐다.
- **단계**: `prepare` 느린 중립 보폭을 시작한다 -> `act` 한쪽으로 어깨와 골반을 기울이며 발을 엇디딘다 -> `hold` 가장 큰 기울기에서 한 발을 내밀어 균형을 잡는 순간을 6프레임 유지한다 -> `recover` 몸을 세우고 정상 neutral 보폭으로 멈춘다.
- **품질 gate**: 발이 바닥을 스치고 shadow가 발을 따라가야 한다. 계속 일정한 보폭이면 `walk/run`, 바닥으로 주저앉으면 `slide` 또는 `fall_roll`, 좌우 이동 없이 몸만 흔들리면 실패다.
- **테스트 프롬프트**: `male_01, full body 3/4 walking alone on a forest path, stagger sideways twice, arms counterbalance, one foot catches balance, recover upright without falling, visible foot travel and ground shadow, no running, no sliding, no rolling`

### 4. 깨어나다

- **읽히는 핵심**: 닫힌 눈과 처진 머리의 휴식 상태에서 시선과 상체가 순서대로 올라오며 주변을 인식한다. 시작 상태가 명확해야 한다.
- **정지/이동**: stationary transition. 시작과 끝의 root를 고정하고, 마지막에 일어서기나 이동으로 이어지지 않게 한다.
- **단계**: `prepare` 누워 있거나 몸을 낮춘 휴식 자세, 눈 감기와 머리 처짐 -> `act` 눈과 머리가 먼저 들리고 손으로 지면을 짚는다 -> `hold` 상체를 세운 깨어난 자세와 정면 시선을 유지한다 -> `recover` 손을 내리고 안정된 낮은 neutral로 돌아온다.
- **품질 gate**: 첫 프레임에서 잠든 상태, 중간에서 눈·머리의 상승, 마지막에서 alert hold가 구별되어야 한다. 곧바로 튀어 오르면 `jump`, 좌면에 엉덩이를 두면 `sit`, 완전 직립까지 가면 `stand`과 섞이므로 실패다.
- **테스트 프롬프트**: `male_01, full body 3/4, start lying on the ground asleep, eyes and head lift first, brace with one hand, sit into an alert low upright pose, hold awake gaze, no jump, no standing, no bed required, fixed camera`

### 5. 숨을 고르다

- **읽히는 핵심**: 큰 동작 뒤 어깨와 가슴이 두 번 이상 들썩이고, 손은 무릎 또는 가슴에 잠깐 놓인다. 몸의 회복이 목적이다.
- **정지/이동**: stationary. 달리기에서 들어올 수 있지만 본 동작 구간에서는 발과 root를 고정한다.
- **단계**: `prepare` 동작을 끝내며 몸을 약간 앞으로 기울인다 -> `act` 손을 무릎 또는 가슴에 대고 어깨를 올린다 -> `hold` 두 번의 호흡 주기와 짧은 안정 hold를 보여준다 -> `recover` 상체를 세우고 팔을 자연스럽게 내린다.
- **품질 gate**: 320x180 중경에서 어깨의 상승·하강이 두 번 읽혀야 한다. 완전히 멈춰 있으면 `stop`, 한 지점을 탐색하면 `investigate`, 무릎을 깊게 접으면 `crouch`로 오인되므로 실패다. 전신 160x90은 보조 판정만 허용한다.
- **테스트 프롬프트**: `male_01, medium full-body 3/4 after a long run, stop in place, hands briefly on knees, shoulders and chest rise and fall twice, catch breath, recover upright, no talking, no crouching hold, no camera movement`

### 6. 잠들다

- **읽히는 핵심**: 시선이 풀리고 머리와 어깨가 천천히 처진 다음, 규칙적인 작은 호흡으로 정지한다. 단순히 멈춰 서 있는 모습과 달라야 한다.
- **정지/이동**: stationary. 발, root, shadow는 끝까지 고정한다.
- **단계**: `prepare` 서 있거나 낮은 neutral에서 눈을 느리게 감고 팔을 이완한다 -> `act` 머리가 한쪽으로 기울고 상체가 처진다 -> `hold` 눈 감은 휴식 자세와 2회의 작은 호흡을 유지한다 -> `recover` 눈을 뜨고 고개를 들어 neutral로 복귀한다.
- **품질 gate**: 320x180 중경에서 눈 감김 또는 머리 처짐 중 하나와 호흡 중 하나가 보여야 한다. 발이 이동하거나 팔을 크게 머리 위로 올리면 `stop` 또는 `stretch`로 읽히므로 실패다. 침대·의자 사용은 별도 조건부 버전으로 취급한다.
- **테스트 프롬프트**: `male_01, medium 3/4 stationary, eyelids slowly close, head and shoulders droop, relaxed arms, subtle breathing during sleep hold, gently wake to neutral, fixed feet, no bed, no chair, no walking`

### 7. 하품하다

- **읽히는 핵심**: 턱이 크게 열리고 한 손으로 입을 가리거나 양팔이 느슨하게 올라간다. 팔을 머리 위로 곧게 펴지 않아야 한다.
- **정지/이동**: stationary. 얼굴과 상체 중심의 짧은 동작이며 발은 고정한다.
- **단계**: `prepare` 시선이 느려지고 입이 닫힌 neutral -> `act` 턱을 열고 한 손을 입 앞에 올린다 -> `hold` 열린 입·처진 눈·짧은 호흡을 6프레임 유지한다 -> `recover` 입을 닫고 손을 내린다.
- **품질 gate**: 320x180 중경에서 입 또는 손-입 관계가 보이지 않으면 불합격이다. 양팔을 높이 펴면 `stretch`, 손을 앞으로 반복하면 `magic` 또는 `wave`, 손을 입에 붙인 채 물체를 들면 `먹다`로 오인될 수 있다.
- **테스트 프롬프트**: `male_01, medium 3/4 stationary, slow yawn, jaw opens wide, one hand covers the mouth, sleepy eyes, brief hold, hand lowers and face returns neutral, no overhead stretch, no food, no magic effect`

### 8. 재채기하다

- **읽히는 핵심**: 머리와 어깨가 짧고 빠르게 앞으로 튀고, 손이나 팔꿈치가 얼굴 앞을 가린다. 한 번의 명확한 반동 뒤 안정된다.
- **정지/이동**: stationary. 반동은 크지만 위치 이동은 없어야 한다.
- **단계**: `prepare` 코와 어깨 주변의 작은 예비 움직임 -> `act` 머리와 상체가 짧게 접히며 팔꿈치가 얼굴 앞을 가린다 -> `hold` 반동 직후 자세를 6프레임 유지한다 -> `recover` 고개를 들고 팔을 내린다.
- **품질 gate**: 320x180 중경에서 예비 움직임과 한 번의 반동이 모두 보인다. 반복해서 고개를 숙이면 `bow` 또는 `nod`, 손에서 빛이 나오면 `magic`, 이동이 붙으면 `비틀거리다`로 오인된다. 소리나 자막 없이도 통과해야 한다.
- **테스트 프롬프트**: `male_01, medium 3/4 stationary, subtle pre-sneeze pause, one sharp forward sneeze with elbow covering face, brief recoil hold, recover upright, no sound cue, no bow, no nod, no magic glow, fixed feet`

## B. 조건부 solo 및 상호작용 트랙

캐릭터는 혼자 움직일 수 있어도, 아래 동작은 장면의 물체·지형·상대가 의미를 완성한다. 핵심 solo 목록에 섞지 않고 조건부 트랙으로 등록한다.

| 동작 | 필요한 조건 | 정지/이동 | 판독성 | 핵심 gate |
|---|---|---|---|---|
| **헤엄치다** | 물, 수면, 깊이 방향 | locomotion | 높음 | 팔 젓기와 수면 접촉, 수평 이동이 함께 보여야 함 |
| **뛰어넘다** | 낮고 명확한 장애물 | locomotion | 높음 | 장애물의 앞-위-뒤 관계가 한 화면에 있어야 함 |
| **기대다** | 벽·나무·기둥 | stationary | 중간 | 등/어깨 접점과 체중 이동이 보여야 함 |
| **냄새 맡다** | 꽃·약초·흔적 등 냄새의 근원 | stationary | 중간 | 코와 근원 사이 거리, 짧은 반복을 보여야 함 |
| **줍다** | 바닥 물체 | stationary transition | 높음 | 손이 물체에 닿고 물체가 손에 따라 이동해야 함 |
| **열다** | 문·상자·책 등 대상 | stationary transition | 높음 | 손 접촉과 대상의 실제 개방이 동기화되어야 함 |
| **읽다** | 책·지도·문서 | stationary | 높음, 중경 이상 | 시선과 페이지/문서 방향이 고정되어야 함 |
| **먹다 / 마시다** | 음식·컵·병 | stationary | 중간~높음 | 물체가 입까지 이동하고 다시 내려와야 함 |
| **말하다 / 대화하다** | 청자, 대사 또는 명확한 청취 맥락 | stationary | 낮음~중간 | 입·시선·상대 반응 없이는 solo 판정 금지 |
| **싸우다 / 공격하다** | 상대 또는 명확한 표적·무기 | locomotion/action | 높음 | 공격 방향과 표적 반응 없이는 전투로 확정하지 않음 |
| **건네다 / 받다** | 물건과 상대 | stationary interaction | 높음 | 손-물건-상대의 세 점이 같은 시간축에 있어야 함 |
| **안다 / 포옹하다** | 포옹할 상대 | stationary interaction | 높음 | 두 인물의 팔과 몸통 접촉 없이는 성립하지 않음 |

### 조건부 후보의 모션 계약과 테스트 프롬프트

#### 헤엄치다

- **단계**: `prepare` 물가에서 몸을 낮춘다 -> `act` 팔과 다리를 번갈아 저으며 몸을 수면에 띄운다 -> `hold` 수면에 닿은 몸통과 전진을 유지한다 -> `recover` 물가에 손을 짚고 물 밖으로 안정화한다.
- **gate**: 물이 없는 투명 sheet만으로 승인하지 않는다. 수면선, 물결, 캐릭터의 수평 이동이 한 장면에 있고, 육상에서의 `crawl`과 구별되어야 한다.
- **프롬프트**: `male_01 swimming alone across a clear pond, waterline crosses the torso, alternating arm strokes and visible leg kicks, horizontal progress, reach the bank and recover, no walking on water, no crawling, no floating without water contact`

#### 뛰어넘다

- **단계**: `prepare` 장애물 앞에서 두 발을 모아 무게중심을 낮춘다 -> `act` 장애물을 넘으며 두 발이 동시에 지면에서 떨어진다 -> `hold` 장애물 위가 아니라 공중의 짧은 최고점 -> `recover` 장애물 뒤 양발 착지와 균형 회복.
- **gate**: 장애물의 앞·위·뒤가 같은 프레임 축에서 읽혀야 한다. 장애물이 없으면 `jump`로 처리하고, 손을 벽에 대면 `climb`로 분기한다.
- **프롬프트**: `male_01 leaping over a low fallen log on a forest path, clear approach, both feet leave the ground, body passes above the log, land beyond it and recover, no wall, no climbing, no generic jump in place`

#### 기대다 / 냄새 맡다

- **기대다 단계**: `prepare` 벽 옆에 선다 -> `act` 등과 어깨를 벽에 붙이며 체중을 옮긴다 -> `hold` 한쪽 무릎이 풀린 편안한 접촉 자세 -> `recover` 벽에서 몸을 떼고 neutral.
- **냄새 맡다 단계**: `prepare` 근원을 발견하고 고개를 향한다 -> `act` 코를 꽃·약초·흔적 가까이 가져간다 -> `hold` 짧은 두 번의 들이마심 -> `recover` 고개를 들고 근원에서 물러난다.
- **gate**: 기준물 없는 테스트는 승인하지 않는다. 기대기는 접촉점이 없으면 `sit` 또는 `stand`, 냄새 맡기는 근원이 없으면 `investigate` 또는 단순 시선 이동으로 오인된다.
- **프롬프트**: `male_01 leaning against a large tree trunk, back and shoulder visibly contact bark, relaxed weight shift, short hold, push away and recover, no chair, no sitting`
- **프롬프트**: `male_01 kneeling near a glowing herb, lean nose close to the herb, sniff twice, lift head and step back, clear source of scent, no reading, no magic casting, no object transfer`

#### 줍다 / 열다

- **줍다 단계**: `prepare` 바닥의 열쇠나 보물을 발견한다 -> `act` 허리와 무릎을 낮추고 손이 물체에 닿는다 -> `hold` 물체를 손에 쥔 상태 -> `recover` 상체를 세우며 물체를 유지한다.
- **열다 단계**: `prepare` 문·상자·책 앞에서 손을 뻗는다 -> `act` 손잡이·뚜껑·표지를 실제로 움직인다 -> `hold` 열린 틈 또는 펼쳐진 면을 보여준다 -> `recover` 손을 떼고 열린 대상을 유지한다.
- **gate**: 물체의 상태 변화가 없으면 각각 `crouch`/`investigate`, `point`/`magic`의 오인으로 실패한다. 물체가 손에 붙지 않거나 문이 캐릭터 손보다 먼저 열려도 실패다.
- **프롬프트**: `male_01 picking up a bright key from the forest floor, look down, lower body, hand contacts key, key visibly leaves the ground in the hand, stand neutral, no empty-hand gesture`
- **프롬프트**: `male_01 opening an old castle door, hand grips the handle, door visibly rotates open after contact, pause with the doorway revealed, hand releases, no magic, no pushing an invisible object`

#### 읽다 / 먹다 / 마시다

- **읽다 단계**: `prepare` 책·지도·문서를 펼쳐 든다 -> `act` 시선과 얼굴을 페이지에 고정한다 -> `hold` 페이지를 읽는 정지 자세 -> `recover` 문서를 내리고 주변을 본다.
- **먹다·마시다 단계**: `prepare` 음식·컵·병을 손에 든다 -> `act` 물체를 입까지 올린다 -> `hold` 한 모금 또는 한입 후 잠깐 멈춘다 -> `recover` 물체를 내리고 neutral.
- **gate**: 읽기는 페이지가 보이지 않으면 `investigate`, 먹기는 음식이 입에 닿지 않으면 `point` 또는 빈손 동작으로 처리한다. 물체가 프레임 사이에서 변형·소실되면 실패다.
- **프롬프트**: `male_01 reading an open map in a castle library, both hands hold the map, eyes track the page, page orientation stays stable, lower the map to recover, no talking, no pointing, no magic`
- **프롬프트**: `male_01 drinking from a small wooden cup at a camp, cup travels from hand to mouth and back, one clear sip hold, swallow and recover, no empty-hand gesture, no pouring from offscreen`

#### 말하다 / 대화하다 / 싸우다 / 건네다 / 받다 / 안다

- **말하다·대화하다**: 상대의 얼굴, 시선, 대사 또는 반응이 필요하다. 단독 인물의 열린 손만으로는 말하다를 승인하지 않고 `interaction` 또는 conversation scene으로 분리한다.
- **싸우다·공격하다**: 상대 또는 표적의 위치, 공격 방향, 충돌/회피 반응을 같은 영상에 둔다. 무기를 휘두르는 solo sheet만으로는 전투 의미를 확정하지 않는다.
- **건네다·받다**: 주는 사람, 받는 사람, 물체의 세 요소를 같은 타임라인에 유지한다. 손만 내미는 포즈는 실패다.
- **안다·포옹하다**: 두 몸통의 접촉, 팔의 감김, 분리 회복이 필요하다. 팔을 벌리는 단독 포즈는 포옹으로 분류하지 않는다.
- **공통 프롬프트**: `male_01 and a second story character, clear eye contact and turn-taking, one short exchange, visible hand or object contact only where required, hold the relationship, recover apart, no solo interpretation`
- **전투 프롬프트**: `male_01 facing a visible training target, clear attack direction and target reaction, one controlled strike and recovery, no empty background, no generic dance, no magic glow`
- **전달 프롬프트**: `male_01 hands a visible golden key to a second character, key remains between hands during transfer, receiver closes hand, both recover, no invisible object, no waving`
- **포옹 프롬프트**: `male_01 and a second character step together, arms visibly wrap around both torsos, brief embrace hold, separate and recover, no handshake, no solo arms-open pose`

## 제작 우선순위와 중단 조건

1. **경례하다**: 정지 동작의 기준 샘플로 먼저 제작한다. 이마 손 위치와 `investigate` 대비가 통과한 뒤 다른 손 제스처를 진행한다.
2. **엎드리다**: 접지·shadow 품질 기준 샘플로 제작한다. `crawl`과 `fall_roll`의 지면 접촉을 side-by-side로 검수한다.
3. **비틀거리다**: 신규 이동 동작으로 제작한다. `walk/run`의 보폭과 `slide`/`fall_roll`의 바닥 접촉을 동시에 피하는지 확인한다.
4. **깨어나다 / 숨을 고르다**: 중경용 stationary transition으로 제작한다. 전신 원경 canonical action으로 확장하지 않는다.
5. **잠들다 / 하품하다 / 재채기하다**: 표정·상체 품질이 확보된 캐릭터 중경에서만 시험한다. 160x90 무라벨 판독이 약하면 감정/상태 modifier로 남긴다.
6. 조건부 후보는 기준물·소품·상대가 준비된 장면에서만 별도 렌더한다. 의존 요소를 지운 단독 sheet를 solo action으로 승격하지 않는다.

### 즉시 중단할 실패 패턴

- `prepare`가 사라져 첫 프레임부터 의미 포즈인 경우
- `hold`가 6프레임보다 짧아 한 컷에서 의미가 사라지는 경우
- 정지 후보의 발 또는 shadow가 미끄러지는 경우
- 이동 후보가 배경 이동만으로 전진하는 경우
- 손·얼굴·물체가 프레임마다 변형되어 동작보다 에셋 오류가 먼저 보이는 경우
- 기존 동작으로 2/3 이상 잘못 맞히는 경우

이 보고서는 `tools/next_actions/round3_words_motion.md`만 새로 작성하며, 공용 코드와 기존 에셋은 수정하지 않는다.
