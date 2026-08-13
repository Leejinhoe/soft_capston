# Round 4 어휘 조사: 보물·소품·마법 물체

- 작성일: 2026-08-10 (KST)
- 역할: 보물·소품·마법 물체
- 범위: 한국어 아동 동화에서 보물상자, 열쇠, 지도, 보석, 문, 레버, 단서, 마법 유물과 자연스럽게 결합하는 추가 동작
- 산출물 제한: 이 보고서만 작성했으며 런타임·백엔드·데이터베이스·기존 에셋은 수정하지 않았다.

## 조사 방법

1. 다음 기존 산출물을 읽고 이미 구현되었거나 이미 후보로 다뤄진 항목을 제외했다.
   - `tools/next_actions/treasure_story_words.md`
   - `tools/next_actions/round3_words_language.md`
   - `tools/next_actions/round3_words_assets.md`
   - `tools/next_actions/round3_words_motion.md`
   - `assets/characters/motion_sheets/generated_round3`
   - `assets/characters/motion_sheets/generated_v2`
   - `tools/vocabulary_ensemble/merged_visual_vocabulary.json`
2. 병합 어휘의 canonical action과 생성 모션 시트 이름을 다시 대조했다. 현재 병합 어휘에는 `climb`, `crawl`, `hide`, `investigate`, `journey`, `jump`, `magic`, `sit`, `stand`, `stop`, `wave`가 있고, round3에는 `salute`, `prone`, `stagger`, `wake`, `yawn`, `sneeze` 시트가 있다.
3. `open_chest`, `unlock`, `pick_up`, `lift`, `uncover`, `dig`, `insert`, `turn_key`, `read`, `peek`, `lean`, `throw`, `push`, `pull`, `dive`, `swim`, `ride`, `dodge`, `give/receive`, `hug` 등 기존 보물·round3 후보는 기본 추천에서 제외했다. 다만 `pull_lever`, `turn_dial`, `place_gem`처럼 물체의 형태와 상태 변화를 고정한 좁은 시각 sense만 별도 후보로 남겼다.
4. 사전은 동사의 물체 결합 의미를 확인하는 데 사용하고, 아동 이야기 적합성은 British Council LearnEnglish Kids의 보물 지도·모험 이야기 자료와 현재 저장소의 동화 배경 목록을 교차 확인했다.

## 보수적 판정 기준

- 인물의 손 모양만 바뀌고 소품 상태가 바뀌지 않으면 후보를 `text-only/scene-only`로 낮췄다.
- `hold`는 단순히 손을 뻗은 자세가 아니라, 레버가 내려가고 문양이 켜지거나 보석이 홈에 안착하는 등 결과 상태를 유지하는 구간이어야 한다.
- `pick_up`과 `lift`는 이미 다뤄졌으므로, 새 `carry`는 물체를 든 채 화면 안에서 위치가 이동하고 `drop`은 손에서 분리되어 떨어지는 경우에만 성립한다.
- `magic`와 새 마법 물체 동작은 구별한다. 손에서 빛이 나오는 것만으로는 새 동작이 아니며, 반드시 봉인·램프·가마솥·보석 같은 물체의 접촉과 상태 변화가 있어야 한다.

## 후보 14개

### 1. 레버를 당겨 작동시키다 — `pull_lever`

- 예문: **The child pulled the old lever, and the secret door opened.**
- 분류: **prop-bound**. 레버와 레버가 연결된 문·다리·기계가 필수다.
- 한 장면 판독성: 손이 레버 손잡이를 실제로 잡고 아래 또는 몸 쪽으로 당긴 뒤, 레버 각도가 바뀌고 연결된 장치가 반응한다. 일반 `pull`의 몸통 기울기보다 접점과 결과가 훨씬 구체적이다.
- 시각 계약: `prepare` 레버와 손의 위치를 확인하고 팔꿈치를 굽힌다 -> `act` 손이 손잡이에 닿아 레버를 끝 위치까지 당긴다 -> `hold` 내려간 레버와 열린 문 또는 움직인 다리를 유지한다 -> `recover` 손을 놓고 결과를 바라본다.
- 혼동/음성 cue: `pull`·`push`·`unlock`과 혼동된다. **negative cue:** 레버가 없는 공중 당기기, 문손잡이를 당기는 동작, 대상 변화 없는 힘주기, 손이 레버를 통과하는 장면.
- 우선순위: **next asset**. 레버와 결과 장치를 한 화면에 두면 작은 소품 상호작용으로도 읽힌다.

