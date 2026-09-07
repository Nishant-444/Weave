export interface Collection {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
}

export interface DocumentItem {
  id: string;
  collection_id: string;
  filename: string;
  type: "pdf" | "csv";
  status: "processing" | "completed" | "failed";
  total_pages: number; // page count for PDF, row count for CSV
  file_size: number;
  error?: string | null;
  uploaded_at: string;
  chunk_count: number;
}

export interface JobProgressEvent {
  job_id: string;
  document_id: string;
  stage: "queued" | "parsing" | "chunking" | "embedding" | "storing" | "done" | "failed";
  progress_percent: number;
  message: string;
  total_pages?: number;
  total_chunks?: number;
  error?: string | null;
}

export interface Citation {
  id: number;
  document_id: string;
  source_file: string;
  type: "pdf" | "csv_row" | "sql_query";
  page_num?: number | null;
  char_offset?: number | null;
  snippet: string;
  sql_query?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  route?: "semantic" | "sql";
  routeReason?: string;
  citations?: Citation[];
  sqlQuery?: string | null;
  isStreaming?: boolean;
  timestamp: string;
}

export interface ColumnDefinition {
  name: string;
  original_name: string;
  data_type: string;
}

export interface CSVSchemaResponse {
  document_id: string;
  collection_id: string;
  table_name: string;
  row_count: number;
  column_definitions: ColumnDefinition[];
  created_at: string;
}

export interface CSVPreviewResponse {
  document_id: string;
  table_name: string;
  total_rows: number;
  columns: string[];
  rows: Record<string, any>[];
}

export interface DocumentPage {
  page_num: number;
  text: string;
}

export interface DocumentFullTextResponse {
  document_id: string;
  filename: string;
  total_pages: number;
  pages: DocumentPage[];
}
