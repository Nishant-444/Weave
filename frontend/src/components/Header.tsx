import React from "react";
import { Layers, Plus, Database, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Collection } from "@/types";

interface HeaderProps {
  collections: Collection[];
  activeCollection: Collection | null;
  onSelectCollection: (col: Collection) => void;
  onOpenNewCollection: () => void;
  onClearChat: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  collections,
  activeCollection,
  onSelectCollection,
  onOpenNewCollection,
  onClearChat,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex h-14 w-full items-center justify-between px-6">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <Layers className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-poppins text-lg font-bold tracking-tight text-foreground">
              Weave
            </span>
            <Badge variant="outline" className="text-[10px] font-medium text-muted-foreground px-1.5 py-0">
              v1.0
            </Badge>
          </div>
        </div>

        {/* Center: Collection Switcher */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground shadow-sm">
            <Database className="h-3.5 w-3.5 text-foreground" />
            <span className="font-medium text-foreground">Collection:</span>
            <select
              value={activeCollection?.id || ""}
              onChange={(e) => {
                const selected = collections.find((c) => c.id === e.target.value);
                if (selected) onSelectCollection(selected);
              }}
              className="bg-transparent font-medium text-foreground outline-none cursor-pointer hover:underline"
            >
              {collections.map((c) => (
                <option key={c.id} value={c.id} className="bg-popover text-popover-foreground">
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onOpenNewCollection}
            className="h-8 gap-1 text-xs font-poppins"
          >
            <Plus className="h-3.5 w-3.5" />
            New Collection
          </Button>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearChat}
            className="h-8 text-xs text-muted-foreground hover:text-foreground gap-1.5"
            title="Clear Chat History"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </Button>
        </div>
      </div>
    </header>
  );
};
