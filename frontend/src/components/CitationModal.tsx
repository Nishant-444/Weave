import React from "react";
import { X, FileText, Table, Terminal, Hash, Bookmark } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Citation } from "@/types";

interface CitationModalProps {
  citation: Citation | null;
  onClose: () => void;
}

export const CitationModal: React.FC<CitationModalProps> = ({ citation, onClose }) => {
  if (!citation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in-0">
      <div className="relative w-full max-w-xl rounded-xl border border-border bg-card shadow-2xl p-6 space-y-4">
        {/* Modal Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary text-foreground">
              {citation.type === "pdf" ? (
                <FileText className="h-4 w-4" />
              ) : citation.type === "csv_row" ? (
                <Table className="h-4 w-4" />
              ) : (
                <Terminal className="h-4 w-4" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-poppins text-sm font-bold text-foreground">
                  Citation [{citation.id}]
                </h3>
                <Badge variant="outline" className="text-[10px] font-mono uppercase px-1.5 py-0">
                  {citation.type.replace("_", " ")}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground truncate max-w-sm">
                {citation.source_file}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Citation Metadata Details */}
        <div className="grid grid-cols-2 gap-2 text-xs bg-muted/40 p-3 rounded-lg border border-border/80">
          <div className="flex items-center gap-1.5">
            <Bookmark className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">Location:</span>
            <span className="font-semibold text-foreground">
              {citation.type === "pdf"
                ? `Page ${citation.page_num || "N/A"}`
                : citation.type === "csv_row"
                ? `Row ${citation.page_num || "N/A"}`
                : "PostgreSQL Database"}
            </span>
          </div>

          {citation.char_offset !== null && citation.char_offset !== undefined && (
            <div className="flex items-center gap-1.5">
              <Hash className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">Char Offset:</span>
              <span className="font-mono font-medium text-foreground">
                {citation.char_offset}
              </span>
            </div>
          )}
        </div>

        {/* SQL Query if applicable */}
        {citation.sql_query && (
          <div className="space-y-1.5">
            <h4 className="text-xs font-poppins font-semibold text-foreground flex items-center gap-1">
              <Terminal className="h-3.5 w-3.5" /> Executed SQL Query
            </h4>
            <pre className="p-3 rounded-lg bg-background text-xs font-mono text-foreground overflow-x-auto border border-border">
              <code>{citation.sql_query}</code>
            </pre>
          </div>
        )}

        {/* Snippet Context */}
        <div className="space-y-1.5">
          <h4 className="text-xs font-poppins font-semibold text-foreground">
            Extracted Ground Truth Snippet:
          </h4>
          <div className="p-3 rounded-lg bg-background border border-border text-xs leading-relaxed text-foreground whitespace-pre-wrap max-h-60 overflow-y-auto">
            {citation.snippet}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2">
          <Button variant="outline" size="sm" onClick={onClose} className="text-xs font-poppins">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
