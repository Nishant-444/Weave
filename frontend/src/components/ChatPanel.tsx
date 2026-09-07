import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Sparkles, Terminal, Code2, Bot, User, Layers, FileText, Table } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ChatMessage, Citation } from "@/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (query: string) => Promise<void>;
  onOpenCitation: (citation: Citation) => void;
  isStreaming: boolean;
  collectionName: string;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  onSendMessage,
  onOpenCitation,
  isStreaming,
  collectionName,
}) => {
  const [inputQuery, setInputQuery] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const suggestedPrompts = [
    {
      title: "Book Authors (PDFs)",
      query: "Who is the author of both the books?",
      type: "semantic",
    },
    {
      title: "Algorithm Techniques (PDF)",
      query: "What are the common algorithmic problem solving techniques?",
      type: "semantic",
    },
    {
      title: "Financial Aggregation (CSV)",
      query: "What is the total revenue and average operating margin for Apex Systems across all quarters?",
      type: "sql",
    },
    {
      title: "Multi-Condition Ranking (CSV)",
      query: "Which top 3 companies had the highest R&D spend in 2024?",
      type: "sql",
    },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim() || isStreaming) return;
    const query = inputQuery.trim();
    setInputQuery("");
    await onSendMessage(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Helper to parse text nodes and embed interactive citation badges like [1], [2] or 【4†...】
  const parseInlineCitations = (text: string, citations?: Citation[]) => {
    if (!text) return text;

    // Normalize any OpenAI internal grounding markers like 【4†L1-L4】 into clean [4]
    const normalizedText = text.replace(/【(\d+)[^】]*】/g, "[$1]");

    if (!citations || citations.length === 0) return normalizedText;

    const parts = normalizedText.split(/(\[\d+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const citId = parseInt(match[1], 10);
        const foundCit = citations.find((c) => c.id === citId);
        if (foundCit) {
          return (
            <button
              key={idx}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenCitation(foundCit);
              }}
              className="inline-flex items-center gap-0.5 mx-0.5 px-1.5 py-0.5 rounded border border-border bg-secondary text-foreground text-[11px] font-mono font-semibold hover:bg-primary hover:text-primary-foreground transition-all cursor-pointer shadow-2xs"
              title={`View Source: ${foundCit.source_file} (Page ${foundCit.page_num || "N/A"})`}
            >
              [{citId}]
            </button>
          );
        }
      }
      return part;
    });
  };

  // Custom Markdown renderer with citations support
  const renderMessageContent = (content: string, citations?: Citation[]) => {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="mb-2.5 last:mb-0 leading-relaxed text-xs sm:text-sm">
              {React.Children.map(children, (child) =>
                typeof child === "string" ? parseInlineCitations(child, citations) : child
              )}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">
              {React.Children.map(children, (child) =>
                typeof child === "string" ? parseInlineCitations(child, citations) : child
              )}
            </strong>
          ),
          li: ({ children }) => (
            <li className="mb-1.5 leading-relaxed text-xs sm:text-sm">
              {React.Children.map(children, (child) =>
                typeof child === "string" ? parseInlineCitations(child, citations) : child
              )}
            </li>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 my-2 space-y-1 text-xs sm:text-sm">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 my-2 space-y-1 text-xs sm:text-sm">
              {children}
            </ol>
          ),
          h1: ({ children }) => <h1 className="font-poppins text-base font-bold my-2">{children}</h1>,
          h2: ({ children }) => <h2 className="font-poppins text-sm font-bold my-2">{children}</h2>,
          h3: ({ children }) => <h3 className="font-poppins text-xs font-semibold my-1.5">{children}</h3>,
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 rounded border border-border">
              <table className="min-w-full divide-y divide-border text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="bg-muted px-2.5 py-1.5 font-mono font-medium text-left">{children}</th>,
          td: ({ children }) => <td className="px-2.5 py-1.5 border-t border-border/60">{children}</td>,
          code: ({ children }) => (
            <code className="px-1.5 py-0.5 rounded bg-muted font-mono text-[11px] border border-border/60">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    );
  };

  return (
    <div className="flex flex-col h-full bg-background border border-border rounded-xl shadow-sm overflow-hidden">
      {/* Chat Messages Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12 px-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-secondary-foreground mb-3">
              <Sparkles className="h-6 w-6 text-foreground" />
            </div>
            <h2 className="font-poppins text-lg font-bold text-foreground">
              Ask anything across your PDFs & CSVs
            </h2>
            <p className="text-xs text-muted-foreground max-w-md mt-1 mb-6">
              Weave automatically routes queries to vector similarity search for qualitative concepts, or executes exact SQL aggregations on PostgreSQL for tabular data.
            </p>

            {/* Suggested Benchmark Prompts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 w-full max-w-xl text-left">
              {suggestedPrompts.map((p, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    setInputQuery(p.query);
                    textareaRef.current?.focus();
                  }}
                  className="p-3 rounded-lg border border-border/80 bg-card hover:bg-muted/40 hover:border-primary/40 cursor-pointer transition-all space-y-1 shadow-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-poppins font-semibold text-foreground">
                      {p.title}
                    </span>
                    <Badge variant="outline" className="text-[9px] font-mono uppercase px-1 py-0">
                      {p.type}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    "{p.query}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground mt-0.5 shadow-xs">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div
                className={`flex flex-col max-w-[85%] rounded-xl px-4 py-3 shadow-xs ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground ml-auto"
                    : "bg-card border border-border text-card-foreground"
                }`}
              >
                {/* Routing Badge for Assistant */}
                {msg.role === "assistant" && msg.route && (
                  <div className="flex items-center gap-2 mb-2 pb-1.5 border-b border-border/60">
                    <Badge
                      variant="secondary"
                      className="text-[10px] font-poppins uppercase tracking-wider font-semibold gap-1 px-1.5 py-0"
                    >
                      {msg.route === "sql" ? (
                        <>
                          <Terminal className="h-3 w-3" />
                          SQL Aggregation Path
                        </>
                      ) : (
                        <>
                          <Layers className="h-3 w-3" />
                          Semantic RAG Path
                        </>
                      )}
                    </Badge>
                    {msg.routeReason && (
                      <span className="text-[11px] text-muted-foreground truncate" title={msg.routeReason}>
                        {msg.routeReason}
                      </span>
                    )}
                  </div>
                )}

                {/* Message Text Content */}
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {msg.content ? (
                    renderMessageContent(msg.content, msg.citations)
                  ) : msg.isStreaming ? (
                    <div className="flex items-center gap-1.5 py-1.5 text-muted-foreground text-xs font-poppins">
                      <span className="h-2 w-2 rounded-full bg-primary/70 animate-bounce [animation-delay:-0.3s]" />
                      <span className="h-2 w-2 rounded-full bg-primary/70 animate-bounce [animation-delay:-0.15s]" />
                      <span className="h-2 w-2 rounded-full bg-primary/70 animate-bounce" />
                      <span className="ml-2 text-xs text-muted-foreground font-mono">Generating response...</span>
                    </div>
                  ) : null}
                </div>

                {/* Executed SQL Query Display */}
                {msg.sqlQuery && (
                  <div className="mt-2.5 pt-2 border-t border-border/60">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground mb-1 font-mono">
                      <span className="flex items-center gap-1">
                        <Code2 className="h-3.5 w-3.5" /> Executed PostgreSQL Query:
                      </span>
                    </div>
                    <pre className="p-2 rounded bg-muted/60 text-[11px] font-mono text-foreground overflow-x-auto border border-border/60">
                      <code>{msg.sqlQuery}</code>
                    </pre>
                  </div>
                )}

                {/* Citations Footer */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-border/60 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] font-semibold text-muted-foreground font-poppins uppercase">
                      Sources:
                    </span>
                    {msg.citations.map((cit) => (
                      <button
                        key={cit.id}
                        type="button"
                        onClick={() => onOpenCitation(cit)}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-border bg-secondary hover:bg-muted text-[11px] font-medium text-foreground transition-colors cursor-pointer"
                      >
                        {cit.type === "pdf" ? (
                          <FileText className="h-3 w-3" />
                        ) : cit.type === "csv_row" ? (
                          <Table className="h-3 w-3" />
                        ) : (
                          <Terminal className="h-3 w-3" />
                        )}
                        <span>[{cit.id}]</span>
                        <span className="truncate max-w-[120px]">
                          {cit.source_file}
                        </span>
                        {cit.page_num && (
                          <span className="text-muted-foreground">
                            p.{cit.page_num}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {msg.role === "user" && (
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground mt-0.5">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-3 border-t border-border bg-card/60">
        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <div className="relative flex-1">
            <Textarea
              ref={textareaRef}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask Weave anything about documents in '${collectionName}'... (Press Enter to send)`}
              className="min-h-[44px] max-h-32 resize-none text-xs pr-10 py-2.5 bg-background border-border shadow-xs focus-visible:ring-1"
              rows={1}
            />
          </div>
          <Button
            type="submit"
            size="icon"
            disabled={!inputQuery.trim() || isStreaming}
            className="h-11 w-11 shrink-0 rounded-lg shadow-xs"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
};