### 2. 다이얼을 돌려 맞추다 — `turn_dial`

- 예문: **Mina turned the golden dial until the moon symbol faced up.**
- 분류: **prop-bound**. 둥근 다이얼과 맞춰야 할 눈금·문양이 필요하다.
- 한 장면 판독성: 두 손가락 또는 한 손이 다이얼의 가장자리를 잡고 원호를 따라 돌리며, 문양의 방향이 바뀌고 마지막에 특정 눈금에 멈춘다. 캐릭터 몸을 도는 `turn`과 분리된다.
- 시각 계약: `prepare` 다이얼의 시작 문양과 목표 문양을 확인한다 -> `act` 손가락이 가장자리를 잡고 일정한 원호로 회전시킨다 -> `hold` 목표 문양이 눈금과 정렬된 상태를 유지한다 -> `recover` 손을 떼고 잠금 장치 또는 문을 바라본다.
- 혼동/음성 cue: 일반 `turn`, `turn_key`, `magic`과 혼동된다. **negative cue:** 캐릭터만 회전, 열쇠와 자물쇠, 손에서 빛 발생, 다이얼이 프레임 사이에서 순간 이동.
- 우선순위: **next asset**. 시계탑·유적·마법문 배경과 잘 맞고 결과 상태가 객관적이다.

### 3. 보석을 홈에 놓다 — `place_gem`

- 예문: **The princess placed the blue gem in the crown-shaped stone.**
- 분류: **prop-bound**. 손에 든 보석과 정확한 홈·제단·왕관이 필요하다.
- 한 장면 판독성: 물체를 들고 있던 손이 홈 위에서 멈춘 뒤 보석이 손에서 분리되어 홈에 안착하고, 색·빛·문양 같은 결과가 나타난다. 기존 `pick_up`·`lift`와 반대 방향의 “손에서 지지면으로 이동”이다.
- 시각 계약: `prepare` 보석과 홈을 번갈아 확인하고 손을 홈 위에 맞춘다 -> `act` 보석을 수직으로 내려 홈에 끼운다 -> `hold` 손을 떼도 보석이 홈에 고정되고 유물이 빛난다 -> `recover` 손을 거두고 활성화된 유물을 바라본다.
- 혼동/음성 cue: `insert`, `put`, `unlock`, `magic`과 혼동된다. **negative cue:** 보석이 손에 붙어 떠 있음, 홈이 없는 빈손 손짓, 열쇠 삽입과 회전, 결과 상태가 없는 물체 소실.
- 우선순위: **next asset**. `insert`의 넓은 후보를 대체하는 좁은 시각 sense로만 추천한다.

### 4. 봉인을 눌러 찍다 — `press_seal`

- 예문: **The wizard pressed the star seal onto the red wax.**
- 분류: **prop-bound**. 도장 또는 마법 봉인, 왁스·점토·문 표면이 필요하다.
- 한 장면 판독성: 손에 든 도장이 표면을 향해 수직으로 내려가고, 눌린 뒤 별 문양이 표면에 남는다. 버튼을 누르는 `press`보다 접촉 면과 결과 흔적이 선명하다.
- 시각 계약: `prepare` 도장과 왁스 표면을 맞춰 든다 -> `act` 도장을 수직으로 눌러 표면에 밀착한다 -> `hold` 잠시 압력을 유지하며 문양이 찍힌 상태를 보여준다 -> `recover` 도장을 들어 올리고 남은 봉인을 바라본다.
- 혼동/음성 cue: `press`, `place`, `stamp`, `magic`과 혼동된다. **negative cue:** 버튼·왁스·도장 없이 손가락만 누르기, 표면에 문양이 남지 않음, 지팡이에서 빛이 나옴.
- 우선순위: **next asset**. 봉인된 마법문·편지·보물상자에 공통으로 사용할 수 있다.

