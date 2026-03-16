# Use your base image
FROM harbor-registry-non-prod.uidai.gov.in/aiml-projects/ubuntu22-aiml-base:1.0.0

# Clear proxy settings globally
ENV HTTP_PROXY=""
ENV http_proxy=""
ENV HTTPS_PROXY=""
ENV https_proxy=""

COPY ./sources.list /etc/apt/sources.list

# Remove the existing 'app' folder from the base image
RUN rm -rf /app

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .



RUN pip3 uninstall opencv-python-headless -y

RUN pip3 uninstall opencv-python -y


RUN pip3 install -i http://10.10.206.59:8080/repository/pypi-proxy/simple --trusted-host 10.10.206.59 -r requirements.txt

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

