FROM node:22-alpine AS build
WORKDIR /app
COPY viewer/package.json viewer/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY viewer/ ./
# Vite inlines VITE_* at build time, so the API URL is a build arg. In a real
# deploy this is the one thing that differs between environments; see README.
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_VIEWER_URL=http://localhost:5174
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_VIEWER_URL=$VITE_VIEWER_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Single-page app: unknown paths are routes, not missing files.
RUN printf 'server {\n  listen 5174;\n  root /usr/share/nginx/html;\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 5174