### 5. 문을 두드리다 — `knock_on_door`

- 예문: **The little knight knocked on the castle door three times.**
- 분류: **prop-bound**. 문·벽·창문 같은 두드릴 표면이 필수다.
- 한 장면 판독성: 닫힌 문 앞에서 주먹이 문 표면에 반복 접촉하고, 문 너머 반응을 기다린다. `point`, `wave`, `press`와 달리 같은 지점의 반복 타격이 핵심이다.
- 시각 계약: `prepare` 닫힌 문 앞에서 손을 주먹으로 모으고 문을 바라본다 -> `act` 주먹이 문에 세 번 닿는다 -> `hold` 손을 내리고 응답을 기다리며 닫힌 문을 유지한다 -> `recover` 문이 열리거나 캐릭터가 다음 행동으로 돌아간다.
- 혼동/음성 cue: `open`, `press`, `wave`, `attack`과 혼동된다. **negative cue:** 문이 없는데 허공을 치기, 문이 두드리기 전에 열림, 주먹이 문을 관통, 무기를 휘두르는 큰 궤적.
- 우선순위: **next asset**. 성문·비밀방·마법 오두막에 빈도가 높고 오디오 없이도 접촉 횟수가 보인다.

### 6. 보물을 든 채 나르다 — `carry_treasure`

- 예문: **The children carried the heavy treasure chest back to the village.**
- 분류: **prop-bound**. 상자·보따리·지도 같은 지속 보유 물체와 목적지 공간이 필요하다.
- 한 장면 판독성: 물체를 들어 올리는 순간이 아니라, 양손 또는 팔에 물체를 고정한 채 발과 몸의 위치가 화면 안에서 이동한다. `lift`와 `pick_up`보다 이동 지속성이 결정적이다.
- 시각 계약: `prepare` 이미 든 상자의 무게를 확인하고 양손을 고정한다 -> `act` 상자를 몸 앞에 유지한 채 몇 걸음 이동한다 -> `hold` 이동 중 상자와 손의 접점을 유지하고 잠시 멈춘다 -> `recover` 목적지에 상자를 안정적으로 내려놓을 준비를 한다.
- 혼동/음성 cue: `hold`, `lift`, `pick_up`, `journey`와 혼동된다. **negative cue:** 물체가 없는 걷기, 물체가 순간적으로 사라짐, 한 프레임에서만 들어 올리고 이동하지 않음, 상자가 캐릭터와 함께 미끄러짐.
- 우선순위: **later asset**. 이동·손 접점·무게 중심을 동시에 검증해야 하므로 다음 단독 시트보다 장면 합성이 먼저다.

### 7. 단서를 떨어뜨리다 — `drop_clue`

- 예문: **The fairy dropped a bright pebble beside the hidden path.**
- 분류: **prop-bound**. 손에 든 돌·보석·단서와 명확한 바닥 또는 표면이 필요하다.
- 한 장면 판독성: 손이 물체를 들고 있다가 펴지고, 물체가 손에서 분리되어 아래로 이동한 뒤 표면에 남는다. 기존 `pick_up`의 역방향으로, 물체의 소유 상태가 바뀐다.
- 시각 계약: `prepare` 손 안의 단서를 바닥의 위치 위에 가져간다 -> `act` 손가락을 펴 단서를 놓고 물체가 아래로 떨어진다 -> `hold` 단서가 바닥에 남고 손은 비어 있는 상태를 유지한다 -> `recover` 손을 거두고 다음 길 또는 표적을 바라본다.
- 혼동/음성 cue: `fall`, `pick_up`, `place`, `throw`와 혼동된다. **negative cue:** 팔을 크게 휘둘러 멀리 던지기, 캐릭터가 넘어짐, 물체가 손에 계속 붙음, 바닥에 닿기 전에 사라짐.
- 우선순위: **later asset**. 물리적 낙하와 손-물체 분리를 안정적으로 보여야 한다.

