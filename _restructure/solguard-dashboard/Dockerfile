# solguard-dashboard — static HTML served by nginx.
# Vercel is the primary production deployment; this Dockerfile lets you
# run the dashboard anywhere (docker-compose, Railway, Fly, Kubernetes).

FROM nginx:1.27-alpine

# Hardened default config with gzip + security headers baked in.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html

# Health endpoint
RUN printf 'ok\n' > /usr/share/nginx/html/healthz

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s CMD wget -q --spider http://localhost/healthz || exit 1
