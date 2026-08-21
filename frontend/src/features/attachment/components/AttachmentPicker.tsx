import { useEffect, useRef, useState } from "react";
import { CircleAlert, FileText, LoaderCircle, Paperclip, RotateCcw, X } from "lucide-react";

import { AttachmentUploadError, uploadAttachment } from "../api/attachmentApi";
import type {
  AttachmentPickerProps,
  AttachmentRef,
  AttachmentUploadItem,
} from "../types";
import styles from "./AttachmentPicker.module.css";

const DEFAULT_ACCEPT = ".doc,.docx,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp";
const DEFAULT_MAX_COUNT = 5;

export function AttachmentPicker({
  value,
  onChange,
  onUploadStateChange,
  conversationId,
  accept = DEFAULT_ACCEPT,
  maxCount = DEFAULT_MAX_COUNT,
  disabled = false,
  layout = "default",
}: AttachmentPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const attachmentsRef = useRef(value);
  const controllersRef = useRef(new Map<string, AbortController>());
  const [items, setItems] = useState<AttachmentUploadItem[]>([]);
  const [selectionError, setSelectionError] = useState<string | null>(null);

  useEffect(() => {
    attachmentsRef.current = value;
  }, [value]);

  useEffect(() => {
    onUploadStateChange?.(items);
  }, [items, onUploadStateChange]);

  useEffect(() => () => {
    controllersRef.current.forEach((controller) => controller.abort());
  }, []);

  const commitAttachments = (next: AttachmentRef[]) => {
    attachmentsRef.current = next;
    onChange(next);
  };

  const updateItem = (
    localId: string,
    update: (item: AttachmentUploadItem) => AttachmentUploadItem,
  ) => {
    setItems((current) => current.map((item) => (item.localId === localId ? update(item) : item)));
  };

  const upload = async (localId: string, file: File) => {
    const controller = new AbortController();
    controllersRef.current.set(localId, controller);
    updateItem(localId, (item) => ({ ...item, status: "uploading", progress: 0, error: undefined }));

    try {
      const attachment = await uploadAttachment(file, {
        conversationId,
        signal: controller.signal,
        onProgress: (progress) => updateItem(localId, (item) => ({ ...item, progress })),
      });
      if (controller.signal.aborted) return;
      updateItem(localId, (item) => ({ ...item, status: "uploaded", progress: 100, attachment }));
      if (!attachmentsRef.current.some((item) => item.attachmentId === attachment.attachmentId)) {
        commitAttachments([...attachmentsRef.current, attachment]);
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      const message = error instanceof AttachmentUploadError
        ? error.message
        : "附件上传失败，请重试。";
      updateItem(localId, (item) => ({ ...item, status: "failed", error: message }));
    } finally {
      controllersRef.current.delete(localId);
    }
  };

  const handleSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length || disabled) return;

    const activeCount = items.filter((item) => item.status !== "uploaded").length;
    const remaining = Math.max(0, maxCount - value.length - activeCount);
    if (!remaining) {
      setSelectionError(`最多只能选择 ${maxCount} 个附件。`);
      return;
    }

    setSelectionError(files.length > remaining ? `最多只能选择 ${maxCount} 个附件。` : null);
    const nextItems = files.slice(0, remaining).map((file) => ({
      localId: createLocalId(),
      file,
      status: "selected" as const,
      progress: 0,
    }));
    setItems((current) => [...current, ...nextItems]);
    nextItems.forEach((item) => void upload(item.localId, item.file));
  };

  const removeItem = (item: AttachmentUploadItem) => {
    controllersRef.current.get(item.localId)?.abort();
    controllersRef.current.delete(item.localId);
    setItems((current) => current.filter((currentItem) => currentItem.localId !== item.localId));
    if (item.attachment) {
      commitAttachments(
        attachmentsRef.current.filter(
          (attachment) => attachment.attachmentId !== item.attachment?.attachmentId,
        ),
      );
    }
  };

  const removeExisting = (attachment: AttachmentRef) => {
    commitAttachments(
      attachmentsRef.current.filter((item) => item.attachmentId !== attachment.attachmentId),
    );
  };

  const displayedExisting = value.filter(
    (attachment) => !items.some((item) => item.attachment?.attachmentId === attachment.attachmentId),
  );
  const hasCapacity = value.length + items.filter((item) => item.status !== "uploaded").length < maxCount;

  return (
    <section
      className={layout === "composer" ? `${styles.root} ${styles.composerRoot}` : styles.root}
      aria-label="附件"
    >
      <input
        ref={inputRef}
        className={styles.fileInput}
        type="file"
        aria-label="选择附件"
        accept={accept}
        multiple={maxCount > 1}
        onChange={handleSelect}
        disabled={disabled || !hasCapacity}
      />
      <button
        className={styles.addButton}
        type="button"
        title="添加附件"
        aria-label="添加附件"
        onClick={() => inputRef.current?.click()}
        disabled={disabled || !hasCapacity}
      >
        <Paperclip size={16} />
      </button>

      {(selectionError || displayedExisting.length > 0 || items.length > 0) && (
        <div className={styles.list} aria-live="polite">
          {selectionError && <div className={styles.selectionError}>{selectionError}</div>}
          {displayedExisting.map((attachment) => (
            <ExistingAttachment
              key={attachment.attachmentId}
              attachment={attachment}
              disabled={disabled}
              onRemove={() => removeExisting(attachment)}
            />
          ))}
          {items.map((item) => (
            <UploadItem
              key={item.localId}
              item={item}
              disabled={disabled}
              onRetry={() => void upload(item.localId, item.file)}
              onRemove={() => removeItem(item)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ExistingAttachment({
  attachment,
  disabled,
  onRemove,
}: {
  attachment: AttachmentRef;
  disabled: boolean;
  onRemove: () => void;
}) {
  return (
    <div className={styles.item}>
      <FileText size={15} aria-hidden="true" />
      <span className={styles.fileName}>{attachment.fileName}</span>
      <span className={styles.status}>已上传</span>
      <button type="button" title="移除附件" aria-label={`移除 ${attachment.fileName}`} onClick={onRemove} disabled={disabled}>
        <X size={14} />
      </button>
    </div>
  );
}

function UploadItem({
  item,
  disabled,
  onRetry,
  onRemove,
}: {
  item: AttachmentUploadItem;
  disabled: boolean;
  onRetry: () => void;
  onRemove: () => void;
}) {
  const isUploading = item.status === "selected" || item.status === "uploading";
  return (
    <div className={styles.item}>
      {isUploading ? <LoaderCircle className={styles.spinner} size={15} aria-hidden="true" /> : <FileText size={15} aria-hidden="true" />}
      <span className={styles.fileName}>{item.file.name}</span>
      {isUploading && <span className={styles.status}>上传中 {item.progress}%</span>}
      {item.status === "uploaded" && <span className={styles.status}>已上传</span>}
      {item.status === "failed" && (
        <span className={styles.error} title={item.error}>
          <CircleAlert size={14} aria-hidden="true" /> 上传失败
        </span>
      )}
      {item.status === "failed" && (
        <button type="button" title="重新上传" aria-label={`重新上传 ${item.file.name}`} onClick={onRetry} disabled={disabled}>
          <RotateCcw size={14} />
        </button>
      )}
      <button type="button" title="移除附件" aria-label={`移除 ${item.file.name}`} onClick={onRemove} disabled={disabled}>
        <X size={14} />
      </button>
    </div>
  );
}

function createLocalId(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `attachment-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