### 8. 등불에 불을 붙이다 — `light_lantern`

- 예문: **The girl lit the lantern, and the dark cave became bright.**
- 분류: **prop-bound**. 심지와 등불·횃불, 그리고 밝아지는 주변이 필요하다.
- 한 장면 판독성: 불씨나 성냥이 심지에 닿은 뒤 작은 불꽃과 주변 밝기가 생긴다. 손에서 빛을 발사하는 `magic`과 달리 광원이 물체에 붙는다.
- 시각 계약: `prepare` 등불과 불씨를 가까이 들고 심지를 확인한다 -> `act` 불씨를 심지에 접촉시킨다 -> `hold` 심지의 불꽃과 등불 주변의 밝아진 상태를 유지한다 -> `recover` 불씨를 치우고 등불을 든 채 다음 공간을 비춘다.
- 혼동/음성 cue: `magic`, `press`, `turn_on`, `light`의 다른 의미와 혼동된다. **negative cue:** 광원 없는 손빛, 심지에 닿지 않는 불꽃, 불꽃이 등불과 분리되어 따라다님, 주변 밝기 변화 없음.
- 우선순위: **later asset**. 불꽃·광원·배경 노출 변화의 안전한 합성이 필요하다.

### 9. 마법 물약을 젓다 — `stir_potion`

- 예문: **The young witch stirred the silver potion three times.**
- 분류: **prop-bound**. 가마솥·컵과 숟가락 또는 지팡이 끝이 필요하다.
- 한 장면 판독성: 도구 끝이 액체 표면에 닿아 원형으로 반복되고, 액체가 소용돌이치거나 색이 섞인다. 손을 흔드는 `wave`나 `magic`과 분리된다.
- 시각 계약: `prepare` 용기와 도구를 확인하고 도구를 액체 위에 둔다 -> `act` 도구가 액체에 닿아 작은 원을 세 번 그린다 -> `hold` 섞인 색과 잔잔한 소용돌이를 유지한다 -> `recover` 도구를 들어 올리고 용기를 바라본다.
- 혼동/음성 cue: `magic`, `wave`, `turn_dial`, `pour`와 혼동된다. **negative cue:** 액체·도구 없는 공중 원운동, 손끝 광선, 용기 밖에서 젓기, 액체 상태 변화 없음.
- 우선순위: **later asset**. 중경 이상과 액체 효과가 필요하며 장면 전용으로 먼저 시험한다.

### 10. 물약을 따르다 — `pour_potion`

- 예문: **The prince poured the glowing potion into a tiny glass.**
- 분류: **prop-bound**. 액체가 든 용기와 받을 컵·가마솥·홈이 필수다.
- 한 장면 판독성: 용기가 기울고 연속된 액체 줄기가 다른 용기로 이동한다. `drink`와 달리 물체가 입에 가지 않고 두 용기 사이를 흐른다.
- 시각 계약: `prepare` 원래 용기와 받을 용기를 가까이 맞춘다 -> `act` 원래 용기를 기울여 액체 줄기를 만든다 -> `hold` 액체가 받을 용기에 흐르는 상태를 잠시 유지한다 -> `recover` 용기를 세우고 두 용기를 안정시킨다.
- 혼동/음성 cue: `drink`, `place`, `magic`, `drop`과 혼동된다. **negative cue:** 액체 줄기 없음, 컵이 입에 닿음, 빈 용기를 흔듦, 액체가 손에서 바로 생성됨.
- 우선순위: **later asset**. 손·용기·액체의 연속성이 작게 렌더될 때도 남아야 한다.

### 11. 칼을 칼집에서 뽑다 — `draw_sword`

