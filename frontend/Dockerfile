# ---- Base ----
FROM node:20-alpine AS base

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- Development ----
FROM base AS development

COPY . .
EXPOSE 3000
CMD ["npx", "next", "dev", "--turbo", "-H", "0.0.0.0"]

# ---- Production ----
FROM base AS production

COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
