# syntax=docker/dockerfile:1.7

FROM node:22-slim AS frontend-base

WORKDIR /app

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/local-operator \
    && chown -R appuser:appuser /app

COPY --chown=appuser:appuser package.json package-lock.json ./
COPY --chown=appuser:appuser docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER appuser

RUN npm ci --legacy-peer-deps --ignore-scripts

# Run esbuild's native-binary installer after npm finishes writing dependencies.
RUN node node_modules/esbuild/install.js \
    && lock_hash="$(sha256sum package-lock.json)" \
    && printf '%s' "${lock_hash%% *}" > node_modules/.package-lock.sha256

COPY --chown=appuser:appuser .npmrc components.json eslint.config.js index.html playwright.config.ts postcss.config.js tsconfig.api-strict.json tsconfig.app.json tsconfig.json tsconfig.node.json tsconfig.sonar.json vite.config.ts ./
COPY --chown=appuser:appuser public ./public
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser src ./src

FROM frontend-base AS dev

EXPOSE 5173

ENTRYPOINT ["/app/docker-entrypoint.sh"]

FROM frontend-base AS build

ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

FROM nginx:1.29-alpine AS prod

RUN addgroup -g 10001 appuser \
    && adduser -u 10001 -G appuser -h /app -s /sbin/nologin -D appuser

COPY nginx/ /etc/nginx/templates/
COPY docker-prod-entrypoint.sh /docker-entrypoint.d/04-resolve-local-operator-token.envsh
COPY --from=build /app/dist /usr/share/nginx/html

RUN mkdir -p /app/local-operator /var/cache/nginx \
    && chmod +x /docker-entrypoint.d/04-resolve-local-operator-token.envsh \
    && sed -i 's#^pid .*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && sed -i 's/^user  nginx;/# user directive omitted: master runs unprivileged/' /etc/nginx/nginx.conf \
    && chown -R 10001:10001 /app/local-operator /var/cache/nginx /etc/nginx/conf.d

USER appuser

EXPOSE 8080
