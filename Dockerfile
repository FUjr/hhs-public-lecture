FROM node:24-alpine AS frontend

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY index.html ./
COPY vite.config.js ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/bin/docker-compose /usr/local/bin/docker-compose
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

COPY *.py ./
COPY --from=frontend /app/dist ./dist

EXPOSE 8000

CMD ["python", "web_dialogue_app.py", "--host", "0.0.0.0", "--port", "8000"]
