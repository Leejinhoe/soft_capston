# 어휘 연구 라운드 4: 감각·관찰·반응

- 담당: 감각·관찰·반응
- 작성일: 2026-08-10 (KST)
- 범위: 한국어 어린이 동화에서 장면을 읽게 하는 듣기·살피기·놀람·망설임·두려움·발견 반응
- 원칙: 이번 문서는 어휘 조사 보고서이며 이미지·영상 생성이나 런타임/백엔드/DB 변경을 하지 않는다.

## 방법

1. 다음 기존 산출물을 먼저 대조했다: `treasure_story_words.md`, `round3_words_language.md`, `round3_words_assets.md`, `round3_words_motion.md`, `generated_round3`, `generated_v2`, `merged_visual_vocabulary.json`.
2. `merged_visual_vocabulary.json`의 기존 12개 word entry와, 구현·제외 자료에서 확인되는 canonical action(`journey`, `jump`, `investigate`, `magic`, `wave`, `sit`, `stand`, `stop`, `kneel`, `bow`, `crouch`, `stretch`, `clap`, `point`, `nod`, `dance`, `crawl`, `climb`, `slide`, `hide`, `fall_roll` 계열), 그리고 라운드 3에서 이미 직접 조사한 `listen`, `peek`, `sniff`, `flinch`, `freeze`, `yawn`, `sneeze`, `cough`, `faint`, `shiver`, `wake`, `salute`, `prone`, `stagger` 등을 새 기본 제안에서 제외했다.
3. 사전의 동작 의미가 실제 동화 장면에서 관찰 가능한지 확인했다. Oxford Learner's Dictionaries, Cambridge Dictionary, Merriam-Webster를 우선 사용했고, 어린이 모험·전통 이야기의 문맥은 [British Council의 adventure-story writing practice](https://learnenglishkids.britishcouncil.org/sites/kids/files/attachment/LearnEnglishKids-Writing-practice-Level-3-An-adventure-story.pdf)와 [Echo and Hera](https://learnenglishkids.britishcouncil.org/read-write/reading-practice/level-2-reading/echo-hera)를 참고했다.
4. `prepare -> act -> hold -> recover` 네 구간, 음성 없이도 확인 가능한 핵심 실루엣, 기존 동작과의 부정 cue를 기준으로 우선순위를 정했다.

## 랭킹 요약: 상위 7

| 순위 | 한국어 | canonical key | 분류 | 우선도 | 채택 조건 |
|---:|---|---|---|---|---|
| 1 | 웅크리며 겁내다 | `cower` | target-bound | **next asset** | 화면에 위협/겁의 원인이 있고, `crouch`가 아닌 뒤로 물러나는 공포 자세여야 함 |
| 2 | 망설이다 | `hesitate` | target-bound / prop-bound | **next asset** | 문·다리·선택지 등 미완료 목표와 손의 접근-철회가 보여야 함 |
| 3 | 몰래 엿듣다 | `eavesdrop` | partner-bound / environment-bound | **next asset** | 문·벽·창 같은 가림막, 들리는 상대, 숨은 청취 위치를 한 장면에 포함 |
| 4 | 발견하다/눈에 띄는 것을 알아채다 | `spot` | target-bound | **later asset** | 탐색 과정 없이 숨은 표적을 갑자기 발견하는 1회성 전환으로 제한 |
| 5 | 놀라 숨을 들이켜다 | `gasp` | target-bound | **later asset** | 놀라운 표적과 중경 얼굴·상체가 함께 있고, 음성은 보조로만 사용 |
| 6 | 눈을 가늘게 뜨고 보다 | `squint` | target-bound / environment-bound | **later asset** | 먼 표적·강한 빛·작은 글씨 중 하나가 프레임에 고정되고 중경 이상을 사용 |
| 7 | 아파서 얼굴을 찡그리다 | `wince` | target-bound | **later asset** | 가시·상처·차가운 마법 등 통증 원인이 보이며 얼굴 반응을 중경으로 판정 |

`overhear`, `shush`, `blink`는 의미는 자연스럽지만 각각 소리·상대·얼굴의 미세 변화에 과도하게 의존하므로 이번 제작 슬롯에는 넣지 않고 후순위로 둔다.

## 후보 상세

### 1. 웅크리며 겁내다 — `cower`

