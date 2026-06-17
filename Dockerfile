FROM python:3.11-slim

WORKDIR /app

# Install build tools + Rust (needed to compile discord-protos if no pre-built wheel exists)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt .
# --prefer-binary picks pre-built wheels first; falls back to source compile using Rust above
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
