"""Optional private ZeroGPU image-to-video service for the media backend."""
import os
import tempfile
import uuid

import gradio as gr
import spaces
import torch
from diffusers import LTXImageToVideoPipeline
from diffusers.utils import export_to_video
from PIL import ImageOps

MODEL = "Lightricks/LTX-Video"
FRAME_RATE = 12
NUM_FRAMES = 49

pipe = LTXImageToVideoPipeline.from_pretrained(
    MODEL, torch_dtype=torch.float16, low_cpu_mem_usage=True, token=False
).to("cuda")
pipe.vae.enable_tiling()


@spaces.GPU(duration=120)
def generate(image, action, seed):
    if image is None or not (action or "").strip():
        raise gr.Error("An image and action are required.")
    frame = ImageOps.fit(image.convert("RGB"), (384, 384))
    result = pipe(
        image=frame,
        prompt=action.strip()[:500],
        negative_prompt="distorted face, extra limbs, flickering, blurry, morphing, ghosting, transparency, double exposure",
        width=384,
        height=384,
        num_frames=NUM_FRAMES,
        frame_rate=FRAME_RATE,
        num_inference_steps=50,
        guidance_scale=5.0,
        generator=torch.Generator(device="cpu").manual_seed(int(seed)),
    ).frames[0]
    output = os.path.join(tempfile.gettempdir(), f"video-{uuid.uuid4().hex}.mp4")
    export_to_video(result, output, fps=FRAME_RATE)
    return output


app = gr.Interface(
    fn=generate,
    inputs=[gr.Image(type="pil"), gr.Textbox(), gr.Number(value=42, precision=0)],
    outputs=gr.Video(),
    api_name="generate",
)
app.queue(default_concurrency_limit=1).launch()
