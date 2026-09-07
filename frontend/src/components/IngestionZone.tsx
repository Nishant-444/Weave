import React, { useRef, useState } from "react";
import { UploadCloud, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { JobProgressEvent } from "@/types";

interface IngestionZoneProps {
  onUploadFile: (file: File) => Promise<void>;
  activeJob: JobProgressEvent | null;
  isUploading: boolean;
}

export const IngestionZone: React.FC<IngestionZoneProps> = ({
  onUploadFile,
  activeJob,
  isUploading,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      await onUploadFile(file);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      await onUploadFile(file);
      e.target.value = "";
    }
  };

  return (
    <Card className="border-border bg-card shadow-sm">
      <CardHeader className="pb-3 pt-4 px-4">
        <CardTitle className="font-poppins text-sm font-semibold flex items-center justify-between">
          <span>Document Ingestion</span>
          <div className="flex gap-1.5">
            <Badge variant="secondary" className="text-[10px] font-normal px-1.5 py-0">
              .PDF
            </Badge>
            <Badge variant="secondary" className="text-[10px] font-normal px-1.5 py-0">
              .CSV
            </Badge>
          </div>
        </CardTitle>
        <CardDescription className="text-xs">
          Drag & drop textbook PDFs or tabular CSVs for vectorization & dual SQL indexing.
        </CardDescription>
      </CardHeader>

      <CardContent className="px-4 pb-4 space-y-3">
        {/* Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 text-center cursor-pointer transition-colors ${
            isDragOver
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/30"
          } ${isUploading ? "opacity-50 pointer-events-none" : ""}`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,.csv"
            className="hidden"
          />
          <UploadCloud className="h-7 w-7 text-muted-foreground mb-1.5" />
          <p className="text-xs font-medium text-foreground">
            Click to upload or drag & drop
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            PDF (Page Chunks) • CSV (Dual Typed SQL + Row Embeddings)
          </p>
        </div>

        {/* Live SSE Ingestion Progress Box */}
        {activeJob && (
          <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-poppins font-medium flex items-center gap-1.5">
                {activeJob.stage === "done" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : activeJob.stage === "failed" ? (
                  <AlertCircle className="h-4 w-4 text-destructive" />
                ) : (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                )}
                <span className="capitalize">{activeJob.stage}...</span>
              </span>
              <span className="font-mono text-xs font-semibold">
                {activeJob.progress_percent}%
              </span>
            </div>

            {/* Stage Progress Bar */}
            <div className="w-full bg-secondary rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  activeJob.stage === "done"
                    ? "bg-emerald-600"
                    : activeJob.stage === "failed"
                    ? "bg-destructive"
                    : "bg-primary"
                }`}
                style={{ width: `${activeJob.progress_percent}%` }}
              />
            </div>

            {/* Progress Message */}
            <p className="text-[11px] text-muted-foreground leading-tight">
              {activeJob.message}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
