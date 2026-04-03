FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Python
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    python3.12-venv

WORKDIR /workspace

# Copy requirements first for better Docker layer caching
COPY requirements.txt /workspace/requirements.txt

# Create venv and install deps
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /workspace/requirements.txt

# Optional: pre-create writable dirs
RUN mkdir -p /workspace/checkpoints /workspace/logs

# Copy project files
COPY . /workspace

CMD ["/bin/bash"]