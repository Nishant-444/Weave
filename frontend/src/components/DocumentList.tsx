import React from "react";
import { FileText, Table, Trash2, Eye, HardDrive } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DocumentItem } from "@/types";

interface DocumentListProps {
  documents: DocumentItem[];
  onInspectDoc: (doc: DocumentItem) => void;
  onDeleteDoc: (docId: string) => Promise<void>;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  onInspectDoc,
  onDeleteDoc,
}) => {
  const formatFileSize = (bytes: number) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  return (
    <Card className="border-border bg-card shadow-sm flex flex-col flex-1">
      <CardHeader className="pb-3 pt-4 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="font-poppins text-sm font-semibold flex items-center gap-1.5">
            <HardDrive className="h-4 w-4 text-muted-foreground" />
            <span>Indexed Documents</span>
          </CardTitle>
          <Badge variant="outline" className="text-xs font-mono">
            {documents.length}
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Documents isolated within active collection.
        </CardDescription>
      </CardHeader>

      <CardContent className="px-4 pb-4 flex-1 overflow-y-auto max-h-[380px] space-y-2">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
            <p className="text-xs font-medium">No documents in this collection.</p>
            <p className="text-[11px] mt-0.5">Upload a PDF or CSV above to begin.</p>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="group flex items-center justify-between p-2.5 rounded-lg border border-border/80 bg-background hover:bg-muted/30 transition-colors"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-secondary text-secondary-foreground mt-0.5">
                  {doc.type === "pdf" ? (
                    <FileText className="h-3.5 w-3.5 text-foreground" />
                  ) : (
                    <Table className="h-3.5 w-3.5 text-foreground" />
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground truncate max-w-[180px]" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px] text-muted-foreground">
                    <span>
                      {doc.type === "pdf" ? `${doc.total_pages} pages` : `${doc.total_pages} rows`}
                    </span>
                    <span>•</span>
                    <span>{doc.chunk_count} chunks</span>
                    <span>•</span>
                    <span>{formatFileSize(doc.file_size)}</span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  onClick={() => onInspectDoc(doc)}
                  title={doc.type === "pdf" ? "View Full Extracted Text" : "View SQL Schema & Data"}
                >
                  <Eye className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  onClick={() => onDeleteDoc(doc.id)}
                  title="Delete Document"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
};