- 예문: **The hero drew his silver sword when the stone door shook.**
- 분류: **prop-bound**, 표적·위험은 선택적이다. 칼집과 칼의 분리 상태가 필수다.
- 한 장면 판독성: 한 손이 칼자루를 잡고 칼날이 칼집에서 길게 분리되며, 마지막에 칼을 낮춰 유지한다. `battle`·`magic`처럼 이미 휘두르는 동작과 다르다.
- 시각 계약: `prepare` 칼집과 칼자루를 확인하고 손을 칼자루에 둔다 -> `act` 칼을 한 방향으로 뽑아 칼집과 완전히 분리한다 -> `hold` 칼날을 안전한 아래쪽 또는 옆으로 유지한다 -> `recover` 공격하지 않고 경계 자세로 돌아간다.
- 혼동/음성 cue: `battle`, `magic`, `wave`, `pull`과 혼동된다. **negative cue:** 칼집 없는 허공에서 칼 생성, 칼을 크게 휘두르기, 칼날이 손에 붙음, 표적을 찌르는 동작.
- 우선순위: **later asset**. 칼집·칼날 가림·안전한 회복 자세의 에셋 검수가 필요하다.

### 12. 종을 울리다 — `ring_bell`

- 예문: **The boy rang the silver bell, and the sleeping castle woke.**
- 분류: **prop-bound**. 손에 들거나 매달린 종과 고정 지점·줄이 필요하다.
- 한 장면 판독성: 종을 흔들거나 줄을 당긴 뒤 종의 내부 추 또는 진동이 보이고, 인물이 반응을 기다린다. 소리가 없어도 반복 흔들림과 종 형태가 의미를 보조한다.
- 시각 계약: `prepare` 종 또는 종줄의 위치를 확인한다 -> `act` 종을 좌우로 흔들거나 줄을 한 번 당긴다 -> `hold` 종이 흔들림을 멈추며 신호 후 대기 상태를 유지한다 -> `recover` 손을 놓고 문·성·파트너의 반응을 본다.
- 혼동/음성 cue: `wave`, `pull_lever`, `press`, `magic`과 혼동된다. **negative cue:** 종 없는 손 흔들기, 줄이 없는 공중 당기기, 벨이 움직이지 않음, 소리만 있고 접촉이 없음.
- 우선순위: **later asset**. 이야기 장치로는 좋지만 무음 환경의 판독성 검사가 필요하다.

### 13. 지도에 표시하다 — `mark_map`

- 예문: **Lina marked the cave on the treasure map with a red X.**
- 분류: **prop-bound**이며 읽기·쓰기 장면에 가깝다. 지도와 펜·숯·손가락이 필수다.
- 한 장면 판독성: 지도 위 특정 위치에 선·X가 실제로 남고, 캐릭터가 그 위치를 확인한다. 단, 작은 프레임에서는 필기와 읽기의 차이가 약하다.
- 시각 계약: `prepare` 펼친 지도에서 목표 지점을 찾고 도구 끝을 그 위에 둔다 -> `act` 짧은 선 또는 X를 그린다 -> `hold` 새 표시와 지도 위 위치를 보여준다 -> `recover` 도구를 내리고 표시된 장소를 가리키거나 바라본다.
- 혼동/음성 cue: `read`, `point`, `investigate`, `write`와 혼동된다. **negative cue:** 지도 없는 공중 필기, 표시가 남지 않음, 페이지를 읽기만 함, 도구 끝과 종이 접촉 없음.
- 우선순위: **text-only/scene-only**. 지도 확대·필기 도구·표시 유지가 보장되지 않으면 새 기본 모션으로 추천하지 않는다.

### 14. 봉인을 찍다 — `stamp_seal`

