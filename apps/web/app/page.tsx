"use client";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

type Source = {
  document_id: string;
  filename: string;
  chunk_id: number;
  score: number;
};

type ChatResponse = {
  answer: string;
  sources: Source[];
};

type Document = {
  document_id: string;
  filename: string;
  content_type: string;
  chunks: number;
};

type DocumentListResponse = {
  documents: Document[];
};

type UploadResponse = {
  document_id: string;
  filename: string;
  chunks: number;
  status: string;
};

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

const ALLOWED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".md",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>(
    []
  );

  const [question, setQuestion] = useState("");

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] = useState<
    string | null
  >(null);

  const [documents, setDocuments] = useState<
    Document[]
  >([]);

  const [documentsLoading, setDocumentsLoading] =
    useState(true);

  const [uploading, setUploading] =
    useState(false);

  const [deletingDocumentId, setDeletingDocumentId] =
    useState<string | null>(null);

  const [documentError, setDocumentError] =
    useState<string | null>(null);

  const fileInputRef =
    useRef<HTMLInputElement | null>(null);

  async function loadDocuments() {
    setDocumentsLoading(true);
    setDocumentError(null);

    try {
      const response = await fetch(
        `${API_URL}/documents`
      );

      if (!response.ok) {
        throw new Error(
          "Failed to load documents."
        );
      }

      const data =
        (await response.json()) as DocumentListResponse;

      setDocuments(data.documents);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to load documents.";

      setDocumentError(message);
    } finally {
      setDocumentsLoading(false);
    }
  }

    useEffect(() => {
      // Loading documents on mount intentionally updates component state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDocuments();
  }, []);

  async function sendMessage(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const trimmedQuestion =
      question.trim();

    if (!trimmedQuestion || isLoading) {
      return;
    }

    setError(null);

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setQuestion("");
    setIsLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question: trimmedQuestion,
            top_k: 5,
          }),
        }
      );

      if (!response.ok) {
        let detail =
          "Unable to get a response from LocalRAG.";

        try {
          const errorBody =
            await response.json();

          if (
            typeof errorBody.detail ===
            "string"
          ) {
            detail = errorBody.detail;
          }
        } catch {
          // Keep default error.
        }

        throw new Error(detail);
      }

      const data =
        (await response.json()) as ChatResponse;

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.answer,
        sources: data.sources,
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Something went wrong.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  function openFilePicker() {
    if (uploading) {
      return;
    }

    fileInputRef.current?.click();
  }

  async function handleFileChange(
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];

    event.target.value = "";

    if (!file) {
      return;
    }

    await uploadDocument(file);
  }

  async function uploadDocument(file: File) {
    const extension = `.${file.name
      .split(".")
      .pop()
      ?.toLowerCase()}`;

    if (
      !ALLOWED_EXTENSIONS.includes(
        extension
      )
    ) {
      setDocumentError(
        "Unsupported file type. Use PDF, DOCX, TXT, or MD."
      );
      return;
    }

    setUploading(true);
    setDocumentError(null);

    try {
      const formData = new FormData();

      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/documents/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        let detail =
          "Document upload failed.";

        try {
          const errorBody =
            await response.json();

          if (
            typeof errorBody.detail ===
            "string"
          ) {
            detail = errorBody.detail;
          }
        } catch {
          // Keep default error.
        }

        throw new Error(detail);
      }

      const data =
        (await response.json()) as UploadResponse;

      await loadDocuments();

      setDocumentError(null);

      console.log(
        `Indexed ${data.filename} (${data.chunks} chunks)`
      );
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Document upload failed.";

      setDocumentError(message);
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(
    documentId: string
  ) {
    if (deletingDocumentId) {
      return;
    }

    const confirmed =
      window.confirm(
        "Delete this document and all of its indexed chunks?"
      );

    if (!confirmed) {
      return;
    }

    setDeletingDocumentId(documentId);
    setDocumentError(null);

    try {
      const response = await fetch(
        `${API_URL}/documents/${documentId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        let detail =
          "Failed to delete document.";

        try {
          const errorBody =
            await response.json();

          if (
            typeof errorBody.detail ===
            "string"
          ) {
            detail = errorBody.detail;
          }
        } catch {
          // Keep default error.
        }

        throw new Error(detail);
      }

      await loadDocuments();
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Failed to delete document.";

      setDocumentError(message);
    } finally {
      setDeletingDocumentId(null);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="app-header">
          <div>
            <p className="eyebrow">
              LOCALRAG
            </p>

            <h1>Ask your documents.</h1>

            <p className="subtitle">
              Private, local document retrieval
              powered by Ollama and Qdrant.
            </p>
          </div>

          <div className="status-pill">
            <span className="status-dot" />
            Local
          </div>
        </header>

        <div className="workspace-grid">
          <aside className="documents-panel">
            <div className="panel-header">
              <div>
                <h2>Documents</h2>

                <p>
                  {documents.length}{" "}
                  {documents.length === 1
                    ? "document"
                    : "documents"}
                </p>
              </div>

              <button
                type="button"
                className="upload-button"
                onClick={openFilePicker}
                disabled={uploading}
              >
                {uploading
                  ? "Indexing..."
                  : "+ Upload"}
              </button>

              <input
                ref={fileInputRef}
                type="file"
                className="hidden-file-input"
                accept=".pdf,.docx,.txt,.md"
                onChange={handleFileChange}
              />
            </div>

            {documentError && (
              <div className="document-error">
                {documentError}
              </div>
            )}

            <div className="document-list">
              {documentsLoading ? (
                <div className="documents-empty">
                  Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="documents-empty">
                  <div className="documents-empty-icon">
                    +
                  </div>

                  <strong>
                    No documents yet
                  </strong>

                  <span>
                    Upload a document to start
                    asking questions.
                  </span>
                </div>
              ) : (
                documents.map((document) => (
                  <article
                    className="document-card"
                    key={document.document_id}
                  >
                    <div className="document-icon">
                      DOC
                    </div>

                    <div className="document-info">
                      <span className="document-name">
                        {document.filename}
                      </span>

                      <span className="document-meta">
                        {document.chunks}{" "}
                        {document.chunks === 1
                          ? "chunk"
                          : "chunks"}
                      </span>
                    </div>

                    <button
                      type="button"
                      className="delete-button"
                      aria-label={`Delete ${document.filename}`}
                      title={`Delete ${document.filename}`}
                      disabled={
                        deletingDocumentId ===
                        document.document_id
                      }
                      onClick={() =>
                        void deleteDocument(
                          document.document_id
                        )
                      }
                    >
                      {deletingDocumentId ===
                      document.document_id
                        ? "..."
                        : "×"}
                    </button>
                  </article>
                ))
              )}
            </div>

            <div className="upload-hint">
              Supported: PDF, DOCX, TXT, MD
            </div>
          </aside>

          <section className="chat-panel">
            {messages.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  ⌕
                </div>

                <h2>
                  Ask something about your
                  documents
                </h2>

                <p>
                  LocalRAG will retrieve
                  relevant document chunks
                  and use them as context for
                  the answer.
                </p>

                <div className="suggestions">
                  <button
                    type="button"
                    onClick={() =>
                      setQuestion(
                        "What does LocalRAG use for vector storage?"
                      )
                    }
                  >
                    What does LocalRAG use
                    for vector storage?
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      setQuestion(
                        "How does LocalRAG retrieve relevant documents?"
                      )
                    }
                  >
                    How does document
                    retrieval work?
                  </button>
                </div>
              </div>
            ) : (
              <div className="messages">
                {messages.map((message) => (
                  <article
                    key={message.id}
                    className={`message ${
                      message.role === "user"
                        ? "message-user"
                        : "message-assistant"
                    }`}
                  >
                    <div className="message-label">
                      {message.role ===
                      "user"
                        ? "You"
                        : "LocalRAG"}
                    </div>

                    <div className="message-content">
                      {message.content}
                    </div>

                    {message.role ===
                      "assistant" &&
                      message.sources &&
                      message.sources.length >
                        0 && (
                        <div className="sources">
                          <div className="sources-title">
                            Sources
                          </div>

                          <div className="source-list">
                            {message.sources.map(
                              (
                                source,
                                index
                              ) => (
                                <div
                                  className="source-card"
                                  key={`${source.document_id}-${source.chunk_id}-${index}`}
                                >
                                  <div className="source-icon">
                                    DOC
                                  </div>

                                  <div className="source-info">
                                    <span className="source-name">
                                      {
                                        source.filename
                                      }
                                    </span>

                                    <span className="source-meta">
                                      Chunk{" "}
                                      {
                                        source.chunk_id
                                      }
                                      {" · "}
                                      Score{" "}
                                      {source.score.toFixed(
                                        2
                                      )}
                                    </span>
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )}
                  </article>
                ))}

                {isLoading && (
                  <article className="message message-assistant">
                    <div className="message-label">
                      LocalRAG
                    </div>

                    <div className="typing-indicator">
                      <span />
                      <span />
                      <span />
                    </div>
                  </article>
                )}
              </div>
            )}

            {error && (
              <div className="error-banner">
                <strong>
                  Request failed.
                </strong>

                <span>{error}</span>
              </div>
            )}

            <form
              className="composer"
              onSubmit={sendMessage}
            >
              <textarea
                value={question}
                onChange={(event) =>
                  setQuestion(
                    event.target.value
                  )
                }
                placeholder="Ask your documents..."
                rows={1}
                disabled={isLoading}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey
                  ) {
                    event.preventDefault();

                    if (
                      question.trim() &&
                      !isLoading
                    ) {
                      event.currentTarget.form?.requestSubmit();
                    }
                  }
                }}
              />

              <button
                type="submit"
                className="send-button"
                disabled={
                  !question.trim() ||
                  isLoading
                }
              >
                {isLoading ? "..." : "Send"}
              </button>
            </form>

            <p className="composer-hint">
              Press Enter to send · Shift +
              Enter for a new line
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}