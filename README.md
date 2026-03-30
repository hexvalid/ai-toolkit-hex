# AI Toolkit Hex

Minimal Apple Silicon fork of [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit).

This fork exists for a very specific workflow:

- train locally on macOS with `device: mps`
- generate sample previews on another machine through Draw Things
- allow the remote preview model to be different from the local training model

This README only covers macOS on Apple Silicon.

## What Is Different

- Local training is meant to run on Apple Silicon with MPS.
- Preview sampling is remote, not local in-process generation.
- Preview sampling is configured through `sample.drawthings`.
- The remote sample model can be different from the model you are training on your Mac.
- Returned previews are saved by AI Toolkit, not into the Draw Things gallery on the remote machine.

## Requirements

- Apple Silicon Mac
- macOS
- Xcode Command Line Tools
- Homebrew
- Python 3.12
- Node 22
- Git

## Install

```bash
xcode-select --install

brew install python@3.12 node@22 git
echo 'export PATH="/opt/homebrew/opt/python@3.12/bin:/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile

git clone https://github.com/hexvalid/ai-toolkit-hex.git
cd ai-toolkit-hex

python3.12 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install --no-cache-dir torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1
pip install -r requirements.txt

cd ui
npm run build_and_start
```

Open [http://localhost:8675](http://localhost:8675).

## Remote Samples

Training happens on your Mac. Sample previews happen on another machine running Draw Things remote access.

In the job config or UI, set:

- `device: mps`
- `sample.drawthings.server`
- `sample.drawthings.port`
- `sample.drawthings.model`
- `sample.drawthings.shared_secret` if your remote server requires it

The remote Draw Things model can be different from `model.name_or_path`.

## CLI

```bash
source venv/bin/activate
python run.py path/to/config.yml
```

## Notes

- You still need the correct Hugging Face access/token for gated models.
- This fork is intentionally optimized around the MPS + remote-preview workflow, not general multi-platform setup docs.

## Credits

This project is based on [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit). Credit for the core project, training system, and the vast majority of the original work goes to the upstream project and its contributors.
