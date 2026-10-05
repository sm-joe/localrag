Security Policy
Overview
LocalRAG is a local, Docker-based RAG application.
Security is implemented across document ingestion, RAG prompt
construction, container runtime, dependencies, and CI.
Supported Versions
LocalRAG is currently maintained as a single active project version.
Security fixes should be applied to the current `main` branch.
Reporting a Vulnerability
Please do not disclose an undisclosed security vulnerability in a public
issue.
For a private report, use the repository’s available GitHub security
reporting mechanism if enabled.
A useful report should include:
Clear vulnerability description
Affected component
Reproduction steps
Security impact
Relevant safe logs/screenshots
Suggested remediation, if known
Do not include passwords, API keys, private credentials, personal data,
or other secrets.
Security Controls
File Upload Security
Supported document types are:
``` text
PDF
DOCX
TXT
Markdown
```
Uploads are protected by:
Maximum upload size
Empty-file rejection
Filename validation
Path separator normalization
Basename normalization
NUL-byte rejection
File extension validation
File content validation
Temporary-file cleanup
Parser Limits
Current limits include:
PDF: maximum 200 pages
DOCX: maximum 10,000 paragraphs
Extracted text: maximum 2,000,000 characters
Content Validation
PDF and DOCX content is checked before parsing.
Text files use controlled decoding error handling.
Malformed or unsupported content is rejected.
RAG Prompt Security
Retrieved document content is treated as untrusted external data.
Retrieved content is not allowed to act as:
System instructions
Developer instructions
User instructions
Commands
Policies
Requests to reveal secrets
Requests to reveal internal configuration
Requests to modify application behavior
Prompt-injection text inside a document is treated as document content.
Retrieval Security
Normal semantic retrieval uses:
Top-K: `5`
Score threshold: `0.45`
Queries explicitly identifying a supported filename use exact filename
matching before semantic retrieval.
Container Security
The API and web containers run as non-root users.
The configuration also uses:
`no-new-privileges`
Dropped Linux capabilities
Restricted temporary filesystems
Localhost-only application bindings
Isolated Docker networks
Persistent volumes only where required
Qdrant and Ollama are kept on the internal backend network rather than
published directly to the host.
Secrets
Environment files containing local configuration or secrets are excluded
from source control.
The repository must never contain:
Cloud credentials
API keys
Private keys
Passwords
Access tokens
Production secrets
Use `.env.example` for documented configuration examples.
Dependency Security
Application dependencies are pinned.
The CI pipeline performs container vulnerability scanning using Trivy.
The blocking vulnerability gate focuses on `CRITICAL` and `HIGH`
findings, with unfixed findings excluded.
CI Security
Gitleaks
Detects committed secrets and credentials.
CodeQL
Performs static application security analysis.
Trivy Config
Scans repository configuration and infrastructure definitions.
Trivy Container Scanning
Scans the built API and web images after they are built and loaded into
the CI runner.
Security Regression
Automated tests cover security-related behavior including:
Upload validation
Parser validation
Retrieval behavior
Prompt-injection protection
RAG behavior
The API test suite should pass before a change is considered complete.
Security Baseline
The current baseline includes:
Secure file upload handling
Parser resource limits
Untrusted-document prompt handling
Non-root containers
Capability dropping
`no-new-privileges`
Internal backend networking
Localhost-only application exposure
Secret scanning
SAST
Configuration scanning
Container vulnerability scanning
Automated regression testing
Scope
LocalRAG is intentionally a small portable Docker application.
The project does not attempt to provide:
Kubernetes security
Multi-cluster security
Enterprise IAM
Service-mesh security
Cloud perimeter controls
Multi-tenant isolation
Enterprise SIEM integration
Those controls are outside the intended scope.
Security Disclaimer
LocalRAG is a personal/open-source engineering project and should not
automatically be considered production-ready for security-sensitive
multi-user deployments.
Before exposing the application beyond a trusted local environment,
perform an independent security review appropriate to the deployment
environment.