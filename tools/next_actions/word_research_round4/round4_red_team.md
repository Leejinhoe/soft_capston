# Round 4 Red-Team Review: Fairy-Tale Learning Candidates

- Date: 2026-08-10 (KST)
- Scope: additional child-friendly English words that can occur in fairy tales
- Output policy: only this review and `round4_learning_candidates.json` are new; runtime, backend, database, existing reports, images, and videos were not changed.

## Audit Baseline

The existing merged vocabulary already covers `journey` (walk/run), `crawl`, `climb`, `investigate`, `jump`, `magic`, `stop`, `wave`, `hide`, `sit`, and `stand`. Round 3 also has generated cycles and previews for `salute`, `prone`, `stagger`, `wake`, `yawn`, and `sneeze`. Those meanings are duplicate territory, even when a new report phrases them differently.

The review also checked the four Round 4 reports, `treasure_story_words.md`, the three Round 3 reports, the generated motion-sheet folders, the Round 3 video previews, and `merged_visual_vocabulary.json`. Dictionary and child-story sanity checks used the source links preserved in the reports, including Cambridge, Oxford Learner's Dictionaries, Merriam-Webster, and British Council LearnEnglish Kids. A web check confirmed that `beckon` requires a visible receiver, `cower` combines fear with lowering/backward movement, `spot` means noticing a hard-to-see target, and the British Council treasure-map material explicitly uses crossing a bridge.

## Red-Team Gates

1. A broad existing action is not promoted just because a prop or adjective is added. A narrower key survives only when the prop, relationship, target, or environment changes the observable meaning and has a visible result.
2. A candidate fails as an asset when its meaning needs an absent prop, environment, partner, target, audio cue, or narrative backstory. It is then labelled `scene_only` or rejected.
3. Every kept candidate must support `prepare -> act -> hold -> recover`. The hold must preserve a state, contact, relationship, target response, or traversal threshold; a generic pose is insufficient.
4. Small-screen review must be possible without relying on sound. Face micro-actions, writing, liquid effects, and route intention are therefore down-ranked unless the scene supplies the missing evidence.

## Final Set

There are 18 candidates: 6 `next_asset`, 8 `later_asset`, and 4 `scene_only`.

| Priority | Key | Korean meaning | Category | Red-team pass condition |
|---|---|---|---|---|
| next_asset | `pull_lever` | 레버를 당겨 작동시키다 | prop-bound | Hand grips a visible lever; lever angle and linked device change. |
| next_asset | `turn_dial` | 다이얼을 돌려 맞추다 | prop-bound | A marked dial rotates to a visible target alignment. |
| next_asset | `place_gem` | 보석을 홈에 놓다 | prop-bound | Gem leaves the hand, seats in a visible socket, and remains there. |
| next_asset | `cross_bridge` | 다리를 건너다 | environment-bound | Bridge entrance, span, and opposite ground are all visible. |
| next_asset | `squeeze_through` | 좁은 틈을 비집고 지나가다 | environment-bound | Two boundaries compress the shoulders and a far-side exit is revealed. |
| next_asset | `duck_under` | 몸을 숙여 아래로 지나가다 | environment-bound | A low obstacle forces a height change while the character passes beneath it. |
| later_asset | `knock_on_door` | 문을 두드리다 | prop-bound | Repeated fist-to-door contact is followed by a waiting hold. |
| later_asset | `press_seal` | 봉인을 눌러 찍다 | prop-bound | A seal visibly contacts wax or a surface and leaves a mark. |
| later_asset | `light_lantern` | 등불에 불을 붙이다 | prop-bound | Flame attaches to the wick and the lantern becomes the light source. |
| later_asset | `wade` | 얕은 물을 헤치며 걷다 | environment-bound | Waterline, leg resistance, ripples, and dry-land recovery are visible. |
| later_asset | `row` | 노를 저어 배를 움직이다 | prop-bound | Hands, oar, water contact, and boat displacement remain causally linked. |
| later_asset | `shake_hands` | 악수하다 | partner-bound | Two visible characters make hand contact and perform a short shake. |
| later_asset | `beckon` | 손짓해 부르다 | target-bound | A visible receiver is addressed by inward repeated hand motion. |
| later_asset | `cower` | 웅크리며 겁내다 | target-bound | A visible threat causes lowering, backward movement, and protective arms. |
| scene_only | `meet` | 만나다 | partner-bound | Two roots must approach, share a location, face each other, and hold. |
| scene_only | `eavesdrop` | 몰래 엿듣다 | partner-bound | A private speaker, cover, listening position, and preferably audio/scene cue are present. |
| scene_only | `spot` | 숨은 것을 발견하다 | target-bound | A hidden target appears at a defined moment and the character switches from search to discovery. |
| scene_only | `hesitate` | 망설이다 | target-bound | A visible goal is approached but not completed; the hand withdraws without changing its state. |

