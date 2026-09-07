import { useState, useEffect } from "react";
import { Header } from "@/components/Header";
import { IngestionZone } from "@/components/IngestionZone";
import { DocumentList } from "@/components/DocumentList";
import { ChatPanel } from "@/components/ChatPanel";
import { CitationModal } from "@/components/CitationModal";
import { DocumentInspectorModal } from "@/components/DocumentInspectorModal";
import { NewCollectionModal } from "@/components/NewCollectionModal";
import {
  Collection,
  DocumentItem,
  ChatMessage,
  Citation,
  JobProgressEvent,
} from "@/types";
import { apiUrl } from "@/lib/api";

export function App() {
  // State
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeCollection, setActiveCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Ingestion State
  const [activeJob, setActiveJob] = useState<JobProgressEvent | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Streaming State
  const [isStreaming, setIsStreaming] = useState(false);

  // Modals
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [inspectingDoc, setInspectingDoc] = useState<DocumentItem | null>(null);
  const [isNewCollectionOpen, setIsNewCollectionOpen] = useState(false);

  // 1. Initial Load: Collections
  useEffect(() => {
    fetchCollections();
  }, []);

  // 2. Fetch documents when activeCollection changes
  useEffect(() => {
    if (activeCollection) {
      fetchDocuments(activeCollection.id);
    }
  }, [activeCollection]);

  const fetchCollections = async () => {
    try {
      const res = await fetch(apiUrl("/collections"));
      if (res.ok) {
        const data: Collection[] = await res.json();
        setCollections(data);
        if (data.length > 0 && !activeCollection) {
          const defaultCol = data.find((c) => c.name === "Default") || data[0];
          setActiveCollection(defaultCol);
        }
      }
    } catch (e) {
      console.error("Failed to fetch collections:", e);
    }
  };

  const fetchDocuments = async (colId: string) => {
    try {
      const res = await fetch(apiUrl(`/documents?collection_id=${colId}`));
      if (res.ok) {
        const data: DocumentItem[] = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error("Failed to fetch documents:", e);
    }
  };

  // 3. Upload File Handler
  const handleUploadFile = async (file: File) => {
    if (!activeCollection) return;
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("collection_id", activeCollection.id);

    try {
      const res = await fetch(apiUrl("/upload"), {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const uploadData = await res.json();
      const jobId = uploadData.job_id;

      // Subscribe to live SSE progress stream
      const eventSource = new EventSource(apiUrl(`/ingest/progress/${jobId}`));

      eventSource.addEventListener("progress", (e) => {
        try {
          const progress: JobProgressEvent = JSON.parse(e.data);
          setActiveJob(progress);

          if (progress.stage === "done" || progress.stage === "failed") {
            eventSource.close();
            setIsUploading(false);
            fetchDocuments(activeCollection.id);
            setTimeout(() => setActiveJob(null), 5000);
          }
        } catch (err) {
          console.error("Error parsing SSE event:", err);
        }
      });

      eventSource.onerror = () => {
        eventSource.close();
        setIsUploading(false);
        fetchDocuments(activeCollection.id);
      };
    } catch (err: any) {
      console.error("Upload error:", err);
      setIsUploading(false);
      alert(err.message || "Failed to upload document");
    }
  };

  // 4. Delete Document Handler
  const handleDeleteDoc = async (docId: string) => {
    if (!confirm("Are you sure you want to delete this document and all its chunks/tables?")) {
      return;
    }
    try {
      const res = await fetch(apiUrl(`/document/${docId}`), { method: "DELETE" });
      if (res.ok && activeCollection) {
        fetchDocuments(activeCollection.id);
      }
    } catch (e) {
      console.error("Failed to delete document:", e);
    }
  };

  // 5. Create Collection Handler
  const handleCreateCollection = async (name: string, description?: string) => {
    const res = await fetch(apiUrl("/collections"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to create collection");
    }

    const newCol: Collection = await res.json();
    setCollections((prev) => [...prev, newCol]);
    setActiveCollection(newCol);
  };

  // 6. Send Chat Message (SSE Streaming)
  const handleSendMessage = async (query: string) => {
    if (!activeCollection || isStreaming) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };

    const assistantMessageId = crypto.randomUUID();
    const initialAssistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);
    setIsStreaming(true);

    try {
      const response = await fetch(apiUrl("/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          collection_id: activeCollection.id,
        }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body stream");
      }

      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const normalized = buffer.replace(/\r\n/g, "\n");
        const blocks = normalized.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (!block.trim()) continue;

          let eventType = "message";
          let dataStr = "";

          const blockLines = block.split("\n");
          for (const line of blockLines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("event:")) {
              eventType = trimmed.replace("event:", "").trim();
            } else if (trimmed.startsWith("data:")) {
              dataStr = trimmed.replace("data:", "").trim();
            }
          }

          if (!dataStr) continue;

          try {
            const parsed = JSON.parse(dataStr);

            if (eventType === "routing") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, route: parsed.route, routeReason: parsed.reason }
                    : msg
                )
              );
            } else if (eventType === "token") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: msg.content + parsed.token }
                    : msg
                )
              );
            } else if (eventType === "citations") {
              const citList: Citation[] = parsed.citations || [];
              const sqlCit = citList.find((c) => c.type === "sql_query");
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        citations: citList,
                        sqlQuery: sqlCit?.sql_query || null,
                      }
                    : msg
                )
              );
            } else if (eventType === "error") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        content: parsed.error || "An error occurred while generating the response.",
                        isStreaming: false,
                      }
                    : msg
                )
              );
            } else if (eventType === "done") {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? { ...msg, isStreaming: false }
                    : msg
                )
              );
            }
          } catch {
            // Ignore non-JSON raw strings
          }
        }
      }
    } catch (err: any) {
      console.error("Chat error:", err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: `Error: ${err.message || "Unable to retrieve response."}`,
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex h-screen w-screen flex-col bg-background text-foreground overflow-hidden font-sans">
      {/* Top Navbar */}
      <Header
        collections={collections}
        activeCollection={activeCollection}
        onSelectCollection={setActiveCollection}
        onOpenNewCollection={() => setIsNewCollectionOpen(true)}
        onClearChat={() => setMessages([])}
      />

      {/* Main Two-Pane Workspace */}
      <main className="flex flex-1 overflow-hidden p-4 gap-4">
        {/* Left Pane: Ingestion & Document Explorer (Fixed Width) */}
        <div className="w-full lg:w-[400px] xl:w-[430px] flex flex-col gap-4 shrink-0 overflow-y-auto">
          <IngestionZone
            onUploadFile={handleUploadFile}
            activeJob={activeJob}
            isUploading={isUploading}
          />
          <DocumentList
            documents={documents}
            onInspectDoc={setInspectingDoc}
            onDeleteDoc={handleDeleteDoc}
          />
        </div>

        {/* Right Pane: Interactive RAG Chat (Fluid) */}
        <div className="flex-1 flex flex-col h-full min-w-0">
          <ChatPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            onOpenCitation={setSelectedCitation}
            isStreaming={isStreaming}
            collectionName={activeCollection?.name || "Default"}
          />
        </div>
      </main>

      {/* Modals & Drawers */}
      <CitationModal
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
      <DocumentInspectorModal
        document={inspectingDoc}
        onClose={() => setInspectingDoc(null)}
      />
      <NewCollectionModal
        isOpen={isNewCollectionOpen}
        onClose={() => setIsNewCollectionOpen(false)}
        onCreateCollection={handleCreateCollection}
      />
    </div>
  );
}

export default App;
