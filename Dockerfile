FROM harbor-registry-non-prod.uidai.gov.in/devops/golang:1.24.7-ubuntu-build AS build

# Set module mode + proxy rules
ENV GO111MODULE=on \
    GOPROXY=http://10.10.204.46:8080/repository/goproxy \
    GOPRIVATE=bitbucket.uidai.net.in/* \
    GONOPROXY=bitbucket.uidai.net.in/* \
    GONOSUMDB=*

WORKDIR /

COPY ./.netrc /root/.netrc
COPY ./cyclonedx-gomod /usr/local/bin/cyclonedx-gomod
COPY . .

RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o operator360-portal-backend .

RUN chmod +x /usr/local/bin/cyclonedx-gomod
RUN cyclonedx-gomod app -json -output /SCA-bom.json -main .

FROM harbor-registry-non-prod.uidai.gov.in/devops/golang:1.24.7-ubuntu_jammy-gcc-git

# Create User
RUN useradd -ms /bin/bash uidapp
USER uidapp
WORKDIR /home/uidapp

COPY --from=build /operator360-portal-backend .
COPY --from=build /SCA-bom.json .
COPY --from=build /users.json .

# No config.json baked in — runtime config comes entirely from OPT360_* env
# vars (ConfigMap for non-secret fields, Secret for credentials), see
# config/config.go and docs/LOCAL_SETUP.md. config.json is still supported as
# a fallback for local (non-container) runs but is gitignored and never part
# of the build context.

EXPOSE 8080
CMD ["/home/uidapp/operator360-portal-backend"]