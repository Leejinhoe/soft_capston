# Round 4 어휘 연구: 탐험·장소 이동

- 작성일: 2026-08-10 (KST)
- 역할: 탐험·장소 이동
- 범위: 성, 동굴, 숲, 폐허, 다리, 절벽, 비밀 통로에서 경로를 읽게 하는 동작
- 산출물 제한: 이 보고서만 작성했으며 이미지·영상과 런타임/백엔드/데이터베이스 코드는 변경하지 않았다.

## 방법

1. 먼저 `treasure_story_words.md`, `round3_words_language.md`, `round3_words_assets.md`, `round3_words_motion.md`, `generated_round3`, `generated_v2`, `merged_visual_vocabulary.json`을 읽었다. 기존 `walk/journey`, `run`, `jump`, `investigate`, `climb`, `crawl`, `slide`, `hide`, `fall_roll`, `enter`, `escape`, `follow`, `chase`, `dig`, `push`, `pull`, `peek`, `lean`, `swim`, `dive`, `salute`, `wake`, `yawn`, `sneeze` 등은 새 기본 후보에서 제외했다.
2. Cambridge, Oxford Learner's Dictionaries, Merriam-Webster의 동사 정의를 대조했다. 동화 경로에 실제로 쓰이는지는 British Council LearnEnglish Kids의 *The treasure map*과 답안 자료의 `cross the bridge`, `go through the cave` 같은 길찾기 문장으로 확인했다.
3. 후보는 `prepare -> act -> hold -> recover`를 한 장면에서 읽을 수 있고, 기존 동작과 다른 접점/경로 결과가 보일 때만 남겼다. 물, 벽, 틈, 다리, 배처럼 환경·소품이 의미를 완성하면 solo로 올리지 않았다.

## 기존 자료와의 경계

- `cross_bridge`는 일반 `walk`가 아니다. 다리의 시작 쪽, 건너는 중간, 반대편 착지/도달이 같은 경로 축에 보여야 한다.
- `vault`는 기존 `jump` 또는 Round 3의 “뛰어넘다”를 넓혀 부르는 말이 아니다. 손을 장애물에 짚고 몸이 장애물 위를 넘는 좁은 시각적 의미로만 검토한다.
- `duck_under`는 기존 `crouch`가 아니다. 낮은 나뭇가지·성문 들보·무너진 폐허 아래를 실제로 통과해야 한다.
- `squeeze_through`는 기존 `crawl`이 아니다. 양쪽 벽이 좁고 어깨를 돌려 몸을 압축한 채 틈의 반대편으로 빠져나와야 한다.
- `wade`는 `walk`의 물 배경 버전이 아니다. 수면선, 물의 저항, 물결/튀는 물이 발걸음과 함께 있어야 한다.
- `backtrack`, `detour`, `retreat`는 이동 자체보다 경로·위협 정보가 핵심이어서 단독 인물 시트의 우선순위를 낮췄다.

## 후보 요약