No new unrestricted solo action survived the gates. Round 3's solo cycles are already implemented, and the remaining solo proposals (`cough`, `faint`, `flinch`, `freeze`, `meditate`, `cry`, `sing`, `whistle`, and similar) are either near-duplicates, states/emotions, or audio/face dependent.

## Category Separation

- `prop-bound`: `pull_lever`, `turn_dial`, `place_gem`, `knock_on_door`, `press_seal`, `light_lantern`, and `row` need an object whose state or position proves the action.
- `environment-bound`: `cross_bridge`, `squeeze_through`, `duck_under`, and `wade` need a traversable environmental boundary or medium.
- `partner-bound`: `shake_hands`, `meet`, and `eavesdrop` need another visible character; `eavesdrop` additionally needs a cover or private-space relation.
- `target-bound`: `beckon`, `cower`, `spot`, and `hesitate` need a visible receiver, threat, hidden object, or unfinished goal.
- `solo`: none in the final set. This is intentional: the apparent solo candidates were already implemented or did not pass silent visual distinction.
- `scene-only`: `meet`, `eavesdrop`, `spot`, and `hesitate` are useful story labels, but their decisive evidence belongs in a composite scene rather than a transparent character-only sheet.

## Narrow-Meaning Decisions

- `pull_lever` is not general `pull`: the hand-lever contact and linked state change are mandatory.
- `turn_dial` is not character `turn`: the marked dial rotates around its own axis and reaches an alignment.
- `place_gem` is not generic `place` or `insert`: the gem must leave the hand and seat in a visible socket.
- `cross_bridge` is not `journey`: the bridge span and opposite endpoint are the meaning-bearing environment.
- `squeeze_through` is not `crawl` or `hide`: the body compresses between two boundaries and exits on the far side.
- `duck_under` is not `crouch`: the low obstacle causes the height change and the character visibly travels beneath it.
- `beckon` is not `wave`: the inward hand path addresses a visible receiver and asks that receiver to approach.
- `cower` is not `crouch`: fear, a visible threat, and backward/protective movement are required.
- `spot` is not `investigate`: it is a one-time discovery transition with a specified hidden target, not continued scanning.
- `hesitate` is not `stop`: it is an incomplete approach to a visible goal followed by withdrawal, with no completed target state.

## Rejected Proposals

The list below records the strongest rejected or deferred proposals from all four reports. `duplicate_mapping` names the existing action or final narrow key that would absorb the proposal if its extra condition is missing.

