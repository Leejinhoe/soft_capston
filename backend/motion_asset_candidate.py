"""Optional reference-conditioned motion-sheet candidates, never auto-published."""
import io
import os

from PIL import Image


def validate_motion_sheet(data):
    if not data or len(data) > 15_000_000:
        raise ValueError('Candidate image is empty or exceeds the size limit.')
    with Image.open(io.BytesIO(data)) as image:
        if image.format != 'PNG' or image.mode != 'RGBA':
            raise ValueError('Candidate must be a transparent PNG.')
        width, height = image.size
        if width < 512 or height < 256 or width * height > 16_000_000 or width % 4 or height % 2:
            raise ValueError('Candidate must have an evenly divisible 4x2 grid.')
        alpha = image.getchannel('A')
        if alpha.getextrema()[0] > 8:
            raise ValueError('Candidate has no transparent background.')
        cell_w, cell_h = width // 4, height // 2
        for index in range(8):
            x, y = (index % 4) * cell_w, (index // 4) * cell_h
            cell = alpha.crop((x, y, x + cell_w, y + cell_h))
            bbox = cell.point(lambda value: 255 if value > 32 else 0).getbbox()
            if not bbox:
                raise ValueError(f'Candidate frame {index + 1} is empty.')
            if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == cell_w or bbox[3] == cell_h:
                raise ValueError(f'Candidate frame {index + 1} touches a cell boundary.')
    return {'width': width, 'height': height, 'columns': 4, 'rows': 2}


def candidate_prompt(request):
    action = str(request.get('source_action') or request.get('action') or '').strip()
    if not action:
        raise ValueError('An identified action is required.')
    props = ', '.join(str(item)[:60] for item in (request.get('required_props') or [])[:5])
    return (
        'Create a transparent PNG 4 by 2 animation sprite sheet with eight '
        'sequential full-body frames of the exact reference character performing '
        f'this action: {action[:120]}. Preserve face, hair, clothes and proportions. '
        'Keep each pose entirely inside its own cell with transparent margins. '
        'No text, scenery, extra characters or grid lines. '
        + (f'Keep the required object visible and consistent: {props}.' if props else '')
    )


async def generate_candidate(request, reference_bytes, generate_image):
    if not reference_bytes or len(reference_bytes) > 15_000_000:
        raise ValueError('A valid character reference image is required.')
    if request.get('requires_partner'):
        raise ValueError('Multi-character interactions require a second reference.')
    result = await generate_image(reference_bytes, candidate_prompt(request))
    info = validate_motion_sheet(result)
    return result, {**info, 'status': 'review_required',
                    'identity_verification': 'not_performed',
                    'motion_quality_verification': 'not_performed'}


async def generate_hf_candidate(reference_bytes, prompt):
    from huggingface_hub import AsyncInferenceClient
    from hf_media_common import HF_TOKEN

    model = os.getenv('MOTION_ASSET_IMAGE_MODEL', '').strip()
    provider = os.getenv('MOTION_ASSET_IMAGE_PROVIDER', '').strip()
    if not model or not provider or not HF_TOKEN:
        raise ValueError('Motion candidate provider, model and token must be configured.')
    async with AsyncInferenceClient(provider=provider, token=HF_TOKEN, timeout=180) as client:
        image = await client.image_to_image(reference_bytes, prompt=prompt, model=model)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def candidate_generation_enabled():
    return os.getenv('MOTION_ASSET_AUTO_GENERATION', '').strip().lower() == 'true'
