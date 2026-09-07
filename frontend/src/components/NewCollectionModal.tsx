import React, { useState } from "react";
import { X, Plus, Database, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface NewCollectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateCollection: (name: string, description?: string) => Promise<void>;
}

export const NewCollectionModal: React.FC<NewCollectionModalProps> = ({
  isOpen,
  onClose,
  onCreateCollection,
}) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await onCreateCollection(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create collection");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in-0">
      <div className="relative w-full max-w-md rounded-xl border border-border bg-card shadow-2xl p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary text-foreground">
              <Database className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-poppins text-sm font-bold text-foreground">
                Create Collection
              </h3>
              <p className="text-xs text-muted-foreground">
                Isolate documents and queries into a new tenant workspace.
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          {error && (
            <div className="p-2 rounded bg-destructive/10 border border-destructive/20 text-destructive text-xs">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-poppins font-medium text-foreground">
              Collection Name *
            </label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Financial Reports 2024"
              required
              className="text-xs"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-poppins font-medium text-foreground">
              Description (Optional)
            </label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Quarterly 10-K and 10-Q filings"
              className="text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
              className="text-xs font-poppins"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!name.trim() || isSubmitting}
              className="text-xs font-poppins"
            >
              {isSubmitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : (
                <Plus className="h-3.5 w-3.5 mr-1" />
              )}
              Create Workspace
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
