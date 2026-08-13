# Round 5 Word Research Red-Team

## Selection Gate

새 단어는 다음 조건을 통과해야 에셋 제작으로 이동한다.

1. 기존 동작을 제거해도 핵심 실루엣이 남아야 한다.
2. 손-소품, 발-지면, 손-손, 손-입 접촉점이 주요 프레임에서 유지되어야 한다.
3. `prepare -> act -> hold -> recover`의 8초 구조가 있어야 한다.
4. 파티클이나 소리 없이도 동작이 읽혀야 한다.
5. 목표물, 도착점, 결과 상태가 화면에 남아야 한다.

## Duplicates Removed

- `shake_hands`: existing `social_rescue` asset
- `hesitate`: existing `reactions_observation` asset

## Recommended First Batch

`plant_flag`, `put_on_crown`, `point_out`, `touch_probe`, `stack_stones`

이 다섯 개는 단독 캐릭터로 제작할 수 있고, 결과 상태가 남아 관객이 행동을 판독하기 쉽다. 첫 에셋 제작에서는 큰 소품과 명확한 접촉점을 우선 사용한다.

## Deferred

- `feed_dragon`: 두 개체의 입·손·먹이·시선 정렬 위험이 높다.
- `sprinkle_fairy_dust`: 파티클 없이는 `magic`과 분리하기 어렵다.
- `look_into_mirror`: 반사 이미지 동기화가 필요한 장면 합성 동작이다.
- `tie_string`: 매듭이 작고 손 접촉이 가려지기 쉬워 중경 구도 검증이 필요하다.
- `dive`: 수면과 수중 깊이 연속성이 확보된 뒤 제작한다.

## Next Implementation Order

1. DB의 `fit_vocabulary`/시각 어휘와 중복 확인
2. 1차 5개 동작의 소품·배경 앵커 설계
3. 선택 캐릭터 2종으로 모션 시트 생성
4. 8초 MP4 렌더링 및 무음 판독성 검수
5. 통과한 단어만 vocabulary seed와 Flutter 선택지에 연결
