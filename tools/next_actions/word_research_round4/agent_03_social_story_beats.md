# 어휘 연구 Round 4: 관계·감정·서사 전환

- 역할: 관계·감정·서사 전환
- 조사일: 2026-08-10 (KST)
- 범위: 한국 어린이 동화에서 인물 간 만남, 신호, 보호, 갈등, 화해로 읽히는 관찰 가능한 동작
- 대상: 향후 visual-action 학습용 후보. 이미지·영상·런타임 코드는 생성하거나 수정하지 않음.

## 방법

기존 `treasure_story_words.md`, `round3_words_language.md`, `round3_words_assets.md`, `round3_words_motion.md`, `generated_round3`, `generated_v2`, `merged_visual_vocabulary.json`을 먼저 대조했다. 이미 구현되었거나 반복 검토된 `wave`, `follow`, `rescue`, `hug`, `offer/receive`, `salute`, `wake`, `yawn`, `sneeze`, `peek`, `listen`, `talk/whisper`, `open`, `unlock`, `pick_up`, `dig`, `pull`, `push` 등은 기본 후보에서 제외했다. 단, `whisper_to_ear`와 `hold_hands`는 기존 의미를 그대로 재제안하지 않고, 파트너와의 접촉 관계가 화면에 명시되는 좁은 visual sense로만 기록한다.

영어 의미와 용례는 Oxford Learner's Dictionaries, Cambridge Dictionary를 우선 확인하고, 어린이 서사 맥락은 British Council LearnEnglish Kids와 PBS KIDS의 친구·도움·전통 이야기 자료를 보조 근거로 삼았다. 모든 후보는 `prepare -> act -> hold -> recover` 순서를 지키며, 상대·표적·소품·위협이 없으면 의미가 무너지는 경우를 보수적으로 낮게 평가했다.

## 상위 추천

| 순위 | 후보 | 분류 | 우선도 | 다음 제작에 필요한 최소 장면 |
|---:|---|---|---|---|
| 1 | 만나다 `meet` | partner-bound | **next asset** | 서로 다른 두 인물이 접근해 마주 보고 멈춤 |
| 2 | 악수하다 `shake_hands` | partner-bound | **next asset** | 두 인물의 오른손 접촉과 짧은 상하 흔들림 |
| 3 | 손짓해 부르다 `beckon` | target-bound | **next asset** | 화면 안 대상에게 손바닥을 안쪽으로 반복 신호 |
| 4 | 지키다/보호하다 `protect` | target-bound | **later asset** | 보호 대상과 위협 사이에 몸을 세우는 장면 |
| 5 | 붙잡아 멈추게 하다 `catch` | target-bound | **later asset** | 움직이는 사람 또는 물체가 손에 실제로 멈춤 |
| 6 | 놓아주다 `release` | target-bound | **later asset** | 잡힘/묶임 상태에서 손을 떼고 대상이 자유롭게 이동 |
| 7 | 항복하다 `surrender` | target-bound | **later asset** | 상대·위협 앞에서 무기/손을 내려놓고 두 손을 듦 |

`next asset`은 단독 캐릭터 sheet가 아니라도 두 인물 합성 장면으로 바로 검증할 가치가 있다는 뜻이다. `later asset`은 표적·위협·소품 타이밍을 먼저 고정해야 한다는 뜻이다.

## 후보 12개

### 1. 만나다 `meet`

