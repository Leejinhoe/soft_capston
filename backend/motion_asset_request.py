"""Identify motion fallbacks that need a character-specific asset."""


def missing_motion_asset_request(*, character_key, identity, motion_plan, parameters, story_text=''):
    action = str((motion_plan or {}).get('action') or '').strip()
    key = str(character_key or '').strip()
    tier = str((parameters or {}).get('motion_asset_tier') or '').strip()
    text = str(story_text or '').lower()
    telescope_action = (('망원경' in text or 'telescope' in text) and any(
        word in text for word in ('살펴', '바라', '들여다', '관찰', 'look', 'peer', 'gaze')
    ))
    if not key or (not telescope_action and (
        action in {'', 'idle'} or tier not in {'reference_transform', 'camera_only'}
    )):
        return None
    return {
        'status': 'needs_asset',
        'character_key': key,
        'action': 'look_through_telescope' if telescope_action else action,
        'source_action': ('look through a handheld telescope' if telescope_action
                          else (motion_plan or {}).get('semantic_source_word')),
        'pace': (motion_plan or {}).get('pace'),
        'target': (motion_plan or {}).get('target'),
        'background_key': (motion_plan or {}).get('background_key'),
        'participant_count': (motion_plan or {}).get('participant_count'),
        'requires_partner': bool((motion_plan or {}).get('requires_partner')),
        'requires_object': telescope_action or bool((motion_plan or {}).get('requires_object')),
        'required_props': (['handheld telescope'] if telescope_action
                           else list((motion_plan or {}).get('required_props') or [])),
        'reference_asset_fingerprint': (identity or {}).get('asset_fingerprint'),
        'reference_asset_version': (identity or {}).get('asset_version'),
        'reason': 'no_character_specific_action_asset',
        'fallback_tier': tier,
    }
