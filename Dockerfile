# Use your base image
FROM harbor-registry-non-prod.uidai.gov.in/data-platform/python-base-3:1.0.0

# ---- Global env ----
ENV HTTP_PROXY="" \
    http_proxy="" \
    HTTPS_PROXY="" \
    https_proxy="" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Centralizing Pip Config
    PIP_INDEX_URL=http://10.10.206.59:8080/repository/pypi-proxy/simple \
    PIP_TRUSTED_HOST=10.10.206.59 \
    PIP_EXTRA_INDEX_URL=http://10.10.206.59:8080/repository/pypi-third-party/ \
    PIP_ROOT_USER_ACTION=ignore

# Set internal Ubuntu mirrors
RUN echo "deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu jammy restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-updates restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-security restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-backports restricted universe main multiverse" > /etc/apt/sources.list

# Working directory setup
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Upgrade tooling, handle OpenCV cleanup, install requirements, and generate SBOM in one layer
RUN python3 -m pip install --upgrade --no-cache-dir pip setuptools wheel && \
    (python3 -m pip uninstall -y opencv-python-headless opencv-python || true) && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    # Install CycloneDX, generate report, then remove tool to keep image slim
    python3 -m pip install --no-cache-dir cyclonedx-bom && \
    python3 -m cyclonedx_py requirements --of JSON -o /app/SCA-bom.json requirements.txt && \
    python3 -m pip uninstall -y cyclonedx-bom

# Copy application code and resources
COPY src/ ./src/
COPY resources/ ./resources/

# ---- Security: Non-root user setup ----
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8000

# Run the application
CMD ["python", "src/main.py"]