| 순위 | 한국어 의미 | 제안 English key | 분류 | 우선도 | 한 줄 판정 |
|---:|---|---|---|---|---|
| 1 | 다리를 건너다 | `cross_bridge` (`cross`) | environment-bound | **next asset** | 다리와 양쪽 끝의 관계가 있어 `walk`와 분리 가능 |
| 2 | 좁은 틈을 비집고 지나가다 | `squeeze_through` (`squeeze`) | environment-bound | **next asset** | 양쪽 벽, 어깨 회전, 반대편 reveal이 한 사이클을 만듦 |
| 3 | 몸을 숙여 아래로 지나가다 | `duck_under` (`duck`) | environment-bound | **next asset** | 낮은 장애물 아래 통과가 `crouch`와 직접 구별됨 |
| 4 | 손을 짚고 장애물을 뛰어넘다 | `vault` | environment-bound | **later asset** | 손-장애물 접점이 있어 `jump`와 분리 가능 |
| 5 | 얕은 물을 헤치며 걷다 | `wade` | environment-bound | **later asset** | 수면선과 물 저항이 지상 보행과 다름 |
| 6 | 노를 저어 배를 움직이다 | `row` | prop-bound | **later asset** | 양손-노-배-수면의 인과가 명확함 |
| 7 | 어둠/동굴에서 모습을 드러내다 | `emerge` | environment-bound | **scene-only** | 임계점을 넘는 reveal은 유용하나 보행과 합쳐짐 |
| 8 | 배·마차·비행선에 올라타다 | `board` | prop-bound | **scene-only** | 탈것과 승강 접점 없이는 성립하지 않음 |
| 9 | 배·마차·비행기에서 내리다 | `disembark` | prop-bound | **scene-only** | 탈것에서 지면으로 이동하는 전환 장면에 한정 |
| 10 | 왔던 길을 되짚어 돌아가다 | `backtrack` | environment-bound | **scene-only** | 발자국/지도/잘못 든 갈림길이 없으면 `walk`·`turn`임 |
| 11 | 막힌 곳을 피해 우회하다 | `detour` | environment-bound | **text-only/scene-only** | 다른 경로 선택은 장면 지도에 더 잘 담김 |
| 12 | 위협을 피해 물러서다 | `retreat` | target-bound | **text-only/scene-only** | 적·위험이 없으면 `walk`를 뒤로 재생한 것과 같음 |

## 후보별 검토

### 1. 다리를 건너다 — `cross_bridge`

