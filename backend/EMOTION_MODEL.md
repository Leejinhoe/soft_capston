# KOTE emotion model

The KOTE checkpoint is optional and is not committed to Git because it is a large model artifact. The psychology detail API analyzes each selected choice separately when a completed story is first opened in the psychology tab. If the checkpoint or optional dependencies are unavailable, the existing psychology analysis continues without emotion labels.

From the project root, extract the privately shared model archive so these files exist:

```text
models/emotion_checkpoint/config.json
models/emotion_checkpoint/model.safetensors
models/emotion_tokenizer/vocab.txt
```

Install the optional CPU inference dependencies from the backend directory:

```powershell
python -m pip install -r requirements-emotion.txt
```

The default paths are project-relative. `KOTE_MODEL_PATH` and `KOTE_TOKENIZER` may override them with absolute paths or paths relative to the project root. The model reports emotion cues from the chosen sentence; it is not a psychological diagnosis, and its raw scores are not shown in the app.
