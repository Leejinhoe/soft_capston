# Treasure Story Action Vocabulary

조사일: 2026-08-10

이 문서는 보물상자, 열쇠, 비밀문, 보물찾기 장면에 사용할 동작 후보를 정리한
시각 어휘 학습 자료다. 기존 `generated_round3` 동작과 백엔드 분류 코드는
변경하지 않았다.

## 조사 기준

- `open`은 닫힌 대상의 상태를 바꾸고 안쪽을 드러내는 동작으로 정의한다.
- `unlock`은 열쇠나 코드로 잠금 상태를 해제하는 동작으로 정의한다.
- `grasp`는 손으로 물체를 단단히 잡는 동작이며, `pick up`과 구분한다.
- 보물찾기 장면은 숨겨진 단서, 단서 추적, 탐색, 발견의 순서가 있어야 한다.
- 인물만 잘라서 표현하면 의미가 약해지는 동작은 소품·배경 조건부로 분류한다.

## 1차 에셋 후보

| 우선순위 | 한국어 | 키 | 분류 | 필수 조건 | 8포즈 계약 |
|---|---|---|---|---|---|
| 1 | 보물상자를 열다 | `open_chest` | 소품 조건부 | 상자, 뚜껑 또는 걸쇠 | 접근 -> 손이 걸쇠/뚜껑에 닿음 -> 뚜껑을 들어 올림 -> 열린 상자와 내용물 hold -> 손을 뗌 |
| 2 | 잠금을 풀다 | `unlock` | 소품 조건부 | 열쇠, 자물쇠, 열쇠구멍 | 자물쇠 확인 -> 열쇠 삽입 -> 열쇠 회전 -> 잠금 해제 hold -> 문/상자로 전환 |
| 3 | 줍다 | `pick_up` | 소품 조건부 | 바닥의 열쇠·보물·단서 | 발견 -> 몸을 낮춤 -> 손과 물체 접촉 -> 물체가 바닥에서 떨어짐 -> 손 안의 물체 확인 -> 회복 |
| 4 | 들어 올리다 | `lift` | 소품 조건부 | 들어 올릴 보물·상자·돌 | 양손 준비 -> 잡기 -> 바닥에서 들어 올림 -> 무게를 버티며 hold -> 내려놓거나 확인 |
| 5 | 덮개를 걷어 드러내다 | `uncover` | 소품 조건부 | 천, 상자 뚜껑, 가림막 | 가려진 대상을 봄 -> 덮개 접촉 -> 옆으로 걷음 -> 숨은 대상 reveal hold -> 손 회복 |
| 6 | 파다 | `dig` | 환경·도구 조건부 | 흙/모래와 손 또는 삽 | 지점 확인 -> 무릎을 낮춤 -> 반복해서 파기 -> 흙더미와 구멍 hold -> 물체 발견 -> 회복 |

## 2차 후보

| 한국어 | 키 | 조건 | 보류 이유 |
|---|---|---|---|
| 당기다 | `pull` | 밧줄, 문, 상자 손잡이 | 대상이 실제로 움직이지 않으면 기대기와 구분되지 않음 |
| 밀다 | `push` | 돌문, 바위, 상자 | 대상 이동과 손 접점이 없으면 힘주는 포즈로 오인됨 |
| 끼우다 | `insert` | 열쇠와 열쇠구멍, 보석과 홈 | `unlock`의 세부 단계로 먼저 사용 |
| 열쇠를 돌리다 | `turn_key` | 열쇠와 자물쇠 | `unlock` 내부 계약으로 우선 처리 |
| 들어가다 | `enter` | 열린 문·동굴·성 | 인물 에셋보다 배경과 경로 에셋이 먼저 필요 |
| 탈출하다 | `escape` | 출구·추격 위험·장애물 | 이야기 맥락과 경로가 없으면 달리기와 구분되지 않음 |
| 따라가다 | `follow` | 앞선 인물·빛·발자국 | 상대 또는 명확한 유도 대상이 필요 |
| 쫓아가다 | `chase` | 도망가는 대상 | 2인 장면과 상대 이동이 필요 |
| 구하다 | `rescue` | 위험에 처한 대상 | 단독 인물 모션이 아니라 관계 장면으로 분리 |

## 기존 단어와의 경계

- `open_chest`는 일반적인 손동작이 아니라 **뚜껑과 내용물이 함께 변하는 상호작용**이다.
- `unlock`은 `open_chest`보다 앞선 단계다. 열쇠 삽입과 회전이 보이지 않으면 `open`으로 낮추지 않는다.
- `pick_up`은 `crouch`나 `kneel`이 아니다. 물체가 바닥에서 손으로 이동해야 한다.
- `uncover`는 `hide`가 아니다. 인물이 숨는 것이 아니라 가림막을 치워 대상을 보여주는 동작이다.
- `examine`와 `search`는 기존 `investigate`와 겹치므로 별도 기본 동작으로 추가하지 않고, 소품·카메라 조건이 있는 변형으로 둔다.
- `enter`, `escape`, `follow`, `chase`, `rescue`는 캐릭터만의 단독 모션보다 경로·상대·위험 요소를 함께 설계해야 한다.

## 다음 학습 순서

1. `open_chest`와 `unlock`을 같은 보물상자 장면에서 연속 동작으로 만든다.
2. `pick_up`과 `lift`를 바닥 접점·손 접점이 보이는 중간 샷으로 만든다.
3. `uncover`와 `dig`를 보물찾기 배경에 붙여 조건부 에셋으로 만든다.
4. 각 에셋은 `prepare -> act -> hold -> recover` 단계와 소품 상태 변화를 함께 검수한다.

## 참고 자료

- [Merriam-Webster: open](https://www.merriam-webster.com/dictionary/open)
- [Oxford Learner's Dictionaries: unlock](https://www.oxfordlearnersdictionaries.com/us/definition/english/unlock)
- [Cambridge Dictionary: grasp](https://dictionary.cambridge.org/us/dictionary/english/grasp)
- [PBS Kids: treasure hunt vocabulary activity](https://www.pbs.org/parents/crafts-and-experiments/exploring-space-by-hunting-for-treasure)
- [Education Quizzes: explore and action verbs](https://www.educationquizzes.com/ks1/vocabulary-age-6/verbs-18-age-6-including-expand-and-explore/)
