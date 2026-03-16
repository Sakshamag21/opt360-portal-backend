FROM harbor-registry-non-prod.uidai.gov.in/aiml-projects/aiml-base:1.0.0 AS builder
# ... (Builder stage remains same)

FROM harbor-registry-non-prod.uidai.gov.in/aiml-projects/aiml-base:1.0.0
ENV DEBIAN_FRONTEND=noninteractive TZ=Asia/Kolkata PYTHONUNBUFFERED=1

# INLINE FIX: No COPY needed
RUN echo "deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu jammy restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-updates restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-security restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-backports restricted universe main multiverse" > /etc/apt/sources.list

COPY requirements.txt .

# Proceed with install
# Install system dependencies
# Added flags to bypass GPG signature issues with the internal mirror
RUN pip3 install -i http://10.10.206.59:8080/repository/pypi-proxy/simple --trusted-host 10.10.206.59 -r requirements.txt

WORKDIR /app
# Install CycloneDX SBOM tool
RUN python3 -m pip install cyclonedx-bom


# Configure pip for internal proxy
RUN mkdir -p /root/.pip && \
    echo "[global]\nindex-url = 10.10.206.59\ntrusted-host = 10.10.206.59" > /root/.pip/pip.conf

# Copy application code
COPY src/ ./src/
COPY resources/ ./resources/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install CycloneDX SBOM tool
RUN python3 -m pip install cyclonedx-bom

# Generate SBOM using CycloneDX Python CLI
RUN python3 -m cyclonedx_py requirements -i requirements.txt -o /SCA-bom.json  

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=5)"

# Run the application
CMD ["python", "src/main.py"]
