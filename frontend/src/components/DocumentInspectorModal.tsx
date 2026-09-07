import React, { useEffect, useState } from "react";
import { X, FileText, Table, Loader2, Database, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  DocumentItem,
  DocumentFullTextResponse,
  CSVSchemaResponse,
  CSVPreviewResponse,
} from "@/types";
import { apiUrl } from "@/lib/api";

interface DocumentInspectorModalProps {
  document: DocumentItem | null;
  onClose: () => void;
}

export const DocumentInspectorModal: React.FC<DocumentInspectorModalProps> = ({
  document,
  onClose,
}) => {
  const [loading, setLoading] = useState(true);
  const [pdfData, setPdfData] = useState<DocumentFullTextResponse | null>(null);
  const [csvSchema, setCsvSchema] = useState<CSVSchemaResponse | null>(null);
  const [csvPreview, setCsvPreview] = useState<CSVPreviewResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchFilter, setSearchFilter] = useState("");

  useEffect(() => {
    if (!document) return;
    setLoading(true);

    const fetchData = async () => {
      try {
        if (document.type === "pdf") {
          const res = await fetch(apiUrl(`/document/${document.id}/text`));
          if (res.ok) {
            const data: DocumentFullTextResponse = await res.json();
            setPdfData(data);
            setCurrentPage(1);
          }
        } else {
          // CSV Schema & Preview
          const [schemaRes, previewRes] = await Promise.all([
            fetch(apiUrl(`/document/${document.id}/csv-schema`)),
            fetch(apiUrl(`/document/${document.id}/csv-preview?limit=25`)),
          ]);
          if (schemaRes.ok) setCsvSchema(await schemaRes.json());
          if (previewRes.ok) setCsvPreview(await previewRes.json());
        }
      } catch (e) {
        console.error("Failed to inspect document:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [document]);

  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in-0">
      <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-xl border border-border bg-card shadow-2xl p-6 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary text-foreground">
              {document.type === "pdf" ? <FileText className="h-4 w-4" /> : <Table className="h-4 w-4" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-poppins text-sm font-bold text-foreground truncate max-w-md">
                  {document.filename}
                </h3>
                <Badge variant="outline" className="text-[10px] font-mono uppercase px-1.5 py-0">
                  {document.type}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {document.type === "pdf"
                  ? `${document.total_pages} extracted pages • Section 3.5 Full-Text View`
                  : `${document.total_pages} loaded rows • Section 3.3 PostgreSQL Dynamic Table`}
              </p>
            </div>
          </div>

          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto py-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <p className="text-xs">Loading document inspection data...</p>
            </div>
          ) : document.type === "pdf" && pdfData ? (
            /* PDF Full-Text Viewer */
            <div className="space-y-4">
              {/* Pagination Controls */}
              <div className="flex items-center justify-between bg-muted/40 p-2.5 rounded-lg border border-border/80">
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage <= 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    className="h-7 px-2 text-xs"
                  >
                    <ChevronLeft className="h-3.5 w-3.5 mr-1" /> Prev
                  </Button>
                  <span className="text-xs font-mono font-medium">
                    Page {currentPage} of {pdfData.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= pdfData.total_pages}
                    onClick={() => setCurrentPage((p) => Math.min(pdfData.total_pages, p + 1))}
                    className="h-7 px-2 text-xs"
                  >
                    Next <ChevronRight className="h-3.5 w-3.5 ml-1" />
                  </Button>
                </div>

                <div className="relative w-48">
                  <Input
                    placeholder="Filter page text..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="h-7 text-xs pr-7"
                  />
                  <Search className="h-3.5 w-3.5 absolute right-2 top-2 text-muted-foreground" />
                </div>
              </div>

              {/* Page Content Display */}
              <div className="p-4 rounded-lg bg-background border border-border min-h-[300px] text-xs font-mono leading-relaxed whitespace-pre-wrap text-foreground max-h-[420px] overflow-y-auto">
                {pdfData.pages.find((p) => p.page_num === currentPage)?.text ||
                  "No text extracted on this page."}
              </div>
            </div>
          ) : document.type === "csv" && csvSchema && csvPreview ? (
            /* CSV Schema & Table Preview */
            <div className="space-y-4">
              {/* Schema Columns Summary */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-poppins text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5" /> PostgreSQL Table:{" "}
                    <code className="font-mono font-normal text-muted-foreground">
                      {csvSchema.table_name}
                    </code>
                  </h4>
                  <span className="text-xs text-muted-foreground font-mono">
                    {csvSchema.row_count} Total Rows
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {csvSchema.column_definitions.map((col, idx) => (
                    <Badge
                      key={idx}
                      variant="secondary"
                      className="text-[11px] font-mono px-2 py-0.5"
                    >
                      <span className="font-semibold text-foreground">{col.name}</span>
                      <span className="text-muted-foreground ml-1 text-[10px]">
                        ({col.data_type})
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Raw Data Preview Table */}
              <div className="rounded-lg border border-border overflow-hidden">
                <div className="max-h-72 overflow-x-auto overflow-y-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-muted/80 sticky top-0 border-b border-border">
                      <tr>
                        {csvPreview.columns.map((col, idx) => (
                          <th
                            key={idx}
                            className="p-2 font-mono font-semibold text-foreground uppercase tracking-wider text-[10px]"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60 bg-background font-mono text-[11px]">
                      {csvPreview.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-muted/30">
                          {csvPreview.columns.map((col, cIdx) => (
                            <td key={cIdx} className="p-2 truncate max-w-[200px]" title={String(row[col] ?? "")}>
                              {String(row[col] ?? "null")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground text-center py-8">
              No preview data available for this document.
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-border flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose} className="text-xs font-poppins">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
