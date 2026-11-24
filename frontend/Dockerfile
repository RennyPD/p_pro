FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ARG VITE_SENTRY_DSN=
ARG VITE_RELEASE=
ENV VITE_API_URL=$VITE_API_URL VITE_SENTRY_DSN=$VITE_SENTRY_DSN VITE_RELEASE=$VITE_RELEASE
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
