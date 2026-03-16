# Use your base image
FROM harbor-registry-non-prod.uidai.gov.in/aiml-projects/ubuntu22-aiml-base:1.0.0

# ---- Global env ----
ENV HTTP_PROXY="" \
    http_proxy="" \
    HTTPS_PROXY="" \
    https_proxy="" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Clean any preexisting /app
RUN rm -rf /app

# Working dir
WORKDIR /app

# Copy requirements first (cache-friendly)
COPY requirements.txt .

# Make sure pip tooling is current
RUN python3 -m pip install --upgrade --no-cache-dir pip setuptools wheel

# If OpenCV is present in the base image and you want it removed
RUN python3 -m pip uninstall -y opencv-python-headless || true \
 && python3 -m pip uninstall -y opencv-python || true

# Install project dependencies from your internal proxy
# (keep PyPI as fallback in case some wheels are not mirrored)
RUN python3 -m pip install --no-cache-dir \
    -i http://10.10.206.59:8080/repository/pypi-proxy/simple \
    --trusted-host 10.10.206.59 \
    --extra-index-url https://pypi.org/simple \
    -r requirements.txt

# Copy app code
COPY src/ ./src/
COPY resources/ ./resources/

# ---- Install CycloneDX and generate SBOM as root ----
# Install CycloneDX SBOM tool
RUN python3 -m pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    cyclonedx-bom

# (Optional) verify CLI presence
RUN cyclonedx-py --version || python3 -m cyclonedx_py --version

# Generate SBOM from requirements.txt, write it into /app (writable path)
RUN python3 -m cyclonedx_py requirements \
    -i requirements.txt \
    -o /app/SCA-bom.json

# ---- Create non-root user for runtime ----
RUN useradd -m -u 1000 appuser \
 && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000


# Run the application
CMD ["python", "src/main.py"]
