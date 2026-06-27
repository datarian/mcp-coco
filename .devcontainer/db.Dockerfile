FROM mcr.microsoft.com/devcontainers/base:bookworm

ENV PGVECTOR_VERSION=0.8.3

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        postgresql-15 \
        postgresql-client-15 \
        postgresql-server-dev-15 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://github.com/pgvector/pgvector/archive/refs/tags/v${PGVECTOR_VERSION}.tar.gz" -o /tmp/pgvector.tar.gz \
    && tar -xzf /tmp/pgvector.tar.gz -C /tmp \
    && cd "/tmp/pgvector-${PGVECTOR_VERSION}" \
    && make \
    && make install \
    && rm -rf /tmp/pgvector.tar.gz "/tmp/pgvector-${PGVECTOR_VERSION}"

COPY .devcontainer/start-db.sh /usr/local/bin/start-db.sh

RUN chmod +x /usr/local/bin/start-db.sh \
    && mkdir -p /var/lib/postgresql/data \
    && chown -R postgres:postgres /var/lib/postgresql