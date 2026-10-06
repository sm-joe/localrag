# syntax=docker/dockerfile:1.7

FROM ollama/ollama:0.35.1

ENV OLLAMA_MODELS=/opt/ollama-models \
    OLLAMA_HOST=0.0.0.0:11434 \
    HOME=/home/ollama

RUN mkdir -p /opt/ollama-models /home/ollama \
    && groupadd --gid 10001 ollama \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --home-dir /home/ollama \
        --no-create-home \
        --shell /usr/sbin/nologin \
        ollama \
    && chown -R 10001:10001 \
        /opt/ollama-models \
        /home/ollama

USER 10001:10001

ENTRYPOINT ["ollama"]

CMD ["serve"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ollama list >/dev/null 2>&1 || exit 1