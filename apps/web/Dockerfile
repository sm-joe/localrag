FROM node:22-alpine AS dependencies

WORKDIR /app

COPY package.json ./

RUN npm install


FROM node:22-alpine AS builder

WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

RUN mkdir -p public && npm run build


FROM node:22-alpine AS runner

RUN npm install -g npm@latest && npm cache clean --force \
    && rm -rf /usr/local/lib/node_modules/npm \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup \
        --system \
        --gid 10001 \
        localrag \
    && adduser \
        --system \
        --uid 10001 \
        --ingroup localrag \
        --no-create-home \
        localrag

COPY --from=builder --chown=10001:10001 /app/public ./public
COPY --from=builder --chown=10001:10001 /app/.next/standalone ./
COPY --from=builder --chown=10001:10001 /app/.next/static ./.next/static

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000', r => process.exit(r.statusCode >= 200 && r.statusCode < 400 ? 0 : 1)).on('error', () => process.exit(1))"

EXPOSE 3000

CMD ["node", "server.js"]