LocalRAG
Portable open-source RAG assistant for personal use.
Architecture
Next.js frontend
FastAPI backend
Qdrant vector database
Ollama/local LLM
Docker Compose
Kubernetes deployment
Development
Start the core services:
```bash
docker compose up --build
```
Frontend:
http://localhost:3000
API:
http://localhost:8000
API health:
http://localhost:8000/health
Qdrant:
http://localhost:6333