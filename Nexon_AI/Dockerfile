FROM python:3.10-slim

# Install system dependencies (ffmpeg is required for video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables to prevent HF auto-injection & optimize CPU
ENV HF_XET_HIGH_PERFORMANCE=1 \
    TRANSFORMERS_CACHE=/tmp/hf_cache \
    PYTORCH_NO_CUDA_MEMORY_CACHING=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Expose Gradio port
EXPOSE 7860

# Start the app
CMD ["python", "app.py"]
