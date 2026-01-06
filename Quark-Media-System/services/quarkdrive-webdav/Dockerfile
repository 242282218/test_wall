FROM rust:bookworm AS builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/quarkdrive-webdav /usr/local/bin/quarkdrive-webdav

EXPOSE 5244 12345

ENTRYPOINT ["quarkdrive-webdav"]
