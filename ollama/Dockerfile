FROM ollama/ollama:latest

ENV OLLAMA_MODELS=/opt/ollama-models \
    OLLAMA_HOST=0.0.0.0:11434

RUN mkdir -p /opt/ollama-models

RUN set -eux; \
    ollama serve > /tmp/ollama-build.log 2>&1 & \
    OLLAMA_PID=$!; \
    until ollama list >/dev/null 2>&1; do \
        if ! kill -0 "${OLLAMA_PID}" 2>/dev/null; then \
            cat /tmp/ollama-build.log; \
            exit 1; \
        fi; \
        sleep 2; \
    done; \
    ollama pull nomic-embed-text; \
    ollama pull llama3.2:3b; \
    kill "${OLLAMA_PID}"; \
    wait "${OLLAMA_PID}" || true; \
    rm -f /tmp/ollama-build.log

ENTRYPOINT ["ollama"]

CMD ["serve"]