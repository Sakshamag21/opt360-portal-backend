FROM harbor-registry-non-prod.uidai.gov.in/base/node:18-alpine AS build

WORKDIR /app

COPY package*.json /app/

# ENV http_proxy=http://10.10.16.22:3128
# ENV https_proxy=http://10.12.11.13:3128

# proxy
RUN npm config set registry http://10.10.206.59:8080/repository/npm-proxy/
# RUN npm config set https-proxy http://10.12.11.13:3128
RUN npm install -g @cyclonedx/cyclonedx-npm@1.15.0

# Install dependencies
RUN npm install --legacy-peer-deps
RUN npm dedupe

COPY .  /app/

# Build the application first
RUN npm run build

# Generate CycloneDX SBOM (Must Be After build stage)
# Using production flag to only include production dependencies in BOM
RUN cyclonedx-npm --spec-version 1.6 --ignore-npm-errors --output-file /app/SCA-bom.json

# Verify build output
RUN ls -la ./build/

FROM harbor-registry-non-prod.uidai.gov.in/base/nginx:ubuntu22.04_stable_25022026 AS prod

#Configure nginx
RUN rm -rf /etc/nginx/nginx. conf
COPY nginx.conf /etc/nginx/nginx.conf 
COPY default.conf /etc/nginx/conf.d/default.conf

#Copy build files
COPY --from=build /app/build /usr/share/nginx/html

# Copy SCA BOM file from build stage
COPY --from=build /app/SCA-bom.json /tmp/SCA-bom.json

# Verify BOM file exists
RUN ls -la /tmp/SCA-bom.json

# Verify copied files
RUN ls -la /usr/share/nginx/html/

# Set proper permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Ensure log directory exists and is writable
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chmod -R 755 /var/log/nginx

# Create symbolic links for stdout/stderr logging (Kubernetes best practice)
RUN ln -sf /dev/stdout /var/log/nginx/access.log && \
    ln -sf /dev/stderr /var/log/nginx/error.log

EXPOSE 80

EXPOSE 443

WORKDIR /usr/share/nginx/html

COPY --from=build /app/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Test nginx configuration
RUN nginx -t

CMD ["/docker-entrypoint.sh"]
