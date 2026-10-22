# Build context is the repository root because Vite imports the shared adapter
# from backend/integration.
FROM node:20-alpine AS build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
COPY backend/integration/ /build/backend/integration/

RUN npm run build


FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/frontend/dist/ /usr/share/nginx/html/

EXPOSE 80
