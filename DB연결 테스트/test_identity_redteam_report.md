# Character Identity Red-Team Report

## Scope

The new integration test follows the production flow:

`save_story_characters` -> `load_story_cast_member` -> `push_scene` (choice and scene contract) -> `create_scene_media_job` (image/video queue request), plus the synchronous `generate_media` boundary.

It uses in-memory fakes for the Mongo collections and mocks only the external media generation call. No application source files were changed.

## Covered attacks

- Character rename between scenes: the persisted `character_key` remains the assertion target.
- Choice/story text mentioning another cast member: the selected primary identity is checked against the original key.
- Previous scene contract without `character_key`: checked at the media boundary.
- Injected key from another profile: the story-cast membership check must reject it.
- Legacy story without `story_cast`: migration must create and persist a real profile key.
- Image/video request: queued request and synchronous generation both carry the same key; the scene is marked pending for the queued request.

## Execution result

Command:

`python -m unittest discover -s "DB연결 테스트" -p "test_choice_media_identity_flow.py" -v`

Result: **8 tests run, 8 passed.**

The previously reproduced risk is fixed. `create_scene_media_job()` now rejects a story media request that omits the story's locked `character_key`, and rejects keys that are not members of the saved story cast. The explicit request key is also selected before text-based cast matching, so a companion name in a choice sentence cannot silently replace the selected hero.

## Remaining limitations

- These tests do not call a live MongoDB instance or an actual HTTP client, so middleware/auth header parsing remains outside this test's boundary.
- Provider output is mocked; image/video prompt construction and provider-side identity drift require separate provider contract tests.
- `push_scene()` currently stores the supplied contract but does not itself derive or validate `character_key` from the story cast. The test protects the caller contract, not automatic repair of omitted fields.
- The test checks the media request payload and pending scene linkage, not worker completion synchronization or final file metadata.
