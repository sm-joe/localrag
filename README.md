LocalRAG
LocalRAG is a portable, Docker-based Retrieval-Augmented Generation
(RAG) chatbot for running document-grounded AI locally.
It combines a Next.js web UI, FastAPI backend, Qdrant vector database,
and Ollama local LLM/embedding services into a single Docker Compose
application.
Architecture
``` text
Browser
   |
   v
Next.js Web UI
   |
   v
FastAPI API
   |
   +--------------------+
   |                    |
   v                    v
Document Ingestion    RAG / Chat
   |                    |
   +--> Parser          +--> Query Embedding
   +--> Chunker         +--> Qdrant Retrieval
   +--> Embeddings      +--> Prompt Construction
          |             +--> Ollama LLM
          v                    |
       Qdrant <----------------+
```
Stack
Frontend: Next.js / React
Backend: FastAPI / Python
Vector database: Qdrant
LLM runtime: Ollama
LLM: `llama3.2:3b` by default
Embeddings: `nomic-embed-text`
Containerization: Docker Compose
Features
Local document ingestion
PDF, DOCX, TXT, and Markdown support
File type and content validation
Upload and parser resource limits
Text normalization and chunking
Local embeddings through Ollama
Vector search through Qdrant
Filename-aware exact retrieval
Document-grounded answers
Source citations
Prompt-injection-resistant retrieval prompts
Persistent Qdrant and Ollama data
Hardened non-root containers
Localhost-only application ports
Docker security controls
Automated API and web CI
Gitleaks secret scanning
CodeQL analysis
Trivy configuration scanning
Trivy container vulnerability scanning
Quick Start
Prerequisites
Docker Desktop with Docker Compose
At least 8 GB RAM recommended
Sufficient disk space for Ollama models and Qdrant data
Start LocalRAG
From the repository root:
``` powershell
docker compose build
docker compose up -d
```
Check the services:
``` powershell
docker compose ps
```
Open:
``` text
http://localhost:3000
```
Stop
``` powershell
docker compose down
```
Persistent data remains under `data/qdrant` and `data/ollama`.
Configuration
Example model configuration:
``` text
LLM_MODEL=llama3.2:3b
EMBEDDING_MODEL=nomic-embed-text
```
The API uses Docker Compose service names for Qdrant and Ollama.
Document Ingestion
Supported extensions:
``` text
.pdf
.docx
.txt
.md
```
The ingestion pipeline validates file type, content, filename safety,
upload size, empty files, PDF page count, DOCX paragraph count, and
extracted text size.
Temporary upload data is cleaned up after processing.
Retrieval
LocalRAG uses semantic retrieval with top-K 5 and a 0.45 score
threshold.
When a query explicitly contains a supported filename, LocalRAG performs
exact filename retrieval before falling back to semantic retrieval. This
preserves the normal semantic threshold while making
document-identification questions reliable.
RAG Safety
Retrieved document content is treated as untrusted data.
The application prevents retrieved content from acting as system,
developer, or user instructions, commands, policies, or requests for
secrets/internal information.
Answers are grounded in relevant retrieved evidence and use source
citations.
Evaluation Baseline
Metric	Baseline
Evaluation cases	5
Passed	5/5
Pass rate	100%
Expected document recall	100%
Context retrieval	100%
Concept answer pass	100%
Citation coverage	100%
Grounded answer rate	100%
Average concept score	100%
The current regression baseline is top-K `5` and score threshold `0.45`.
Testing
``` powershell
docker compose exec api pytest -q
docker compose exec api pytest -q tests/test_rag.py tests/test_retrieval.py
```
CI Security Gates
``` text
Detect Changes
      |
      +--> Gitleaks
      +--> CodeQL
      +--> Trivy Config
      +--> API Tests
      +--> Web Build
                |
                v
          Docker Build
            |       |
            v       v
        API Image  Web Image
            |       |
            v       v
         Trivy    Trivy
```
The pipeline builds Docker images only when relevant paths change.
Security
See SECURITY.md.
Project Scope
LocalRAG is intentionally a small, portable, self-contained Docker
application.
Out of scope:
Kubernetes
Service mesh
Multi-cluster deployment
Enterprise observability stacks
Complex distributed infrastructure
Cloud-managed LLM dependencies
The goal is a practical local RAG application that can be cloned,
started with Docker Compose, used locally, and understood end-to-end.
License
See the repository license file for licensing terms.