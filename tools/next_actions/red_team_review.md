# Red-Team Review: male_01 Action Preview Set

- 검수일: 2026-08-10 (KST)
- 역할: 다섯 번째 검수자, 레드팀 전담
- 범위: 지정된 `output\video_previews` 산출물과 `tools\next_actions\render_*.py`
- 제한: 공용 provider, asset, 기존 구현 파일은 수정하지 않음. 새 리뷰 파일만 작성함.

## 최종 판정 요약

| 수용 순서 | 동작 | 행동 판독성 | 캐릭터 동일성 | 접지 | 프레임/배경 안정성 | 실제 앱 판정 |
|---:|---|---|---|---|---|---|
| 1 | sit | 낮아지는 무릎·몸통, 착석 후 hold가 명확함 | 동일한 `male_01` | 고정 bottom alignment로 양호 | 배경 기준점 고정, 샘플상 큰 깜빡임 없음 | **완성** |
| 2 | stand | 착석 hold에서 몸통 상승·다리 신전·직립 hold가 명확함 | 동일한 `male_01` | 고정 bottom alignment로 양호 | 배경 기준점 고정, 샘플상 큰 깜빡임 없음 | **완성** |
| 3 | stop | 달리기와 감속은 읽히나 마지막 정지가 달리기 포즈임 | 동일한 `male_01`, 우향 연속성 양호 | 이동 중 기준선은 있으나 최종 발 자세가 부적합 | 배경은 고정, 별도 고정 표식이 화면에 남음 | **프로토타입** |
| 4 | wave | 손을 들고 내리는 이진 동작은 읽히나 실제 waving arc는 없음 | 동일한 `male_01` | 발과 몸통은 안정적 | 배경 고정, 셀 교체 프레임에 하드 컷 | **프로토타입** |
| 5 | turn | 앞-3/4-뒤 방향 변화는 읽히나 회전 과정이 아니라 포즈 교체임 | 의상·색상은 동일하나 rear asset이 달리기 포즈 | 후면에서 한 발이 들려 접지 실패 | 배경·중앙 가이드는 고정되지만 debug overlay가 납품 영상에 포함됨 | **거절** |

`완성`은 현재 영상 묶음에서 실제 앱의 동작 후보로 넣을 수 있다는 뜻이다. 단, sit/stand는 다른 preview와 달리 `768x384@24fps`이므로 앱이 고정 `960x480@30fps` 계약을 요구하는 경우에는 배포 전 인코딩 규격을 통일해야 한다.

## 동작별 엄격 검수

### 1. sit

- contact sheet의 0.0~4.5초 샘플에서 직립 시작, 무릎 굽힘, 낮은 자세, 착석, 착석 hold가 순서대로 보인다. 손은 몸을 낮추는 동안 앞으로 내려가고, 발/무릎/몸통의 높이 변화가 함께 있어 단순 위치 이동으로 보이지 않는다.
- `render_sit_stand_quality.py:121-132`는 sit 셀 0~4를 순차 keyframe으로 쓰고 마지막 셀을 1.0까지 hold한다. 짧은 전환 구간에는 `:89-116`의 optical-flow 보간이 사용된다. contact sheet에서는 큰 이중 윤곽이나 배경 흔들림이 확인되지 않았다.
- 캐릭터의 얼굴, 파란 튜닉, 빨간 망토, 부츠가 reference 및 stand와 일관된다. `:175-199`의 단일 배경과 고정 `center_x`, `ground_y` 때문에 수직 기준이 안정적이다.
- 판정: **완성**. 다만 768x384, 24fps 메타데이터는 아래 확인 결과처럼 다른 품질 preview의 960x480, 30fps와 다르므로 앱의 해상도 계약만 확인해야 한다.

### 2. stand

- contact sheet의 0.0~0.5초 seated hold 이후 1.1초부터 몸통이 올라가고 다리가 펴지며, 1.7초 이후 직립 hold가 유지된다. 손/발/몸통의 변화를 함께 읽을 수 있다.
- `render_sit_stand_quality.py:133-144`는 `sit[4]`에서 `stand[0,1,3,5,7]`로 넘어가며 마지막 직립 포즈를 hold한다. sit와 동일한 optical-flow 전환, 단일 fitted background, 고정 root를 사용한다.
- contact sheet에서 배경의 성/나무/길 기준점은 고정되고 캐릭터만 변화한다. 동일 캐릭터와 동일 바닥선으로 sit과 연속 사용하기 좋다.
- 판정: **완성**. sit과 같은 `768x384@24fps` 규격 확인은 필요하지만, 시각적 동작 품질 자체는 앱 후보로 수용한다.