- **예문:** 숲길에서 토끼와 여우가 서로 다가와 나무 앞에서 만났다.
- **조건:** partner-bound. 두 인물이 같은 장소에 도착해 서로를 향해야 한다. Oxford는 `meet`을 우연히 같은 장소에 있어 서로 이야기하는 것, 또는 약속해 함께 모이는 것으로 설명한다. [Oxford: meet](https://www.oxfordlearnersdictionaries.com/definition/english/meet_1)
- **시각적 이유:** 두 root가 양쪽에서 접근하고, 서로 마주 보는 정지 hold가 생겨 `follow`나 단순 `journey`와 분리된다.
- **계약:** `prepare` 두 인물이 화면 양끝에서 상대를 향해 선다 -> `act` 서로 접근한다 -> `hold` 일정 거리에서 마주 보고 시선을 맞춘다 -> `recover` 다음 대화·악수·동행으로 이어질 수 있는 중립 자세.
- **혼동/negative cue:** 한 인물만 뒤를 따라가면 `follow`, 뒤에서 쫓으면 `chase`, 만나지 않고 지나가면 `journey`다. 두 인물이 실제로 같은 위치에 모이지 않는 컷은 실패.
- **우선도:** **next asset**. 어린이 이야기에서 “새 친구를 만남”과 “구조자를 만남”을 모두 열지만, 반드시 2인 합성으로 검증한다.

### 2. 악수하다 `shake_hands`

- **예문:** 왕자와 숲의 수호자는 약속을 지키기로 악수했다.
- **조건:** partner-bound. 두 사람이 마주 보고 손을 맞잡아야 한다. Cambridge는 서로 마주 본 두 사람이 손을 잡고 위아래로 움직이는 인사 또는 합의의 표현으로 정의한다. [Cambridge: shake hands](https://dictionary.cambridge.org/us/dictionary/english/shake-hands)
- **시각적 이유:** 손-손 접촉과 짧은 상하 반복이 명확해 빈손 내밀기와 구별된다.
- **계약:** `prepare` 두 인물이 한 걸음 거리에서 서로의 오른손을 내민다 -> `act` 손이 맞닿고 맞잡힌다 -> `hold` 맞잡은 손을 1~2회 짧게 흔든다 -> `recover` 손을 놓고 상대를 바라본다.
- **혼동/negative cue:** 손만 내밀고 접촉이 없으면 `offer/receive` 또는 `point`, 좌우로 흔들면 `wave`, 한 인물의 이마에 손이 가면 `salute`다. 물건이 손 사이를 오가면 악수로 판정하지 않는다.
- **우선도:** **next asset**. 새 친구·동맹·화해의 사건 전환을 한 컷에 담을 수 있다.

### 3. 손짓해 부르다 `beckon`

- **예문:** 요정은 멀리 있는 아이에게 숨은 오솔길로 오라고 손짓했다.
- **조건:** target-bound. 신호를 받는 인물이나 동물이 화면 안에 있어야 한다. Cambridge는 가까이 오라는 뜻을 손이나 머리의 움직임으로 알리는 것으로 정의한다. [Cambridge: beckon](https://dictionary.cambridge.org/us/dictionary/english/beckon)
- **시각적 이유:** 손바닥을 자신 쪽으로 반복해서 당기는 동작은 `wave`의 좌우 흔들기와 방향성이 다르다.
- **계약:** `prepare` 시선이 먼 대상에 고정되고 팔꿈치를 든다 -> `act` 손바닥을 안쪽으로 두 번 당긴다 -> `hold` 대상과 눈을 맞춘 채 손을 낮춘다 -> `recover` 대상이 오거나 다음 행동으로 연결될 중립 자세.
- **혼동/negative cue:** 좌우 손 흔들기는 `wave`, 한 방향을 가리키고 끝내면 `point`, 대상 없이 손을 앞에서 움직이면 `magic` 또는 설명 제스처다. 대상의 위치와 응답이 없으면 보류.
- **우선도:** **next asset**. 기존 `wave`와의 red-team 비교를 전제로 전용 손 궤적을 만든다.

### 4. 지키다/보호하다 `protect`

- **예문:** 용사는 작은 여우 앞에 서서 폭풍의 돌멩이를 막아 주었다.
- **조건:** target-bound. 보호받는 인물·동물과 실제 위협이 필요하다. Oxford는 사람이나 사물이 해를 입지 않도록 하는 것으로 정의하며, 공격이나 바람으로부터 대상을 가리는 예를 든다. [Oxford: protect](https://www.oxfordlearnersdictionaries.com/definition/english/protect)
- **시각적 이유:** 보호자는 대상과 위협 사이에 몸을 놓고 방패·팔·망토로 차단한다. “자기만 피함”과 달리 대상의 안전이 화면에 남는다.
- **계약:** `prepare` 보호 대상 뒤 또는 옆에 위협이 접근한다 -> `act` 보호자가 대상과 위협 사이로 이동해 팔·방패·망토를 펼친다 -> `hold` 위협을 향해 차단 자세를 유지하고 대상은 뒤에 머문다 -> `recover` 위협이 사라진 뒤 보호자와 대상이 함께 안정된다.
- **혼동/negative cue:** 자신만 옆으로 피하면 `dodge`, 대상에게 달려가 데리고 나오면 `rescue`, 대상과 몸을 맞대기만 하면 기존 `hug`다. 위협 또는 보호 대상이 없으면 `protect`로 채택하지 않는다.
- **우선도:** **later asset**. 위협의 방향과 대상의 반응까지 포함한 장면 자산이 먼저다.

### 5. 붙잡아 멈추게 하다 `catch`

- **예문:** 왕자는 절벽에서 미끄러진 친구의 손을 재빨리 붙잡았다.
- **조건:** target-bound. 움직이는 사람이나 물체의 이동을 중간에 멈추고 손에 잡아야 한다. Oxford는 움직이는 물체나 사람을 멈춰 손에 잡는 뜻을 첫 의미로 제시한다. [Oxford: catch](https://www.oxfordlearnersdictionaries.com/definition/english/catch_1)
- **시각적 이유:** 접근하는 손, 움직이는 표적, 접촉 직후의 정지가 인과적으로 보인다.
- **계약:** `prepare` 표적이 캐릭터 쪽으로 떨어지거나 미끄러진다 -> `act` 캐릭터가 몸을 뻗어 손목·팔 또는 물체를 잡는다 -> `hold` 표적의 이동이 멈추고 잡힌 상태를 유지한다 -> `recover` 표적을 안전한 위치로 당기거나 안정된 자세로 돌아온다.
- **혼동/negative cue:** 가만히 있는 물체를 잡으면 `grasp`, 바닥에서 들어 올리면 `pick_up`, 표적을 밖으로 데리고 나오면 `rescue`다. 움직이는 표적이 없거나 손이 접촉하지 않으면 실패.
- **우선도:** **later asset**. 파트너 추락 버전과 날아오는 열쇠 버전을 별도 계약으로 분리한다.

### 6. 놓아주다 `release`

- **예문:** 왕자는 밧줄을 풀고 작은 용을 숲으로 놓아주었다.
- **조건:** target-bound. 묶이거나 붙잡힌 대상의 움직임을 허용해야 한다. Oxford는 갇힌 사람을 밖으로 나오게 하는 뜻과, 잡고 있던 것을 놓아 자유롭게 움직이게 하는 뜻을 구분한다. [Oxford: release](https://www.oxfordlearnersdictionaries.com/definition/english/release_1)
- **시각적 이유:** 손·밧줄·문고리의 접촉이 끊기고 대상이 즉시 멀어지는 상태 변화가 선명하다.
- **계약:** `prepare` 대상이 줄·손·우리 안에 제한된 상태다 -> `act` 캐릭터가 묶음을 풀거나 손을 뗀다 -> `hold` 대상과 캐릭터 사이의 제한이 사라진다 -> `recover` 대상은 자유롭게 이동하고 캐릭터는 손을 내린다.
- **혼동/negative cue:** 손에서 물체가 떨어지는 것만 보이면 `drop`, 문을 여는 것만 보이면 `open`, 위험에서 대상을 꺼내는 과정이면 `rescue`다. 제한 상태와 자유 이동이 모두 없으면 판정하지 않는다.
- **우선도:** **later asset**. 새장·밧줄·손목 중 한 가지 제한 장치를 고정해 제작한다.

### 7. 항복하다 `surrender`

- **예문:** 기사는 검을 바닥에 내려놓고 용 앞에 두 손을 들었다.
- **조건:** target-bound. 위협하는 상대와 내려놓을 무기 또는 위험 맥락이 필요하다. Oxford의 `surrender` 동사 항목은 상대에게 통제권을 넘기거나 저항을 멈추는 뜻을 포함한다. [Oxford: surrender](https://www.oxfordlearnersdictionaries.com/definition/english/surrender_1)
- **시각적 이유:** 무기를 낮추고 두 손을 높여 공격 의사를 중단하는 전환이 한 화면에 남는다.
- **계약:** `prepare` 상대를 마주한 방어 자세와 손의 무기 -> `act` 무기를 천천히 내려놓고 두 손을 올린다 -> `hold` 손바닥을 보인 채 움직임을 멈춘다 -> `recover` 상대가 위협을 거두면 손을 낮추되 중립을 유지한다.
- **혼동/negative cue:** 두 팔을 위로 펴기만 하면 `stretch`, 손에서 빛이 나오면 `magic`, 이마에 한 손을 대면 `salute`다. 상대·위협·저항 중 하나라도 없으면 `surrender`로 채택하지 않는다.
- **우선도:** **later asset**. 전투를 만들지 않더라도 “검을 내려놓음 + 상대 앞의 손바닥”이라는 비폭력 장면으로 검증한다.

### 8. 손을 잡고 함께 가다 `hold_hands` (narrow visual sense)

- **예문:** 겁먹은 아기 용은 친구의 손을 꼭 잡고 어두운 동굴을 건넜다.
- **조건:** partner-bound. 두 인물의 손이 지속적으로 맞닿아 있어야 한다. 일반 `hold`의 물리적 접촉과 어린이 우정·도움 맥락을 결합한 좁은 감각이며, PBS KIDS는 친구가 울 때 포옹하고 도와주는 행동을 우정의 예로 제시한다. [Oxford: hold](https://www.oxfordlearnersdictionaries.com/definition/english/hold_1), [PBS KIDS: friendship](https://www.pbs.org/parents/friendship)
- **시각적 이유:** 두 인물의 손 접점이 유지되고 한 인물이 다른 인물의 보폭·방향에 맞춘다.
- **계약:** `prepare` 두 인물이 나란히 서서 손을 내민다 -> `act` 손이 맞닿고 손가락 또는 손바닥 접촉을 고정한다 -> `hold` 손을 놓지 않은 채 짧게 함께 이동하거나 불안한 표정을 안정시킨다 -> `recover` 목적지에서 손을 천천히 놓는다.
- **혼동/negative cue:** 한 번 잡았다가 상하로 흔들면 `shake_hands`, 한 인물이 다른 인물을 뒤따르면 `follow`, 손 접촉 없이 팔만 벌리면 `hug`로 재분류한다. 두 손 접점이 프레임에서 사라지면 실패.
- **우선도:** **later asset**. 기존 `grasp`와 이동 `journey`를 동시에 배제하는 2인 중경 계약이 필요하다.

### 9. 귀에 속삭이다 `whisper_to_ear` (narrow visual sense)

- **예문:** 여우는 친구의 귀에 비밀 보물 지도를 찾았다고 속삭였다.
- **조건:** partner-bound. 듣는 상대의 귀와 가까운 입, 비밀을 공유하는 관계가 화면에 있어야 한다. Oxford는 매우 조용히 말하는 것과 상대의 귀에 속삭이는 용례를 제시한다. [Oxford: whisper](https://www.oxfordlearnersdictionaries.com/definition/english/whisper_1)
- **시각적 이유:** 얼굴 간 거리를 좁히고 한 손으로 입을 가린 뒤 상대 귀 쪽으로 고개를 기울이는 관계 포즈가 필요하다.
- **계약:** `prepare` 두 인물이 가까이 서고 화자가 상대를 확인한다 -> `act` 화자가 입을 손으로 가리고 상대 귀 쪽으로 기울인다 -> `hold` 입-귀 거리와 조용한 발화를 유지한다 -> `recover` 화자가 물러나고 상대가 비밀을 들은 표정을 보인다.
- **혼동/negative cue:** 상대 없이 입만 움직이면 `talk`, 멀리 외치면 `shout`, 손을 귀에 대는 쪽이 화자면 `listen`이다. 오디오·중경·상대 반응이 없으면 모션 자산으로 승인하지 않는다.
- **우선도:** **text-only/scene-only**. 기존 Round 3의 대화·속삭임 범위를 침범하지 않으면서 “귀에 가까이 말함”을 학습할 때만 보존.

### 10. 다투다 `argue`

- **예문:** 두 형제는 마법 지도를 누가 먼저 찾았는지 잠시 다투었다.
- **조건:** partner-bound. 마주 보는 두 인물과 갈등 전후 맥락이 필요하다. Oxford의 `argue` 정의는 이유를 들어 다른 사람과 의견을 다투는 말하기를 포함한다. [Oxford: argue](https://www.oxfordlearnersdictionaries.com/definition/english/argue)
- **시각적 이유:** 번갈아 상대를 향해 몸을 기울이고 손바닥·팔을 크게 교대하며, 서로의 거리가 벌어지는 관계 변화가 보인다.
- **계약:** `prepare` 두 인물이 같은 단서 앞에서 마주 선다 -> `act` 한 사람이 항의하고 다른 사람이 반박하는 교대 제스처를 보인다 -> `hold` 서로 팔을 내리고 등을 약간 돌린 긴장 상태를 유지한다 -> `recover` 장면 종료 또는 중재자 접근을 위한 중립으로 돌아간다.
- **혼동/negative cue:** 한 인물의 말하기만 보이면 `talk`, 손가락만 내밀면 `point`, 몸을 맞대고 싸우면 전투다. 음성·상대 반응·갈등 전후가 없으면 동작명으로 확정하지 않는다.
- **우선도:** **text-only/scene-only**. 이야기 전환에는 유용하지만 silent solo asset으로는 기존 제스처와 구별이 약하다.

### 11. 화해하다 `reconcile` (narrow scene sense)

- **예문:** 다투던 두 친구는 서로 고개를 끄덕이고 손을 맞잡으며 화해했다.
- **조건:** partner-bound. 이전 갈등과 이후 관계 회복이 같은 장면의 전후로 있어야 한다. Oxford는 다툼 뒤 사람들이 다시 친구가 되게 하는 뜻으로 `reconcile`을 설명한다. [Oxford: reconcile](https://www.oxfordlearnersdictionaries.com/definition/english/reconcile)
- **시각적 이유:** 서로 등을 돌린 상태에서 천천히 돌아서고, 손잡기·악수·포옹 중 하나로 접촉을 회복하는 전환은 이야기 단위로는 읽힌다.
- **계약:** `prepare` 두 인물이 떨어져 팔짱 또는 등을 돌린다 -> `act` 서로 돌아보고 방어 팔을 낮춘다 -> `hold` 악수 또는 손잡기 후 안정된 시선을 유지한다 -> `recover` 나란히 서거나 함께 다음 경로로 이동한다.
- **혼동/negative cue:** 갈등 전 상태가 없으면 `shake_hands` 또는 `hold_hands`, 접촉만 있으면 `hug`다. 이전 분리와 이후 회복을 한 시퀀스에 담지 못하면 `reconcile`로 승인하지 않는다.
- **우선도:** **text-only/scene-only**. 독립 새 모션보다 `argue -> reconcile` 서사 합성의 라벨로 관리한다.

### 12. 사과하다 `apologize` (narrow scene sense)

- **예문:** 마법사는 깨뜨린 별빛 병 앞에서 친구에게 고개를 숙여 사과했다.
- **조건:** partner-bound. 잘못의 대상인 상대와 원인 소품·사건이 있어야 한다. Oxford는 잘못했거나 문제를 일으킨 것에 미안하다고 말하는 것으로 정의한다. [Oxford: apologize](https://www.oxfordlearnersdictionaries.com/definition/english/apologize)
- **시각적 이유:** 상대를 향해 짧게 고개를 숙이고 손을 펴 보이며, 상대의 긴장이 풀리는 반응을 붙일 수 있다.
- **계약:** `prepare` 두 인물 사이에 깨진 소품 또는 갈등 원인이 보인다 -> `act` 사과하는 인물이 상대를 향해 몸을 낮추고 손을 연다 -> `hold` 고개를 숙인 채 상대 반응을 기다린다 -> `recover` 고개를 들고 상대와 거리를 안정시킨다.
- **혼동/negative cue:** 상대·원인 사건 없이 고개만 숙이면 기존 `bow`, 손을 모으면 `pray`, 바닥의 소품만 보면 `investigate`다. 말풍선·상대 반응 또는 명확한 사과 사건이 없으면 모션 자산으로 만들지 않는다.
- **우선도:** **text-only/scene-only**. 관찰 가능한 동작은 기존 `bow`의 좁은 변형에 가깝고, 핵심 의미는 관계 맥락이다.

## 우선 제작 순서와 보류 경계

1. 2인 합성으로 `meet`을 먼저 검증한다. 두 root가 실제로 모이고 마주 보는지, `follow/chase/journey`와 나란히 비교한다.
2. 같은 인물 배치에서 `shake_hands`를 검증한다. 손-손 접촉과 상하 흔들림이 없으면 `offer/receive`로 낮춘다.
3. `beckon`은 기존 `wave`와 side-by-side 테스트한다. 손바닥 안쪽 당김과 화면 속 수신 대상이 필수다.
4. `protect`, `catch`, `release`, `surrender`는 각각 대상·위협·제한 상태의 변화를 포함한 scene composite로 만든다. 캐릭터 단독 투명 sheet로 축약하지 않는다.
5. `hold_hands`와 `whisper_to_ear`는 2인 중경 전용으로만 후속 검토한다. `reconcile`, `argue`, `apologize`는 현재 새 모션보다 장면 라벨·텍스트 이벤트로 보존한다.

## 방법의 한계

- 웹 사전은 단어의 의미와 일반 용례를 뒷받침하지만, 실제 한국 어린이 동화 빈도나 특정 캐릭터 스타일의 판독성을 보장하지 않는다.
- `meet`, `protect`, `reconcile`처럼 사건·관계 자체가 의미인 단어는 단일 캐릭터 PNG로 완결되지 않는다. 이 보고서의 `next asset/later asset`은 2인·장면 합성 제작을 포함한다.
- `whisper_to_ear`, `reconcile`, `apologize`는 화면만으로 확정하면 과대분류 위험이 크다. 음성, 이전 사건, 상대 반응이 없으면 text-only/scene-only로 남긴다.
- 기존 에셋은 파일 목록·manifest·보고서의 의미 계약을 기준으로 대조했으며, 이번 조사에서 PNG나 runtime/backend/database 파일은 변경하지 않았다.

## 참고 자료

- [Oxford Learner's Dictionaries: meet](https://www.oxfordlearnersdictionaries.com/definition/english/meet_1)
- [Oxford Learner's Dictionaries: protect](https://www.oxfordlearnersdictionaries.com/definition/english/protect)
- [Oxford Learner's Dictionaries: catch](https://www.oxfordlearnersdictionaries.com/definition/english/catch_1)
- [Oxford Learner's Dictionaries: release](https://www.oxfordlearnersdictionaries.com/definition/english/release_1)
- [Oxford Learner's Dictionaries: surrender](https://www.oxfordlearnersdictionaries.com/definition/english/surrender_1)
- [Oxford Learner's Dictionaries: whisper](https://www.oxfordlearnersdictionaries.com/definition/english/whisper_1)
- [Oxford Learner's Dictionaries: reconcile](https://www.oxfordlearnersdictionaries.com/definition/english/reconcile)
- [Oxford Learner's Dictionaries: apologize](https://www.oxfordlearnersdictionaries.com/definition/english/apologize)
- [Oxford Learner's Dictionaries: hold](https://www.oxfordlearnersdictionaries.com/definition/english/hold_1)
- [Cambridge Dictionary: shake hands](https://dictionary.cambridge.org/us/dictionary/english/shake-hands)
- [Cambridge Dictionary: beckon](https://dictionary.cambridge.org/us/dictionary/english/beckon)
- [PBS KIDS for Parents: Being a Good Friend and Neighbor](https://www.pbs.org/parents/friendship)
- [British Council LearnEnglish Kids: Reach out](https://learnenglishkids.britishcouncil.org/listen-watch/video-zone/reach-out)
- [British Council LearnEnglish Kids: Traditional stories worksheet](https://learnenglishkids.britishcouncil.org/sites/kids/files/attachment/yourturn-traditional%20stories-worksheet.pdf)
