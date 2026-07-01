# Models

This directory is reserved for local AI model files.

The default detector model path is:

```text
models/best.pt
```

The default OCR model name is:

```text
hezarai/crnn-fa-license-plate-recognition-v2
```

## Recommended setup

Because model files may be large or license-sensitive, do not commit production models unless you are sure that the repository visibility and license policy allow it.

For this project, the detector model is expected to be copied or downloaded to:

```text
models/best.pt
```

Then configure:

```env
DETECTOR_MODEL_PATH=models/best.pt
OCR_MODEL_NAME=hezarai/crnn-fa-license-plate-recognition-v2
```

## Options

### Option 1: Private repository

If the model is small and the repository is private, you may commit it directly or use Git LFS.

### Option 2: GitHub Release

Upload the model file to a GitHub Release and set `MODEL_DOWNLOAD_URL` in `.env`.

Then run:

```bash
make models
```

### Option 3: Internal object storage

Store the model in a private object storage service and set `MODEL_DOWNLOAD_URL` to that secure download URL.

Never commit real secrets, private tokens, or internal infrastructure addresses.