### 3. stop

- contact sheet의 `run -> brake -> last plant -> idle hold` 구조는 시간 흐름과 이동 방향이 명확하다. 손은 달리기 팔 동작을 유지하고, 발은 감속 중 보폭이 줄어드는 것으로 읽히지만, 몸통은 끝까지 전방 러닝 실루엣이다.
- 가장 큰 결함은 `render_stop_quality.py:217-235`에서 stand 셀을 로드하고도 실제 프레임에는 `sprite_for_time(run_cells, second)`만 전달한다는 점이다. `:153-155`의 마지막 hold도 run cell 6을 고정한다. 따라서 `idle hold`가 직립 정지가 아니라 한 발이 들린 러닝 포즈로 보인다.
- `:179-186`의 `FINAL_X` 고정 타원 표식이 달리는 동안 캐릭터 앞에 계속 보인다. 이는 접지 검사용 표식으로는 유용하지만 실제 앱 영상에 포함되면 장면의 자연스러운 배경 기준점이 아니라 인공 debug marker가 된다.
- `GROUND_Y`는 고정되어 있고 배경도 고정되어 카메라 안정성은 좋다. 그러나 포즈의 실제 발바닥이 아닌 alpha bbox 하단을 `:84-101`, `:205-211`에서 ground에 맞추므로 달리기 셀별 발 높이 차이가 접지 오차로 남는다.
- 판정: **프로토타입**. 감속 timing과 이동은 검토용으로 수용 가능하지만, 최종 앱에는 넣지 않는다.

### 4. wave

- contact sheet에서 손을 든 상태와 내린 상태가 반복되어 “손을 든다”는 의미는 전달된다. 발, 몸통, 배경은 고정되어 캐릭터 동일성과 지면 접지는 양호하다.
- 하지만 `render_wave_quality.py:82-93`은 8칸 action sheet에서 cell `0,1` 두 장만 추출한다. `:58-75`의 timeline은 이 두 이미지를 1.6초 주기로 반복할 뿐이며, 손목·팔꿈치·어깨의 중간 궤적이나 반복 방향을 생성하지 않는다.
- 실제 MP4를 전 프레임 비교한 결과, 유의미한 전환은 9, 24, 27, 40, 57, 72, 75, 88, 105, 120, 123, 136, 153, 168, 171, 184번 프레임에서만 나타났고, 전환 평균 차이가 약 5.1이었다. 즉 30fps 영상 안에서 대부분 프레임은 같은 셀을 복제하고 셀 경계에서 hard swap한다.
- `:96-120`의 고정 `center_x=570`, `ground_y=446`와 shadow로 접지는 안정적이며, `:78-79`의 고정 resize로 배경 기준점도 움직이지 않는다. 안정성이 행동 자연스러움을 보완하지는 못한다.
- 판정: **프로토타입**. UI 데모의 binary wave로는 사용할 수 있지만, 실제 캐릭터 동작으로는 최종 수용하지 않는다.

### 5. turn

- contact sheet에서 `FRONT HOLD -> PIVOT -> PELVIS + TORSO -> GAZE LEADS -> BACK HOLD` 라벨과 front/3-quarter/rear 방향은 쉽게 읽힌다. 그러나 이것은 회전 시트의 연속된 각도 변화가 아니라 front, three-quarter, rear 이미지를 hold/blend로 교체한 것이다.
- 전용 회전 시트 부재는 코드와 report 양쪽에서 확인된다. `render_turn_quality.py:177-213`에서 `dedicated_turn_sheet=None`, `dedicated_turn_sheet_found=False`, `rotation_asset_status=partial_not_sufficient_for_final_turn`으로 기록하고, assets 검색에서도 turn/rotate/pivot 이름의 motion sheet가 발견되지 않았다.
- rear anchor는 `male_01_target_journey_sheet_v4.png`의 running pose다. report와 `render_turn_quality.py:208-210`이 명시하듯 후면에서 한 발이 들린다. contact sheet의 4.8~7.0초 rear hold에서도 두 발로 선 turn-in-place가 아니라 달리는 중간 프레임으로 보인다.
- `render_turn_quality.py:115-131`의 상단 라벨, 중앙 수직선, 바닥선, 좌우 표식이 MP4 모든 프레임에 그려진다. 카메라와 기준점은 안정적이지만 이 overlay는 앱 납품 영상으로는 제거되어야 한다.
- 판정: **거절**. 현재 결과는 자산 부족을 보여주는 프로토타입 증거물로만 보관한다. 최종 turn으로 승격하지 않는다.

