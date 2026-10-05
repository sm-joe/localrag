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

EXPOSE 3000

CMD ["node", "server.js"]