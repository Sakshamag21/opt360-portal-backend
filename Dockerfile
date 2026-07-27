# ---- Build stage ----
FROM golang:1.25-bookworm AS build

# If your network requires an internal Go module proxy (mirroring the
# PIP_INDEX_URL / PIP_TRUSTED_HOST setup in the previous Python build),
# set it here, e.g.:
# ENV GOPROXY=http://10.10.206.59:8080/repository/go-proxy/ \
#     GONOSUMCHECK=1 \
#     GOFLAGS=-insecure
ENV CGO_ENABLED=0 \
    GOOS=linux

WORKDIR /app

# Copy go.mod/go.sum first for better layer caching
COPY go.mod go.sum ./
RUN go mod download

# Copy application code and build a static binary
COPY main.go ./
COPY internal/ ./internal/
RUN go build -o /operator360-api .

# Generate a CycloneDX SBOM for the module graph (mirrors the
# cyclonedx-py step in the previous Python build)
RUN go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@latest && \
    cyclonedx-gomod mod -json -output /SCA-bom.json .

# ---- Runtime stage ----
FROM gcr.io/distroless/static-debian12:nonroot AS runtime

WORKDIR /app

# Copy application binary, resources, and generated SBOM
COPY --from=build /operator360-api ./operator360-api
COPY resources/ ./resources/
COPY --from=build /SCA-bom.json /SCA-bom.json

# distroless "nonroot" images already run as a non-root user (65532:65532)
USER nonroot:nonroot

# Expose application port
EXPOSE 8000

# Run the application
ENTRYPOINT ["./operator360-api"]
