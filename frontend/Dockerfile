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

ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