- **의미/근거:** `cross`는 한쪽에서 다른 쪽으로 가는 동작이며 [Cambridge Learner's Dictionary의 cross](https://dictionary.cambridge.org/dictionary/learner-english/cross)는 이를 “one side ... to the other”로 설명한다. 다리는 사람이 양쪽을 건너게 하는 구조물이라는 [Cambridge의 bridge 정의](https://dictionary.cambridge.org/dictionary/english/bridge)와 결합한다. British Council의 어린이 보물찾기 자료에도 `Cross the bridge`가 직접 등장한다([story](https://learnenglishkids.britishcouncil.org/listen-watch/short-stories/treasure-map), [answers PDF](https://learnenglishkids.britishcouncil.org/sites/kids/files/attachment/stories-the-treasure-map-worksheet-answers-final-2012-12-04.pdf)).
- **동화 문장:** “The child crosses the old bridge to reach the castle.” (아이가 성에 가려고 낡은 다리를 건넌다.)
- **분류:** `environment-bound`. 다리, 양쪽 끝, 건너편 지면이 필수다.
- **한 에셋으로 보이는 이유:** 좁은 판자/돌다리 위의 발 디딤, 난간 또는 계곡 아래, 반대편 지면을 한 화면에 두면 경로 결과가 보행과 함께 읽힌다.
- **시각 계약:** `prepare` 다리 입구에서 폭과 건너편을 확인하고 양발을 정렬 -> `act` 다리 위로 발을 옮기며 난간/줄을 잡거나 팔로 균형 유지 -> `hold` 다리 중앙에서 한 발을 내딛은 채 계곡과 반대편을 보여 줌 -> `recover` 반대편 지면에 양발을 딛고 다리에서 벗어나 중립.
- **혼동/부정 cue:** `walk`와 혼동되므로 다리 없이 평지 걷기, 반대편 도달 없이 제자리 보행, 공중에 뜬 발, `jump`처럼 두 발 동시 이탈을 금지한다. `climb`처럼 난간을 오르지도 않는다.
- **우선도:** **next asset**. 다리 배경/경로를 포함한 환경 합성 한 세트가 있으면 동화 장면과 학습 가치가 높다.

### 2. 좁은 틈을 비집고 지나가다 — `squeeze_through`

- **의미/근거:** [Merriam-Webster의 squeeze](https://www.merriam-webster.com/dictionary/squeeze)는 “to get by squeezing”를 포함한다. 여기서는 넓은 의미의 압착이 아니라 두 벽 사이를 몸을 줄여 통과하는 어린이 동화 장면으로 고정한다.
- **동화 문장:** “The child squeezes through the crack in the ruined wall and finds a secret passage.” (아이가 폐허 벽의 틈을 비집고 지나가 비밀 통로를 찾는다.)
- **분류:** `environment-bound`. 양쪽 벽/바위와 반대편 출구가 필수다.
- **한 에셋으로 보이는 이유:** 몸통을 옆으로 돌리고 어깨를 안으로 모은 뒤 좁은 틈에서 사라졌다가 반대편에서 다시 보이는 변화가 단일한 의미 단서다.
- **시각 계약:** `prepare` 틈의 폭을 손으로 재고 몸을 옆으로 돌림 -> `act` 어깨·팔을 접어 한 발씩 틈 안으로 밀어 넣음 -> `hold` 몸통이 양쪽 벽에 가까운 좁은 중간 지점에서 압축된 자세 유지 -> `recover` 반대편으로 몸 전체가 빠져나와 어깨를 펴고 중립.
- **혼동/부정 cue:** `crawl`처럼 네 발로 이동, `hide`처럼 가림막 뒤에서 정지, `walk`처럼 어깨 폭이 그대로인 통과를 금지한다. 틈이 없거나 캐릭터가 순간 삭제되면 실패다.
- **우선도:** **next asset**. 비밀 통로를 탐험하는 장면에서 접점과 reveal이 모두 선명하다.

### 3. 몸을 숙여 아래로 지나가다 — `duck_under`

- **의미/근거:** [Merriam-Webster의 duck](https://www.merriam-webster.com/dictionary/duck)는 머리나 몸을 빠르게 낮추는 뜻을 제시하고, 낮은 천장 아래에서 머리를 숙이는 예를 든다. `under`는 낮은 장애물 아래 통과를 명시하는 시각 수식어다.
- **동화 문장:** “The child ducks under the fallen tree in the forest.” (아이가 숲에서 쓰러진 나무 아래로 몸을 숙여 지나간다.)
- **분류:** `environment-bound`. 낮은 가지·들보·쓰러진 나무와 그 아래의 통과 공간이 필수다.
- **한 에셋으로 보이는 이유:** 머리 높이가 장애물 아래로 내려갔다가 반대편에서 다시 올라오는 높이 변화가 `crouch`와 다르다.
- **시각 계약:** `prepare` 머리 위 장애물을 보고 발을 멈추며 무릎을 풀음 -> `act` 머리·어깨를 빠르게 낮추고 한 손으로 장애물을 짚으며 아래로 통과 -> `hold` 몸이 가장 낮은 지점에서 장애물 아래에 위치 -> `recover` 장애물을 지나 몸을 세우고 다음 길을 향함.
- **혼동/부정 cue:** 제자리 `crouch`, 고개만 숙이는 `bow`, 장애물 없이 낮아지는 모션, `crawl`처럼 무릎과 손이 바닥에 닿는 모션을 금지한다. 장애물 접촉 높이가 머리보다 높으면 의미가 약해진다.
- **우선도:** **next asset**. 숲·폐허·성문에서 재사용할 수 있고 기존 `crouch`와의 부정 cue가 명확하다.

### 4. 손을 짚고 장애물을 뛰어넘다 — `vault`

- **의미/근거:** [Merriam-Webster의 vault](https://www.merriam-webster.com/dictionary/vault)는 손이나 막대의 도움으로 뛰어넘는 동작으로 정의한다. 따라서 기존의 제자리 `jump`나 이미 검토된 일반적인 “뛰어넘다”가 아니라 **손을 장애물에 먼저 짚는 좁은 의미**로만 제안한다.
- **동화 문장:** “The brave child vaults over the broken stone wall.” (용감한 아이가 무너진 돌담을 손을 짚고 뛰어넘는다.)
- **분류:** `environment-bound`. 낮은 돌담·난간·무너진 벽과 착지 공간이 필수다.
- **한 에셋으로 보이는 이유:** 접근, 손바닥 접촉, 골반이 장애물 위를 지나감, 반대편 착지가 하나의 뚜렷한 궤적이다.
- **시각 계약:** `prepare` 장애물 앞에서 속도를 줄이고 팔을 앞으로 준비 -> `act` 한두 손을 돌담 위에 짚고 발을 지면에서 떼어 몸을 넘김 -> `hold` 골반이 장애물 위를 지나고 손 접점이 유지되는 최고점 -> `recover` 반대편에 양발 착지 후 손을 떼고 균형 회복.
- **혼동/부정 cue:** 손 접촉 없는 `jump`, 장애물 옆을 걷는 `walk`, 벽면에 매달리는 `climb`, 넘어져 구르는 `fall_roll`을 금지한다. 장애물이 프레임 밖이면 canonical key를 `jump`로 낮춘다.
- **우선도:** **later asset**. 시각적으로 강하지만 안전한 착지와 손-장애물 접점 검수 비용이 있다.

### 5. 얕은 물을 헤치며 걷다 — `wade`

- **의미/근거:** [Oxford Learner's Dictionaries의 wade](https://www.oxfordlearnersdictionaries.com/definition/english/wade)는 물이나 진흙을 힘들게 걷는다고 설명하며, 개울을 건너는 예문도 제시한다. [Merriam-Webster의 wade](https://www.merriam-webster.com/dictionary/wade)도 공기보다 저항이 큰 매질을 통과하는 발걸음으로 설명한다.
- **동화 문장:** “The child wades across the shallow stream to the hidden cave.” (아이가 숨은 동굴로 가려고 얕은 개울을 헤치며 건넌다.)
- **분류:** `environment-bound`. 물 깊이, 수면선, 물결이 필수다.
- **한 에셋으로 보이는 이유:** 다리가 물에 잠기고 발걸음마다 물결/튀는 물이 생기며, 몸통은 세워진 채 저항을 받는 모습이 `walk`·`swim`과 다르다.
- **시각 계약:** `prepare` 물가에서 깊이와 건너편을 확인하고 바짓단/발을 물에 넣음 -> `act` 무릎 아래 물을 밀며 짧고 무거운 보폭으로 전진 -> `hold` 물살 속에서 한 발을 들어 저항을 이기는 순간과 수면선을 유지 -> `recover` 반대편 마른 땅에 발을 올리고 물을 털며 중립.
- **혼동/부정 cue:** 물 없는 평지 `walk`, 몸이 수평인 `swim`, 물속으로 몸을 던지는 `dive`, 물 위를 걷는 모습, 수면선 없는 투명 시트를 금지한다.
- **우선도:** **later asset**. 환경 제작이 필요하지만 지상 이동과 다른 명확한 물리 단서가 있다.

### 6. 노를 저어 배를 움직이다 — `row`

- **의미/근거:** [Cambridge Dictionary의 row](https://dictionary.cambridge.org/dictionary/english/row)는 노로 물을 밀어 배를 움직이는 동작으로 정의한다. [Cambridge Learner's Dictionary의 row](https://dictionary.cambridge.org/dictionary/learner-english/row)도 노를 사용해 배를 이동시키는 뜻과 섬으로 나아가는 예문을 제시한다.
- **동화 문장:** “The child rows across the moonlit lake toward the castle.” (아이가 달빛 호수를 건너 성을 향해 노를 젓는다.)
- **분류:** `prop-bound`. 배, 노, 수면과 배의 이동이 필수다.
- **한 에셋으로 보이는 이유:** 양손이 노 손잡이를 잡고 당긴 뒤 노 끝이 물을 밀며 배가 뒤로/앞으로 이동하는 인과가 분명하다.
- **시각 계약:** `prepare` 배 안에서 노를 양손으로 잡고 물 방향을 확인 -> `act` 노를 물에 넣어 몸 쪽으로 당김 -> `hold` 노가 물에 잠긴 채 배와 수면이 상대적으로 이동하는 순간 유지 -> `recover` 노를 물에서 빼고 다음 젓기를 준비.
- **혼동/부정 cue:** 노·배 없는 양팔 휘두르기, `swim`처럼 몸이 물에 뜨는 모션, `pull`처럼 고정된 물체를 당기기, 배가 이동하지 않는 제자리 동작을 금지한다.
- **우선도:** **later asset**. 성·동굴·폐허 섬으로 이어지는 경로에는 좋지만 배와 노가 별도 소품 자산이다.

### 7. 어둠/동굴에서 모습을 드러내다 — `emerge`

- **의미/근거:** [Oxford Learner's Dictionaries의 emerge](https://www.oxfordlearnersdictionaries.com/definition/english/emerge)는 보이지 않던 곳에서 나와 보이게 되는 동작을 설명하고 `emerge from the shadows`, `emerge into bright sunlight` 예문을 든다.
- **동화 문장:** “The child emerges from the secret passage into the castle hall.” (아이가 비밀 통로에서 나와 성의 큰 방에 모습을 드러낸다.)
- **분류:** `environment-bound`. 동굴/통로의 어두운 입구와 밝은 출구, 경계선이 필수다.
- **한 에셋으로 보이는 이유:** 어둠 속 실루엣이 보이기 시작하고 임계선을 넘어 전신이 reveal되는 장면은 장소 이동 결과를 분명히 한다.
- **시각 계약:** `prepare` 통로 안의 일부 실루엣만 보이고 출구 빛을 향함 -> `act` 몸과 발이 출구 경계선을 통과하며 점점 드러남 -> `hold` 밝은 공간에 전신이 드러난 채 잠시 주변을 확인 -> `recover` 통로에서 완전히 벗어나 다음 경로의 중립.
- **혼동/부정 cue:** `enter`처럼 밝은 곳에서 어둠으로 사라지는 방향, `hide`처럼 가림막 뒤 정지, `escape`처럼 추격을 전제로 한 질주, 장면 전환만으로 순간 등장하는 것을 금지한다.
- **우선도:** **scene-only**. 인물의 새 전신 주기보다 조명·가림·카메라 reveal가 의미의 절반을 담당한다.

### 8. 배·마차·비행선에 올라타다 — `board`

- **의미/근거:** [Cambridge Dictionary의 board](https://dictionary.cambridge.org/dictionary/english/board)는 배·기차·비행기 등에 올라타는 뜻을 제시한다. 동화에서는 배, 마차, 비행선 중 하나를 장면 소품으로 명시한다.
- **동화 문장:** “The child boards the little boat before the river fog arrives.” (강 안개가 오기 전에 아이가 작은 배에 올라탄다.)
- **분류:** `prop-bound`. 탈것, 승강 지점/사다리, 탑승 전후의 높이 변화가 필수다.
- **한 에셋으로 보이는 이유:** 지면에서 발판으로 올라가 몸을 탈것 안으로 옮기고, 마지막에 탈것 내부에 안정되는 상태 변화가 있다.
- **시각 계약:** `prepare` 부두나 마차 옆에서 탈것 입구와 발판을 확인 -> `act` 손잡이/난간을 잡고 한 발씩 발판을 올라 안으로 들어감 -> `hold` 몸통이 탈것 내부에 있고 발이 바닥에 안정된 탑승 자세 -> `recover` 손을 놓고 앉거나 서서 출발 준비.
- **혼동/부정 cue:** 탈것 없는 `climb`, 문 안으로 들어가는 `enter`, 배 위에서 이미 걷는 모션, 발판 없이 순간 이동을 금지한다.
- **우선도:** **scene-only**. 어휘는 유용하지만 실제 모션은 탈것별로 달라 공통 단독 시트로 만들기 어렵다.

### 9. 배·마차·비행기에서 내리다 — `disembark`

- **의미/근거:** [Oxford Learner's Dictionaries의 disembark](https://www.oxfordlearnersdictionaries.com/definition/english/disembark)는 여행 뒤 탈것, 특히 배나 비행기에서 내리는 뜻을 제시한다. [Cambridge의 disembark](https://dictionary.cambridge.org/dictionary/english/disembark)도 배·비행기 등에서 내리는 동작으로 정의하며 `board`를 반대말로 둔다.
- **동화 문장:** “The child disembarks from the boat beside the ruined tower.” (아이가 폐허 탑 옆에서 배에서 내린다.)
- **분류:** `prop-bound`. 탈것의 내부, 가장자리/사다리, 도착한 지면이 필수다.
- **한 에셋으로 보이는 이유:** 탈것의 높이에서 발판을 거쳐 지면으로 내려오고, 마지막에 물 밖/땅 위의 안정 자세가 되는 방향 전환이 분명하다.
- **시각 계약:** `prepare` 배 가장자리에서 도착 지면과 발판을 살핌 -> `act` 난간을 잡고 발판/선착장으로 한 발씩 내려감 -> `hold` 한 발은 지면, 한 발은 탈것에 둔 전환 순간 -> `recover` 양발을 지면에 놓고 탈것에서 완전히 벗어남.
- **혼동/부정 cue:** 탈것 없는 `walk`·`descend`(기존 내려가다), `board`처럼 지면에서 위로 오르는 방향, 지면 접점 없이 점프하는 모습을 금지한다.
- **우선도:** **scene-only**. `board`와 짝으로는 좋지만 탈것 종류와 카메라 높이에 강하게 묶인다.

### 10. 왔던 길을 되짚어 돌아가다 — `backtrack`

- **의미/근거:** [Cambridge Dictionary의 backtrack](https://dictionary.cambridge.org/dictionary/english/backtrack)은 방금 지나온 길을 따라 되돌아가는 동작이다.
- **동화 문장:** “The child backtracks to the fork after following the wrong torch.” (아이가 잘못된 횃불을 따라간 뒤 갈림길로 되돌아간다.)
- **분류:** `environment-bound`. 갈림길, 발자국/횃불/지도 같은 이전 경로 표식이 필수다.
- **한 에셋으로 보이는 이유:** 새 방향으로 나아가던 인물이 표식을 알아차리고 180도 방향을 바꾼 뒤 동일한 경로를 거꾸로 지나는 장면은 경로 정보가 있을 때만 읽힌다.
- **시각 계약:** `prepare` 갈림길에서 잘못된 흔적을 확인하고 뒤쪽의 이전 표식을 봄 -> `act` 몸을 돌려 왔던 발자국 방향으로 보폭을 전환 -> `hold` 같은 표식 위를 반대 방향으로 통과하는 순간 유지 -> `recover` 올바른 갈림길에 도달해 정지/새 방향 준비.
- **혼동/부정 cue:** 단순 `turn`, 아무 표식 없는 뒤로 걷기, `retreat`처럼 위협에서 벗어나는 후퇴, 같은 화면에서 방향만 바꾸고 경로를 되짚지 않는 모션을 금지한다.
- **우선도:** **scene-only**. 캐릭터 시트보다 발자국·지도·갈림길의 상태 변화로 학습하는 편이 안전하다.

### 11. 막힌 곳을 피해 우회하다 — `detour`

- **의미/근거:** [Cambridge Dictionary의 detour](https://dictionary.cambridge.org/dictionary/english/detour)는 문제를 피하려고 목적지까지의 더 길거나 덜 직접적인 다른 경로를 택하는 뜻이다.
- **동화 문장:** “The child takes a detour around the fallen stones to reach the cave.” (아이가 동굴에 가려고 무너진 돌을 피해 우회한다.)
- **분류:** `environment-bound`. 막힌 본길과 대체 경로가 동시에 보이는 장면이 필요하다.
- **한 에셋으로 보이는 이유:** 길이 두 갈래로 갈리고 한쪽은 돌무더기로 막혀 있어 다른 쪽으로 이동하는 선택을 보여 줄 수 있다. 인물만 보면 일반 걷기다.
- **시각 계약:** `prepare` 막힌 본길과 옆의 대체 길을 비교 -> `act` 몸을 돌려 옆길로 분기하고 장애물을 비켜 감 -> `hold` 본길과 평행한 우회 경로에 들어선 상태를 잠시 보여 줌 -> `recover` 장애물을 지나 목표 방향으로 다시 정렬.
- **혼동/부정 cue:** 갈림길·장애물 없이 옆으로 걷기, `backtrack`처럼 왔던 길로 되돌아가기, `escape`처럼 위험에서 달아나기, `walk`와 동일한 직선 경로를 금지한다.
- **우선도:** **text-only/scene-only**. 작은 시트 하나로 표현하지 말고 지도·경로 그래프나 장면 이벤트로 저장하는 편이 낫다.

### 12. 위협을 피해 물러서다 — `retreat`

- **의미/근거:** [Oxford Learner's Dictionaries의 retreat](https://www.oxfordlearnersdictionaries.com/definition/english/retreat_2)는 위험이나 패배 때문에 장소 또는 적에게서 멀어지는 동작으로 설명한다.
- **동화 문장:** “The child retreats from the cliff edge when the stones begin to fall.” (돌이 떨어지기 시작하자 아이가 절벽 끝에서 물러난다.)
- **분류:** `target-bound`. 떨어지는 돌, 괴물, 불길, 절벽 끝처럼 화면에 보이는 위협/위험 표적이 필수다.
- **한 에셋으로 보이는 이유:** 위협을 바라본 채 몸을 뒤로 빼고 안전선까지 이동하는 방향, 시선, 거리 변화가 함께 있으면 단순 후진 보행과 달라진다.
- **시각 계약:** `prepare` 위협과 안전한 뒤쪽 공간을 확인하며 발을 고정 -> `act` 시선을 위협에 둔 채 몸통을 뒤로 기울이고 짧은 후퇴 보폭 -> `hold` 위험선에서 한 발을 빼고 안전 거리로 이동하는 순간 유지 -> `recover` 안전한 지점에서 몸을 세우고 위협을 계속 확인.
- **혼동/부정 cue:** 위협 없는 `walk`, `escape`처럼 전력 질주, `stagger`처럼 균형 상실, `backtrack`처럼 경로 표식을 따라 되돌아가는 행동을 금지한다.
- **우선도:** **text-only/scene-only**. 상대/위협 반응이 없는 단독 모션은 의미를 보장하지 못한다.

## Top 6 권장

1. **`cross_bridge` — next asset:** British Council의 어린이 보물찾기 경로와 직접 맞고, 다리의 앞·중앙·반대편 결과가 `walk`와 다르게 보인다.
2. **`squeeze_through` — next asset:** 비밀 통로·폐허 벽의 좁은 틈이라는 동화 장면이 풍부하고, 어깨 회전과 양쪽 벽 접점이 단일 cycle을 만든다.
3. **`duck_under` — next asset:** 성문 들보·숲의 쓰러진 나무·폐허 잔해에 재사용할 수 있으며 `crouch`와 높이 변화로 분리된다.
4. **`vault` — later asset:** 손을 짚는 장애물 접점이 `jump`와 명확히 다르지만 착지 안전성과 환경 제작 비용 때문에 한 단계 늦춘다.
5. **`wade` — later asset:** 물리적 저항과 수면선이 `walk`·`swim`을 구분하지만 물 환경과 효과가 필요하다.
6. **`row` — later asset:** 노·배·수면의 인과가 가장 명확한 prop-bound 동작이지만 캐릭터 시트만으로는 완성되지 않는다.

`emerge`는 비밀 통로의 장면 전환으로는 유용하지만 `enter`/`escape`와 방향·가림 연출을 함께 검사해야 한다. `board`, `disembark`는 항구·강·비행선 이야기의 장면 어휘로 보존하되, 탈것별 별도 자산이 생길 때까지 공통 canonical action으로 확정하지 않는다. `backtrack`, `detour`, `retreat`는 경로·표적 메타데이터가 없으면 기존 이동 동작과 구분되지 않으므로 text-only/scene-only로 남긴다.

## 탈락시킨 관련 후보

- `guide`/`lead`: 파트너와 경로가 필요하지만 `follow`와 `point`의 조합으로 읽혀 별도 단일 동작의 판독성이 낮다. 파트너-bound 신규 후보로 추천하지 않는다.
- `pass_through`/`go_through`: 동굴을 통과한다는 문장 빈도는 높지만, 입구·출구가 화면에 없으면 `enter` 또는 `walk`와 중복된다. `squeeze_through`처럼 좁은 틈이라는 시각 제약이 있을 때만 보존한다.
- `leap_across_gap`: 절벽 사이의 틈을 넘는 좁은 의미는 강하지만 Round 3의 `jump`/“뛰어넘다”와 겹친다. 손 접점이 있으면 `vault`, 두 발 도약만 있으면 기존 키로 처리한다.
- `sneak`: 성·숲에 자연스럽지만 보폭과 속도의 수식어에 가까워 기본 `walk`와 한 장면 분리가 어렵다.
- `rappel`: 절벽·성벽에서 인상적이지만 로프·하네스·고정점이 필수이고 어린이용 일반 동화 어휘라기보다 전문 장비 동작이다.

## 방법의 한계

- 사전은 뜻과 용례의 근거이지, 한국어 어린이 동화 전체에서의 빈도 검증은 아니다. British Council 자료는 대표적인 교육용 보물찾기 사례이지 말뭉치 통계가 아니다.
- `cross_bridge`, `squeeze_through`, `duck_under`는 사전 표제어가 아니라 이번 시각 학습용으로 제안한 정규화 key다. 사전 근거는 각각 `cross`, `squeeze`, `duck`의 좁힌 의미에 해당한다.
- `generated_round3`와 기존 보고서의 메타데이터·파일명은 확인했지만 새 후보의 이미지/영상은 생성하거나 시각 제작 검증하지 않았다. 따라서 “next asset”은 구현 승인이라기보다 다음 에셋 실험 우선순위다.
- 환경-bound/prop-bound 후보는 인물만 투명 배경으로 잘라 학습하면 의미가 소실된다. 최종 채택 전에는 기준물의 위치, 그림자, 접점, 경로 결과를 포함한 합성 샘플을 별도로 검수해야 한다.

## 참고 자료

- [Cambridge Learner's Dictionary: cross](https://dictionary.cambridge.org/dictionary/learner-english/cross)
- [Cambridge Dictionary: bridge](https://dictionary.cambridge.org/dictionary/english/bridge)
- [Oxford Learner's Dictionaries: wade](https://www.oxfordlearnersdictionaries.com/definition/english/wade)
- [Merriam-Webster: squeeze](https://www.merriam-webster.com/dictionary/squeeze)
- [Merriam-Webster: duck](https://www.merriam-webster.com/dictionary/duck)
- [Merriam-Webster: vault](https://www.merriam-webster.com/dictionary/vault)
- [Cambridge Dictionary: row](https://dictionary.cambridge.org/dictionary/english/row)
- [Cambridge Dictionary: board](https://dictionary.cambridge.org/dictionary/english/board)
- [Oxford Learner's Dictionaries: disembark](https://www.oxfordlearnersdictionaries.com/definition/english/disembark)
- [Oxford Learner's Dictionaries: emerge](https://www.oxfordlearnersdictionaries.com/definition/english/emerge)
- [Cambridge Dictionary: backtrack](https://dictionary.cambridge.org/dictionary/english/backtrack)
- [Cambridge Dictionary: detour](https://dictionary.cambridge.org/dictionary/english/detour)
- [Oxford Learner's Dictionaries: retreat](https://www.oxfordlearnersdictionaries.com/definition/english/retreat_2)
- [British Council LearnEnglish Kids: The treasure map](https://learnenglishkids.britishcouncil.org/listen-watch/short-stories/treasure-map)
- [British Council LearnEnglish Kids: The treasure map answers PDF](https://learnenglishkids.britishcouncil.org/sites/kids/files/attachment/stories-the-treasure-map-worksheet-answers-final-2012-12-04.pdf)