| Key | Decision | Reason | Duplicate mapping |
|---|---|---|---|
| `walk`, `run`, `journey` | reject | Already represented by merged `journey`; speed or direction does not create a new visual contract. | `journey` |
| `jump`, `crouch`, `crawl`, `hide`, `investigate` | reject | Already implemented; several Round 4 proposals only restated their silhouettes. | same-named existing actions |
| `salute` | reject as new | Round 3 has a generated salute cycle; the old hand-to-forehead pose also conflicts with investigate. | `salute` / `investigate` |
| `prone`, `stagger`, `wake`, `yawn`, `sneeze` | reject as new | Generated Round 3 sheets and previews already cover these meanings. | same-named Round 3 action |
| `carry_treasure` | reject from final | Needs long prop continuity and screen travel; without both, it is `hold`, `lift`, `pick_up`, or `journey`. | `hold` / `journey` |
| `drop_clue` | reject from final | Tiny-object separation and landing are fragile at small scale; can read as `fall`, `throw`, or an object disappearing. | `fall` / `throw` |
| `stir_potion`, `pour_potion` | reject from final | Liquid continuity and vessel geometry dominate the meaning; reserve for a later effects experiment. | `magic` / `place` |
| `draw_sword` | reject from final | Weapon visibility, sheath occlusion, and safe recovery are more production-specific than the learning value justifies here. | `magic` / combat scene |
| `ring_bell` | reject from final | Silent video cannot rely on the bell sound, and rope/fixture variants resemble `pull_lever` or `wave`. | `pull_lever` / `wave` |
| `mark_map` | reject | The decisive change is a tiny written mark and readable map; it is text/scene content, not a robust motion sheet. | `read` / `investigate` |
| `stamp_seal` | reject | Same seal, surface, and mark evidence as `press_seal`; the difference is only pressure duration and lift timing. | `press_seal` |
| `vault` | reject from first batch | It can survive only with a hand-planted obstacle vault; otherwise it is an embellished `jump`, with higher landing risk. | `jump` |
| `backtrack`, `detour` | reject | Route history, markers, or a fork are required; the body motion alone is ordinary `journey`. | `journey` |
| `retreat` | reject | Without a visible threat it is backward `journey`; threat direction and narrative stakes belong in scene metadata. | `journey` |
| `emerge` | reject from asset batch | Lighting, occlusion, and camera reveal carry more meaning than the character cycle. | `enter` / scene reveal |
| `board`, `disembark` | reject from asset batch | Vehicle type, step height, and camera placement make a family of scene transitions rather than one stable action. | `climb` / `enter` / `journey` |
| `cough` | reject | Repeated torso contractions are too close to the implemented `sneeze` at low resolution without audio or face detail. | `sneeze` |
| `faint` | reject | Controlled collapse is unsafe and overlaps `fall_roll`/falling state. | `fall_roll` |
| `flinch`, `freeze` | reject | They need an initiating event and read as a short reaction or `stop`; no stable solo contract. | `stagger` / `stop` |
| `meditate`, `pray` | reject | Hand-together stillness is close to existing posture/magic and needs scene or belief context. | `sit` / `magic` |
| `cry`, `sing`, `whistle`, `shiver`, `blink` | reject | Emotion, audio, or face micro-change is decisive and cannot be trusted in a general character sheet. | emotion / conversation / scene track |
| `peek` | reject | Already reviewed; without a clear cover and target it collapses into `hide` or `investigate`. | `hide` / `investigate` |
| `listen`, `overhear`, `whisper_to_ear` | reject as independent motion | Sound, speaker, and relationship context dominate; `eavesdrop` is retained only as the narrower cover-plus-private-speaker scene label. | `investigate` / conversation track |
| `hold_hands` | reject | Partner contact is meaningful but overlaps existing `hug`/generic hold and needs continuous two-person hand tracking. | `hug` / interaction scene |
| `protect`, `catch`, `release`, `surrender` | reject from final | Each requires a moving target, threat, restraint, or authority relationship; scene composites should be built before any canonical motion. | target/interaction scene track |
| `gasp`, `wince`, `squint` | reject from final | Strong candidates for face-centered scenes, but too small or target-dependent for this batch. | reaction scene track |
| `shush` | reject | A listener, nearby sound/risk, and response are needed; a finger-to-lips pose alone is not enough. | conversation scene track |
| `argue`, `reconcile`, `apologize` | reject | Their meaning is a before/after relationship event, not a stable single motion. `apologize` is especially close to `bow`. | `bow` / scene narrative label |

## Sources

The candidate JSON preserves per-entry links. Key sanity-check sources include:

- [British Council LearnEnglish Kids: The treasure map](https://learnenglishkids.britishcouncil.org/listen-watch/short-stories/treasure-map)
- [British Council treasure-map worksheet PDF](https://learnenglishkids.britishcouncil.org/sites/kids/files/attachment/short-stories-the-treasure-map-worksheet.pdf)
- [Cambridge Learner's Dictionary: beckon](https://dictionary.cambridge.org/dictionary/learner-english/beckon)
- [Cambridge Dictionary: spot](https://dictionary.cambridge.org/us/dictionary/english/spot)
- [Oxford Learner's Dictionaries: cower](https://www.oxfordlearnersdictionaries.com/us/definition/english/cower)
- [Merriam-Webster: squeeze](https://www.merriam-webster.com/dictionary/squeeze)
- [Merriam-Webster: duck](https://www.merriam-webster.com/dictionary/duck)