## MP4 메타데이터 검증

`imageio.v2` reader의 `get_meta_data()`와 `count_frames()`로 실제 파일을 읽었다. 모든 파일은 decode 가능했고 H.264, progressive `yuv420p`였다.

| 파일 | 해상도 | fps | 프레임 수 | 측정 재생시간 |
|---|---:|---:|---:|---:|
| `output\video_previews\male_01_wave_quality_v1.mp4` | 960x480 | 30 | 192 | 6.4s |
| `output\video_previews\male_01_stop_quality_v1.mp4` | 960x480 | 30 | 240 | 8.0s |
| `output\video_previews\male_01_sit_quality_v2.mp4` | 768x384 | 24 | 108 | 4.5s |
| `output\video_previews\male_01_stand_quality_v2.mp4` | 768x384 | 24 | 108 | 4.5s |
| `output\video_previews\male_01_turn_quality_v1.mp4` | 960x480 | 30 | 210 | 7.0s |

Contact sheet 자체도 직접 열람했다. 확인한 PNG 경로와 크기는 다음과 같다.

- `output\video_previews\male_01_wave_quality_v1_contact.png` — 960x432
- `output\video_previews\male_01_stop_quality_v1_contact.png` — 1280x776
- `output\video_previews\male_01_sit_stand_quality_v2_contact.png` — 768x986
- `output\video_previews\male_01_turn_quality_v1_contact.png` — 960x600

## 반드시 필요한 수정 (3개 이내)

1. **turn 자산과 납품 프레임을 다시 만든다.** 전용 turn-in-place sheet를 front/side/three-quarter/back의 planted-foot 단계로 추가하고, running rear 셀을 제거한다. 최종 MP4에서는 상단 phase/debug guide도 제거한다.
2. **stop의 마지막 포즈를 authored stand/stop 포즈로 교체한다.** run cell 6 hold를 없애고 양발이 실제 지면에 닿는 직립 또는 명확한 braking settle을 사용한다. 고정 `FINAL_X` debug marker도 clean delivery에서 제거한다.
3. **wave를 두 셀 반복이 아닌 연속 arc로 만든다.** action sheet의 중간 wave 셀을 사용하거나 보간해 팔/손목 이동을 만들고, cell 경계 hard swap을 없앤다.

## 실행 명령과 확인 경로

실행한 주요 명령:

```powershell
Get-ChildItem -Path output\video_previews -File | Select-Object Name,Length,LastWriteTime | Sort-Object Name
Get-ChildItem -Path tools\next_actions -Filter 'render_*.py' -File | Select-Object FullName,Length,LastWriteTime | Sort-Object Name
Get-Content -Raw output\video_previews\male_01_turn_quality_v1_report.json
imageio.v2 reader의 get_meta_data(), count_frames()를 호출하는 read-only Python 명령
wave MP4 전 프레임의 mean absolute difference를 계산하는 read-only Python 명령
PIL Image.open으로 contact PNG 크기를 확인하는 read-only Python 명령
rg -n "WAVE_CYCLE_SECONDS|_select_wave_cell|..." tools\next_actions\render_*.py output\video_previews\male_01_turn_quality_v1_report.json
Get-ChildItem assets\characters\motion_sheets -File | Where-Object { $_.Name -match '(?i)turn|rotate|pivot' }
```

직접 시각 확인한 핵심 경로:

- `D:\capstone\soft_capston-main\output\video_previews\male_01_wave_quality_v1_contact.png`
- `D:\capstone\soft_capston-main\output\video_previews\male_01_stop_quality_v1_contact.png`
- `D:\capstone\soft_capston-main\output\video_previews\male_01_sit_stand_quality_v2_contact.png`
- `D:\capstone\soft_capston-main\output\video_previews\male_01_turn_quality_v1_contact.png`
- `D:\capstone\soft_capston-main\output\video_previews\male_01_turn_quality_v1_report.json`
- `D:\capstone\soft_capston-main\tools\next_actions\render_wave_quality.py`
- `D:\capstone\soft_capston-main\tools\next_actions\render_stop_quality.py`
- `D:\capstone\soft_capston-main\tools\next_actions\render_sit_stand_quality.py`
- `D:\capstone\soft_capston-main\tools\next_actions\render_turn_quality.py`