- **뜻 / 근거:** 무서워서 몸을 낮추거나 뒤로 물러나다. Oxford는 “bend low and/or move backwards because you are frightened”로 정의하고, Merriam-Webster Kids도 공포 때문에 움츠러들거나 웅크리는 뜻으로 풀이한다 ([Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/cower), [Merriam-Webster Kids](https://www.merriam-webster.com/dictionary/cower)).
- **동화 예문:** `The little fox cowered behind the stone when the dragon roared.`
- **장면 분류:** `target-bound` — 용의 포효, 괴물, 번개처럼 화면에 보이는 위협이 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 무릎을 굽히는 것만이 아니라 몸통을 위협에서 멀리 빼고 팔을 보호 자세로 올리는 방향성이 있어 `crouch`와 구별할 수 있다. 위협 표적의 시선축까지 고정하면 한 시트와 한 위협 합성으로 판독 가능하다.
- **시각 계약:** `prepare`: 위협 쪽을 보며 서 있고 어깨가 올라가기 시작한다 -> `act`: 몸을 낮추며 한두 걸음 뒤로 물러나 팔을 가슴·머리 앞에 둔다 -> `hold`: 시선은 위협 쪽에 둔 채 낮은 몸통과 보호 팔을 유지한다 -> `recover`: 위협이 지나간 뒤 고개를 들고 천천히 중립으로 돌아온다.
- **혼동 / 부정 cue:** `crouch`와 달리 목적 없는 낮은 자세가 아니며 반드시 공포 표적과 후퇴가 있어야 한다. `flinch`처럼 한순간 어깨만 튀면 실패, `hide`처럼 가림막 뒤로 몸 전체가 사라져도 실패, `freeze`처럼 발과 몸이 완전히 고정되어도 실패다.
- **우선도:** **next asset**. 위협 표적과 3/4 또는 측면 구도를 필수 메타데이터로 묶을 때만 채택한다.

### 2. 망설이다 — `hesitate`

- **뜻 / 근거:** 확신이 없거나 긴장해서 말하거나 행동하기 전에 느리게 머뭇거리다. Oxford는 불확실하거나 긴장해서 행동이 늦어지는 뜻과 어떤 일을 할지 망설이는 용법을 함께 제시한다 ([Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/hesitate)).
- **동화 예문:** `Mina hesitated before opening the dark castle door.`
- **장면 분류:** `target-bound / prop-bound` — 문, 다리, 마법 지팡이처럼 아직 실행하지 않은 목표가 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 접근 중 손을 뻗었다가 멈추고, 시선과 몸이 목표와 캐릭터 사이에서 잠시 흔들린 뒤 손을 거두는 미완료 행동이 핵심이다. `stop`의 완료된 정지보다 원인과 철회가 선명하다.
- **시각 계약:** `prepare`: 목표물 앞에서 한 발을 내딛고 손을 뻗을 준비를 한다 -> `act`: 손이 손잡이·발판·지팡이 근처까지 갔다가 멈춘다 -> `hold`: 목표를 바라본 채 손과 발을 중간 지점에 둔다 -> `recover`: 손을 거두고 뒤로 반걸음 물러나거나 다른 선택지 쪽으로 몸을 돌린다.
- **혼동 / 부정 cue:** 완전히 멈춘 채 목표·미완료 접근이 없으면 `stop` 또는 `stand`로 실패, 몸을 낮추거나 뒤로 숨으면 `cower`/`hide`로 실패, 손이 실제로 목표 상태를 바꾸면 `open`/`unlock` 계열로 분기한다. 망설임은 선택지나 실행 직전의 중간 상태여야 한다.
- **우선도:** **next asset**. 문·길 갈림·두 선택지 중 하나를 고르는 장면 템플릿과 함께 제작한다.

### 3. 몰래 엿듣다 — `eavesdrop`

- **뜻 / 근거:** 다른 사람이 사적으로 하는 말을 몰래 듣다. Oxford는 “listen secretly to what other people are saying”, Merriam-Webster Kids는 사적인 대화를 몰래 듣는 뜻으로 정의한다 ([Oxford](https://www.oxfordlearnersdictionaries.com/definition/english/eavesdrop), [Merriam-Webster](https://www.merriam-webster.com/dictionary/eavesdrop)).
- **동화 예문:** `The princess eavesdropped outside the wizard's door.`
- **장면 분류:** `partner-bound / environment-bound` — 말하는 상대와 문·벽·창 같은 가림막이 모두 의미를 완성한다.
- **한 개의 명확한 에셋으로 보이는 이유:** 라운드 3에서 보류한 넓은 `listen`의 좁은 시각적 의미다. 가림막 뒤에 몸을 숨기고 귀·얼굴만 소리 쪽으로 내미는 위치 관계가 있으면 `listen`이나 `investigate`와 분리된다.
- **시각 계약:** `prepare`: 문 또는 벽 바깥에서 주변을 살피고 몸을 가림막 쪽에 붙인다 -> `act`: 귀와 얼굴을 가림막 가까이 가져가며 한쪽 눈만 살짝 내민다 -> `hold`: 몸 대부분은 숨긴 채 귀·시선만 상대 쪽에 고정한다 -> `recover`: 갑자기 고개를 거두고 가림막에서 물러나 중립으로 돌아온다.
- **혼동 / 부정 cue:** 가림막과 사적인 대화가 없고 캐릭터가 공개된 곳에서 귀에 손만 대면 `listen` 또는 `investigate`로 실패, 얼굴과 몸을 전부 드러내면 `watch`/`peek`로 실패, 상대의 입·대사 cue가 없으면 의미를 승인하지 않는다.
- **우선도:** **next asset 조건부**. 캐릭터 시트만 만들면 안 되고, 문/벽 레이어와 상대의 말소리 cue를 포함한 장면 세트로만 채택한다.

### 4. 우연히 엿듣다 — `overhear`

- **뜻 / 근거:** 자신이 참여하지 않은 대화를 우연히 듣다. Oxford는 “hear, especially by accident, a conversation in which you are not involved”로 설명하며 `eavesdrop`과 비교한다 ([Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/overhear)).
- **동화 예문:** `Leo overheard two goblins talking about a hidden key.`
- **장면 분류:** `partner-bound / environment-bound` — 대화하는 상대와 우연히 들을 수 있는 거리·공간이 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 대화에 몰래 접근하는 `eavesdrop`과 달리, 주인공이 하던 일을 멈추고 우연히 소리 쪽으로 고개를 돌리는 ‘발견 순간’으로 연출할 수 있다. 다만 이 차이는 장면 편집이 없으면 약하다.
- **시각 계약:** `prepare`: 캐릭터가 길을 걷거나 물건을 살피는 중이다 -> `act`: 뒤쪽 대화 소리에 고개와 어깨만 돌리고 걸음을 멈춘다 -> `hold`: 상대에게 접근하지 않고 먼 거리에서 듣는 시선을 유지한다 -> `recover`: 소리가 끝나면 원래 길 또는 행동으로 돌아간다.
- **혼동 / 부정 cue:** 가림막에 몸을 붙이거나 일부러 숨으면 `eavesdrop`, 손을 귀에 대고 소리 방향을 탐색하면 `listen`, 소리·말하는 상대가 없으면 `investigate`로 실패한다. 음성 없이 별도 canonical action으로 승인하지 않는다.
- **우선도:** **text-only/scene-only**. 오디오와 편집된 장면 사건의 의미가 핵심이라 독립 모션 시트로는 권하지 않는다.

### 5. 놀라 숨을 들이켜다 — `gasp`

- **뜻 / 근거:** 충격이나 놀람 때문에 갑자기 숨을 들이쉬며 소리를 내다. Cambridge Learner's Dictionary는 놀라거나 충격을 받아 갑자기 숨을 들이쉬는 것으로 정의한다 ([Cambridge Learner's Dictionary](https://dictionary.cambridge.org/us/dictionary/learner-english/gasp)).
- **동화 예문:** `Nuri gasped when the tiny star appeared in the box.`
- **장면 분류:** `target-bound` — 상자 안의 별, 갑자기 나타난 요정처럼 놀람의 표적이 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 입이 열리고 눈·어깨가 함께 올라가며 한 번의 짧은 흡기 반응이 생긴다. 중경에서 표적 reveal 직후 붙이면 `surprise`를 감정 라벨로만 두지 않고 관찰 가능한 반응으로 만들 수 있다.
- **시각 계약:** `prepare`: 표적을 향해 정상적으로 바라본다 -> `act`: 표적이 드러나는 순간 입을 열고 턱·어깨를 짧게 들어 올린다 -> `hold`: 열린 입과 넓어진 눈, 표적 고정 시선을 짧게 유지한다 -> `recover`: 입을 닫고 숨을 내쉬며 손과 어깨를 자연스럽게 내린다.
- **혼동 / 부정 cue:** 소리 없이 입·얼굴이 보이지 않는 원경이면 `gasp`로 승인하지 않는다. 몸을 크게 뒤로 빼면 `flinch`, 몸을 낮추고 물러나면 `cower`, 입을 크게 벌린 채 오래 유지하면 `yawn`으로 실패한다.
- **우선도:** **later asset**. 320x180 이상 중경, 표적 reveal 컷, 선택적 gasp 오디오가 함께 있어야 한다.

### 6. 아파서 얼굴을 찡그리다 — `wince`

- **뜻 / 근거:** 통증이나 불쾌함을 느껴 얼굴에 짧고 갑작스러운 반응을 보이며 머리를 뒤로 움직이다. Cambridge는 얼굴을 통해 통증·당황을 짧게 드러내는 동작으로 정의한다 ([Cambridge](https://dictionary.cambridge.org/us/dictionary/english/wince)).
- **동화 예문:** `The prince winced when the thorn touched his finger.`
- **장면 분류:** `target-bound` — 가시, 상처, 차가운 돌, 뜨거운 주문 등 통증의 원인이 프레임에 있어야 한다.
- **한 개의 명확한 에셋으로 보이는 이유:** 접촉 직후 눈을 찡그리고 머리·목을 짧게 뒤로 빼는 반응은 통증 원인과 붙이면 읽힌다. 단 얼굴 해상도가 낮으면 `flinch`와 분리되지 않는다.
- **시각 계약:** `prepare`: 손가락이나 아픈 부위를 목표물 가까이 둔다 -> `act`: 접촉 순간 눈을 감고 입·눈썹을 찡그리며 머리를 짧게 뺀다 -> `hold`: 아픈 부위를 다른 손으로 감싸고 표적을 보며 짧게 멈춘다 -> `recover`: 숨을 고르고 손을 천천히 떼며 조심스럽게 중립으로 돌아온다.
- **혼동 / 부정 cue:** 통증 표적 없이 어깨만 튀면 `flinch`, 공포 때문에 몸 전체가 움츠러들면 `cower`, 얼굴이 보이지 않으면 `wince`로 승인하지 않는다. 낙상·충돌의 큰 몸동작도 이 key에 쓰지 않는다.
- **우선도:** **later asset**. 얼굴·손·접촉점이 함께 보이는 중경 또는 근접 장면 전용이다.

### 7. 눈을 가늘게 뜨고 보다 — `squint`

- **뜻 / 근거:** 더 잘 보기 위해 눈을 부분적으로 감거나 강한 빛을 피하며 보다. Cambridge와 Oxford 모두 밝은 빛 또는 먼 대상을 더 잘 보기 위해 눈을 가늘게 뜨는 뜻을 제시한다 ([Cambridge](https://dictionary.cambridge.org/us/dictionary/english/squint), [Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/squint_1)).
- **동화 예문:** `The girl squinted at the tiny mark on the old map.`
- **장면 분류:** `target-bound / environment-bound` — 작은 지도 표식, 먼 성, 눈부신 달빛 중 하나가 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 대상에 시선을 고정한 채 눈을 좁히고 얼굴을 약간 앞으로 내미는 동작이 반복되면 ‘탐색’이 아니라 ‘판독을 위한 시각 조절’로 정의할 수 있다.
- **시각 계약:** `prepare`: 먼 표적 또는 작은 표식을 정면으로 본다 -> `act`: 눈을 부분적으로 감고 얼굴을 표적 쪽으로 약간 민다 -> `hold`: 좁힌 눈과 고정된 시선을 유지한다 -> `recover`: 표적이 선명해지거나 빛이 약해지면 눈을 정상적으로 열고 고개를 든다.
- **혼동 / 부정 cue:** 눈을 감았다 뜨기만 하면 `blink`, 고개를 좌우로 크게 돌리면 `investigate`, 한쪽 눈만 닫아 신호를 보내면 `wink`로 실패한다. 원경에서는 얼굴 변화가 판독되지 않으므로 승인하지 않는다.
- **우선도:** **later asset**. 작은 표적과 얼굴이 동시에 보이는 중경 합성 없이는 text-only에 가깝다.

### 8. 숨은 것을 발견하다 — `spot`

- **뜻 / 근거:** 찾기 어려운 사람이나 물건을 특히 갑자기 보거나 알아채다. Oxford는 갑작스럽거나 쉽지 않은 대상을 보는 뜻을, Cambridge는 열심히 바라보다가 알아차리는 뜻을 설명한다 ([Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/spot_2), [Cambridge](https://dictionary.cambridge.org/us/dictionary/english/spot)).
- **동화 예문:** `At last, Hana spotted the silver key under the leaf.`
- **장면 분류:** `target-bound` — 나뭇잎 아래 열쇠, 군중 속 친구, 어둠 속 빛처럼 숨겨진 표적이 필수다.
- **한 개의 명확한 에셋으로 보이는 이유:** `investigate`처럼 계속 둘러보는 과정이 아니라, 시선이 멈추고 표적을 향해 짧게 고개·손이 전환되는 ‘발견 순간’만 계약한다. 표적 reveal 컷과 연결하면 판독 가능성이 있다.
- **시각 계약:** `prepare`: 주변을 살피지만 표적은 아직 찾지 못한 상태다 -> `act`: 표적이 보이는 순간 고개와 눈이 빠르게 멈추고 몸이 표적 쪽으로 정렬된다 -> `hold`: 표적을 가리키거나 손을 가슴으로 가져오며 발견한 시선을 유지한다 -> `recover`: 표적 쪽으로 한 걸음 다가가거나 다음 `pick_up`/`open`으로 연결한다.
- **혼동 / 부정 cue:** 표적이 없거나 시선이 계속 넓게 움직이면 기존 `investigate`, 손가락만 멀리 뻗으면 `point`, 덮개를 걷는 실제 상태 변화가 있으면 `uncover`로 처리한다. 표적의 위치·등장 시점이 메타데이터에 없으면 새 key를 승인하지 않는다.
- **우선도:** **later asset**. 기존 `investigate`의 좁은 발견 전환으로만 조건부 채택하며, 단독 투명 캐릭터 시트는 만들지 않는다.

### 9. 눈을 빠르게 깜빡이다 — `blink`

- **뜻 / 근거:** 눈을 빠르게 감았다가 다시 여는 동작. Cambridge는 한 번 또는 여러 번 빠르게 눈을 닫고 여는 것으로 정의하며, Oxford는 밝은 햇빛이나 놀람에 대한 예문을 제시한다 ([Cambridge](https://dictionary.cambridge.org/us/dictionary/english/blink), [Oxford](https://www.oxfordlearnersdictionaries.com/us/definition/english/blink_1)).
- **동화 예문:** `Joon blinked in the bright fairy light.`
- **장면 분류:** `environment-bound / target-bound` — 갑작스러운 섬광, 먼지, 밝은 마법 빛 같은 원인이 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 원인은 분명하지만 눈만의 변화가 작다. 근접 얼굴과 섬광 전후 컷이 있으면 보일 수 있으나 일반 전신 시트에서는 판독 불가다.
- **시각 계약:** `prepare`: 정상 시선으로 빛 또는 표적을 본다 -> `act`: 양쪽 눈을 짧게 감고 눈썹·머리를 약간 움찔한다 -> `hold`: 눈을 다시 뜨며 빛의 원인을 확인한다 -> `recover`: 정상적인 눈 뜬 자세와 시선으로 돌아온다.
- **혼동 / 부정 cue:** 원인 없이 반복 깜빡이면 자연스러운 생리적 움직임으로 처리하고 key를 부여하지 않는다. 한쪽 눈만 닫으면 `wink`, 눈을 오래 좁히면 `squint`, 몸 전체 반동이면 `flinch`다.
- **우선도:** **text-only/scene-only**. 자동 영상 판독용 기본 모션으로는 보류한다.

### 10. 조용히 하라고 신호하다 — `shush`

- **뜻 / 근거:** 다른 사람에게 조용히 하라고 재촉하다. Merriam-Webster는 “urge to be quiet”로 정의하고, 예문에서 입술에 손가락을 대는 제스처를 함께 보여 준다 ([Merriam-Webster](https://www.merriam-webster.com/dictionary/shush), [sentence examples](https://www.merriam-webster.com/sentences/shush)).
- **동화 예문:** `The fairy shushed the children when footsteps came near.`
- **장면 분류:** `partner-bound` — 조용해져야 하는 동료·아이·군중과, 가까이 다가오는 소리나 위험이 필요하다.
- **한 개의 명확한 에셋으로 보이는 이유:** 검지를 입술에 대고 상대를 향해 몸을 낮추는 포즈는 시각적으로 강하다. 다만 말을 멈추게 하는 상대가 없으면 단순히 입가를 만지는 동작으로 떨어진다.
- **시각 계약:** `prepare`: 상대와 주변 위험을 번갈아 본다 -> `act`: 검지를 입술에 세우고 상대 쪽으로 작은 몸짓을 보낸다 -> `hold`: 입술 앞 손가락과 상대 고정 시선을 유지한다 -> `recover`: 손을 내리고 조용히 숨거나 이동하는 다음 장면으로 전환한다.
- **혼동 / 부정 cue:** 입술 앞 손가락과 상대가 없으면 `shush`로 승인하지 않는다. 손이 귀로 가면 `listen`, 손을 흔들면 `wave`, 입을 가리고 몸이 떨리면 `gasp`나 `cower`와 구분한다. 실제 상대의 반응 또는 정적 장면 cue가 필요하다.
- **우선도:** **text-only/scene-only**. 독립 solo 에셋보다 상대·소리·자막을 포함한 관계 장면에서만 유효하다.

## 상위 추천의 공통 제작 계약

- `cower`: 위협 표적, 후퇴 방향, 낮은 몸통, 보호 팔을 필수 annotation으로 둔다. 기존 `crouch`와 side-by-side 검수한다.
- `hesitate`: 실행 전 손 접점, 미완료 상태, 선택지 또는 목표 표식을 필수로 둔다. 대상 상태가 바뀌면 즉시 다른 action으로 분기한다.
- `eavesdrop`: 가림막 레이어, 대화 상대, 숨은 청취 위치를 하나의 scene composite으로 묶는다. 오디오가 없을 때는 승인하지 않는다.
- `spot`: `investigate`의 반복 탐색과 분리하기 위해 “탐색 전 2~3셀 + 표적 발견 1회 + 다음 행동 연결”로만 설계한다.
- `gasp`, `wince`, `squint`: 얼굴·상체 중심의 중경을 별도로 둔다. 기존 전신 원경 시트에 억지로 매핑하지 않는다.

## 제외·보류 판단

- `listen`, `peek`, `sniff`, `flinch`, `freeze`, `yawn`, `sneeze`, `cough`, `faint`, `shiver` 등은 라운드 3 문서나 생성 에셋에서 이미 다뤄졌으므로 새 후보로 반복하지 않았다. `eavesdrop`은 `listen`의 일반형이 아니라 **가림막 뒤에서 사적인 대화를 몰래 듣는 좁은 시각적 의미**일 때만 예외적으로 제안한다.
- `spot`은 기존 `investigate`와 가장 가까우므로 표적·발견 시점·다음 행동이 없으면 새 canonical action으로 만들지 않는다.
- `blink`, `overhear`, `shush`는 소리 또는 얼굴 미세 변화가 행동의 핵심이다. 오디오·중경·상대 반응을 제공하지 못하는 배포 경로에서는 문장/장면 어휘로만 남긴다.
- `wince`는 통증의 표적 없이 `flinch`와 구별하기 어렵고, `gasp`는 입·눈이 안 보이면 `surprise`라는 감정 라벨로만 읽힌다.

## 한계

- 이번 라운드는 어린이 동화 코퍼스에서의 실제 빈도나 학습 난이도를 정량 집계하지 않았다. 예문은 장면 계약 검토를 위한 짧은 창작 예문이다.
- 사전 정의는 의미의 존재를 뒷받침하지만, 단일 PNG 모션 시트가 자동으로 그 의미를 판정한다는 뜻은 아니다. 특히 `eavesdrop`, `overhear`, `spot`은 공간·상대·표적 metadata가 없으면 기존 동작으로 환원해야 한다.
- 기존 자료의 한국어 설명과 생성 폴더를 확인했지만, 이번 작업에서는 새 이미지·영상과 코드 검증을 수행하지 않았다. 실제 채택 전에는 160x90 원경, 320x180 중경, 음성 제거 조건에서 부정 cue 검수를 다시 해야 한다.
