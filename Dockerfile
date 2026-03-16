FROM harbor-registry-non-prod.uidai.gov.in/base/python:3.11.5-slim

# Point APT to internal mirror
RUN printf "deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu jammy restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-updates restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-security restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-backports restricted universe main multiverse\n" > /etc/apt/sources.list

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Configure internal PyPI once (optional but clean)
# NOTE: Your repo is HTTP; keep trusted-host set to the IP to bypass TLS checks.
RUN mkdir -p /etc/pip && \
    printf "[global]\nindex-url = http://10.10.206.59:8080/repository/pypi-proxy/simple\ntrusted-host = 10.10.206.59\n" > /etc/pip.conf

# Upgrade pip tooling and install application deps from internal PyPI
# Add retries/timeout to handle intermittent internal repo issues
RUN python3 -m pip install --no-cache-dir --timeout 60 --retries 10 --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --timeout 60 --retries 10 --root-user-action=ignore -r requirements.txt

# Install CycloneDX Python CLI (modern tool)
# Provides the 'cyclonedx-py' command
RUN python3 -m pip install --no-cache-dir --timeout 60 --retries 10 cyclonedx-bom

# Copy application code
COPY src/ ./src/
COPY resources/ ./resources/

# Create non-root user for security and fix ownership
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# --- SBOM generation at build-time (runs as root or as appuser; both are OK)
# Using the CLI `cyclonedx-py` to generate from requirements.txt
# Output goes to /SCA-bom.json at image build time
RUN cyclonedx-py requirements -i requirements.txt -o /SCA-bom.json -e JSON

# Switch to non-root user AFTER all installs and SBOM generation
USER appuser

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check (simple HTTP GET)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=5)"

# Run the application
CMD ["python", "src/main.py"]
