set -x
cd /workspace/mahabharat/proto
uv venv -q --python 3.12 .venv-$1
VIRTUAL_ENV=.venv-$1 uv pip install --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu torch torchaudio soundfile $2 && echo INSTALL_OK