- 예문: **The queen stamped the royal mark into the warm wax.**
- 분류: **prop-bound**. 도장·왁스·문서와 남는 문양이 필요하다.
- 한 장면 판독성: 도장을 위에서 내려 눌렀다가 들어 올리고, 표면에 문양이 새로 남는다. `press_seal`과는 “누른 채 유지”가 아니라 “압인 후 분리와 흔적 확인”이 핵심이다.
- 시각 계약: `prepare` 도장 면을 왁스 위에 맞춘다 -> `act` 한 번 강하게 눌렀다가 수직으로 들어 올린다 -> `hold` 왁스에 새 문양이 남은 상태를 보여준다 -> `recover` 도장을 옆에 두고 봉인된 문서를 확인한다.
- 혼동/음성 cue: `press_seal`, `place`, `magic`, `clap`과 혼동된다. **negative cue:** 도장이 표면에 남아 있음, 압인 흔적 없음, 발을 구르는 `stamp`, 손에서 마법 문양이 떠오름.
- 우선순위: **text-only/scene-only**. `press_seal`과 별도 기본 action으로 만들기보다, 같은 소품의 하위 phase로 먼저 두는 편이 안전하다.

## Top 7 권장 순위

| 순위 | 후보 | 권장 이유 | 선행 조건 |
|---:|---|---|---|
| 1 | `pull_lever` | 레버 접점과 장치 반응이 짧은 영상에서 명확하다. | 레버+연결 문/다리 상태 변화 |
| 2 | `turn_dial` | 몸 회전이 아니라 작은 원형 조작이라는 경계가 분명하다. | 눈금·문양이 있는 다이얼 |
| 3 | `place_gem` | 손에서 홈으로 보석이 이동하고 유물이 활성화되는 인과가 강하다. | 보석·홈·활성화 결과 |
| 4 | `press_seal` | 봉인과 마법문 모두에 재사용할 수 있고 흔적이 남는다. | 도장·왁스/표면·문양 |
| 5 | `knock_on_door` | 문 앞의 반복 접촉이 `open`·`wave`와 쉽게 분리된다. | 닫힌 문과 기다림 상태 |
| 6 | `carry_treasure` | 기존 `pick_up`·`lift` 다음 장면의 지속 운반을 채운다. | 고정된 물체·화면 내 이동 경로 |
| 7 | `light_lantern` | `magic`과 달리 광원 물체의 상태 변화가 시각적이다. | 심지·불씨·주변 밝기 |

`stir_potion`, `pour_potion`, `draw_sword`, `ring_bell`은 이야기 활용도는 높지만 중경·소품·효과 합성에 의존하므로 2차 에셋으로 둔다. `mark_map`과 `stamp_seal`은 의미는 자연스럽지만 작은 화면에서 각각 `read/write`, `press_seal`과 겹치므로 당장은 텍스트·장면 태그 또는 기존 상호작용의 하위 phase가 적절하다.

## 기존 단어와의 경계 요약

- `pull_lever`는 일반 `pull`을 추가하는 것이 아니다. 레버 손잡이를 당기고 연결된 장치가 움직이는 좁은 sense만 허용한다.
- `turn_dial`은 캐릭터가 도는 `turn`이 아니다. 다이얼의 중심축과 눈금 정렬이 화면에 있어야 한다.
- `place_gem`은 이미 검토된 `insert`를 다시 추천하는 것이 아니다. 손에 든 보석이 홈에 내려가고 손에서 분리되는 결과 상태를 canonical 계약으로 고정한다.
- `press_seal`과 `stamp_seal`은 둘 다 손바닥·도장과 표면 접촉이 필요하다. 압력을 유지하는 단계가 보이지 않으면 `stamp_seal`을 별도 action으로 만들지 않는다.
- `carry_treasure`는 `lift`가 아니다. 물체를 든 채 실제 발 이동이 있어야 하며, 물체가 이동하지 않으면 `hold`로 낮춘다.
- `light_lantern`은 `magic`이 아니다. 불꽃이 손에서 생성되지 않고 등불 심지에 붙어 주변을 밝히는 상태 변화가 있어야 한다.

## 출처

