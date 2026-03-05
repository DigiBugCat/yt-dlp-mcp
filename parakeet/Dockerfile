FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3-pip python3.12-dev \
      ffmpeg libsndfile1 git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

WORKDIR /app

# Clone the parakeet-v3-diarized repo.
RUN git clone --depth 1 https://github.com/loudpage/parakeet-v3-diarized.git .

# Install PyTorch with CUDA support first, then the rest.
RUN pip install --no-cache-dir --break-system-packages \
      torch torchaudio --index-url https://download.pytorch.org/whl/cu128 \
 && pip install --no-cache-dir --break-system-packages \
      nemo_toolkit[asr] fastapi uvicorn python-multipart pydantic \
      pyannote-audio librosa soundfile pydub

# Apply patches for pyannote 4.0 + NeMo 2.7 compatibility.
COPY patches/diarization_init.py /app/diarization/__init__.py
COPY patches/transcription_fix.py /app/transcription.py

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
