FROM harbor-registry-non-prod.uidai.gov.in/base/python:3.11.5-slim

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt
