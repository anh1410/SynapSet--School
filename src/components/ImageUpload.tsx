import { useRef, useState } from "react";
import { ImagePlus, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MAX_UPLOAD_BYTES, formatBytes, uploadImage, useImageUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Picks a picture, uploads it right away and reports the stored image id.
 *  `compact` is the small square used per item in a picture worksheet. */
export function ImageUpload({
  imageId,
  onChange,
  compact = false,
  label = "Add picture",
}: {
  imageId: string | null;
  onChange: (imageId: string | null) => void;
  compact?: boolean;
  label?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const url = useImageUrl(imageId);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    if (!file.type.startsWith("image/")) {
      setError("That file isn't a picture.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(`Too large (${formatBytes(file.size)}). The limit is ${formatBytes(MAX_UPLOAD_BYTES)}.`);
      return;
    }
    setBusy(true);
    try {
      const res = await uploadImage(file);
      onChange(res.image_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const picker = (
    <input
      ref={inputRef}
      type="file"
      accept="image/png,image/jpeg,image/webp,image/gif"
      className="hidden"
      onChange={(e) => handleFile(e.target.files?.[0])}
    />
  );

  if (compact) {
    return (
      <div>
        {picker}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          title={imageId ? "Replace picture" : label}
          className={cn(
            "relative flex h-20 w-full items-center justify-center overflow-hidden rounded-md border border-dashed border-border bg-secondary/40 text-muted-foreground hover:border-primary/50",
            imageId && "border-solid"
          )}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : url ? (
            <img src={url} alt="" className="h-full w-full object-contain" />
          ) : (
            <ImagePlus className="h-5 w-5" />
          )}
        </button>
        {error && <p className="mt-1 text-[11px] text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {picker}
      {imageId && url && (
        <div className="relative inline-block">
          <img src={url} alt="Your diagram" className="max-h-48 max-w-xs rounded-md border border-border" />
          <button
            type="button"
            onClick={() => onChange(null)}
            title="Remove picture"
            className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full border border-border bg-white text-muted-foreground shadow-sm hover:text-destructive"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" />}
          {busy ? "Uploading…" : imageId ? "Replace picture" : label}
        </Button>
        <span className="text-[11px] text-muted-foreground">PNG, JPG, WEBP or GIF, up to {formatBytes(MAX_UPLOAD_BYTES)}</span>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