- British Council LearnEnglish Kids, [The treasure map](https://learnenglishkids.britishcouncil.org/listen-watch/short-stories/treasure-map): 병 속 지도, 보물 찾기, 지도를 따라가는 아동 이야기 자료.
- British Council LearnEnglish Kids, [An adventure story](https://learnenglishkids.britishcouncil.org/read-write/writing-practice/level-3-writing/adventure-story): 오래된 지도, 숲속 비밀 장소, 보물을 찾는 모험 이야기 어휘.
- Cambridge Learner’s Dictionary, [knock](https://dictionary.cambridge.org/us/dictionary/learner-english/knock): 닫힌 문을 주먹으로 쳐 주의를 끄는 의미.
- Oxford Advanced Learner’s Dictionary, [press](https://www.oxfordlearnersdictionaries.com/definition/american_english/press_2): 버튼·스위치·키를 눌러 작동시키는 의미.
- Oxford Advanced Learner’s Dictionary, [pull](https://www.oxfordlearnersdictionaries.com/definition/english/pull_1) 및 [lever](https://www.oxfordlearnersdictionaries.com/us/definition/english/lever_1): 레버를 당겨 장치를 작동하는 결합.
- Oxford Advanced Learner’s Dictionary, [turn](https://www.oxfordlearnersdictionaries.com/definition/english/turn_1) 및 [dial](https://www.oxfordlearnersdictionaries.com/us/definition/english/dial_1): 중심축을 돌리거나 다이얼을 돌려 설정하는 의미.
- Oxford Advanced Learner’s Dictionary, [place](https://www.oxfordlearnersdictionaries.com/definition/english/place_2): 물체를 특정 위치에 조심스럽고 의도적으로 놓는 의미.
- Cambridge Learner’s Dictionary, [carry](https://dictionary.cambridge.org/us/dictionary/learner-english/carry): 손·팔·등으로 물체를 든 채 다른 곳으로 옮기는 의미.
- Merriam-Webster, [drop](https://www.merriam-webster.com/dictionary/drop): 물체를 떨어뜨리거나 떨어지게 하는 의미.
- Merriam-Webster, [light](https://www.merriam-webster.com/dictionary/light): 불을 붙이거나 점화하는 의미.
- Oxford Advanced Learner’s Dictionary, [pour](https://www.oxfordlearnersdictionaries.com/us/definition/english/pour) 및 [stir](https://www.oxfordlearnersdictionaries.com/us/definition/english/stir_1): 용기에서 액체를 흐르게 하거나 도구로 액체를 저어 섞는 의미.
- Oxford Advanced Learner’s Dictionary, [mark](https://www.oxfordlearnersdictionaries.com/us/definition/english/mark_1): 정보 제공을 위해 기호·선을 쓰거나 그리는 의미.
- Oxford Advanced Learner’s Dictionary, [draw](https://www.oxfordlearnersdictionaries.com/us/definition/english/draw_1): 공격을 위해 칼 같은 무기를 칼집에서 꺼내는 의미.
- Oxford Advanced Learner’s Dictionary, [bell](https://www.oxfordlearnersdictionaries.com/us/definition/english/bell): 종을 울리는 물체와 `ring the bell` 결합 예.

## 한계

- 사전은 동사의 핵심 의미와 물체 결합을 확인하지만, 실제 한국어 동화 문장 빈도나 어린이의 무라벨 영상 판독률을 직접 측정하지 않는다.
- British Council 자료는 교육용 짧은 이야기이므로 한국어 아동 동화 전체의 대표 표본은 아니다. 지도·보물·비밀 장소가 자연스럽게 결합되는지 확인하는 보조 근거로만 사용했다.
- `press_seal`, `place_gem`, `pull_lever`, `turn_dial`은 일반 동사의 의미를 소품 계약으로 좁힌 canonical key 제안이다. 실제 채택 전에는 기존 분류기의 동의어 확장 없이 장면 단위 샘플로 오인율을 검증해야 한다.
- 이 보고서는 어휘·시각 계약 연구만 수행했으며, 어떤 코드·데이터베이스·런타임 분류·이미지/영상 에셋도 변경하지 않았다.
