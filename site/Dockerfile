# Public site (Fase 5 G1): static files on the main domain (nexo.do).
FROM nginx:1.27-alpine
ARG APP_URL=http://localhost:3000
ARG API_URL=http://localhost:8000
ARG SITE_URL=http://localhost:8080
ARG CONTACT_EMAIL=
COPY . /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN cd /usr/share/nginx/html \
    && rm -f Dockerfile nginx.conf \
    && sed -i "s#__APP_URL__#${APP_URL}#; s#__API_URL__#${API_URL}#; s#__CONTACT_EMAIL__#${CONTACT_EMAIL}#" config.js \
    && sed -i "s#__SITE_URL__#${SITE_URL}#g" robots.txt sitemap.xml
