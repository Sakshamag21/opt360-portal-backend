FROM mndc-harbor-registry-non-prod.uidai.net.in/base/golang-1.25.5:latest AS build

# Set module mode + proxy rules
ENV GO111MODULE=on \
    GOPROXY=http://10.10.206.59:8080/repository/go/ \
    GOPRIVATE=bitbucket.uidai.net.in/* \
    GONOPROXY=bitbucket.uidai.net.in/* \
    GONOSUMDB=bitbucket.uidai.net.in

WORKDIR /

COPY ./.netrc /root/.netrc
COPY ./cyclonedx-gomod /usr/local/bin/cyclonedx-gomod
COPY . .

RUN go build -o operator360-api main.go

RUN chmod +x /usr/local/bin/cyclonedx-gomod

# Changed 'app' subcommand to 'mod' to bypass the git version resolution check
RUN cyclonedx-gomod mod -json -output /SCA-bom.json .


FROM mndc-harbor-registry-non-prod.uidai.net.in/base/golang-1.25.5:latest

# Create User
RUN useradd -ms /bin/bash uidapp
USER uidapp
WORKDIR /home/uidapp

COPY --from=build /SCA-bom.json .
COPY --from=build /operator360-api .
EXPOSE 8000
CMD ["/home/uidapp/operator360-api"]