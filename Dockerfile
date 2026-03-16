FROM harbor-registry-non-prod.uidai.gov.in/aiml-projects/ubuntu22-aiml-base:1.0.0

RUN echo "deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu jammy restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-updates restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-security restricted universe main multiverse\n\
deb http://10.10.213.11:8081/ubuntu/mirror/archive.ubuntu.com/ubuntu/ jammy-backports restricted universe main multiverse" > /etc/apt/sources.list

WORKDIR /app


# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir \
    -i http://10.10.206.59:8080/repository/pypi-proxy/simple \
    --trusted-host 10.10.206.59 \
    --upgrade pip && \
    pip install --no-cache-dir \
    --root-user-action=ignore \
    -i http://10.10.206.59:8080/repository/pypi-proxy/simple \
    --trusted-host 10.10.206.59 \
    -r requirements.txt


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
