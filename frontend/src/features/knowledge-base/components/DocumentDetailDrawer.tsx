import { Alert, Button, Descriptions, Drawer, Image, Skeleton, Space, Steps, Tag, Typography } from "antd";
import { ExternalLink, FileImage, FileText, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getKnowledgeDocumentPreviewUrl } from "../api/knowledgeBaseApi";
import type { KnowledgeDocument } from "../types";
import styles from "./DocumentDetailDrawer.module.css";

const imageTypes = new Set<KnowledgeDocument["type"]>(["JPG", "PNG", "BMP", "TIF", "WEBP"]);

export function DocumentDetailDrawer({
  document,
  loading,
  onClose,
  onRetry,
}: {
  document: KnowledgeDocument | null;
  loading?: boolean;
  onClose: () => void;
  onRetry: (documentId: number) => void;
}) {
  const [previewStatus, setPreviewStatus] = useState<"checking" | "ready" | "unavailable">("checking");
  const previewUrl = document ? getKnowledgeDocumentPreviewUrl(document.id) : undefined;
  const isImage = Boolean(document && imageTypes.has(document.type));
  const isPdf = document?.type === "PDF";
  const isDocx = document?.type === "DOCX";
  const isPreviewable = isImage || isPdf || isDocx;

  useEffect(() => {
    if (!previewUrl || !isPreviewable) {
      setPreviewStatus("unavailable");
      return;
    }

    const controller = new AbortController();
    setPreviewStatus("checking");
    void fetch(previewUrl, { method: "HEAD", signal: controller.signal })
      .then((response) => {
        if (!controller.signal.aborted) setPreviewStatus(response.ok ? "ready" : "unavailable");
      })
      .catch(() => {
        if (!controller.signal.aborted) setPreviewStatus("unavailable");
      });

    return () => controller.abort();
  }, [isPreviewable, previewUrl]);

  const steps = [
    { title: "文件准入校验", status: "finish" as const },
    {
      title: "文本解析与清洗",
      status: document?.status === "failed"
        ? "error" as const
        : document?.status === "processing"
          ? "process" as const
          : "finish" as const,
    },
    { title: "章节拆分与切块", status: document?.status === "ready" ? "finish" as const : "wait" as const },
    { title: "向量化与索引", status: document?.status === "ready" ? "finish" as const : "wait" as const },
  ];

  const statusLabel = document?.status === "ready"
    ? "已就绪"
    : document?.status === "failed"
      ? "处理失败"
      : `处理中 ${document?.progress ?? 0}%`;

  const statusColor = document?.status === "ready"
    ? "success"
    : document?.status === "failed"
      ? "error"
      : "processing";

  return (
    <Drawer
      size="large"
      title="文档详情"
      open={Boolean(document)}
      onClose={onClose}
      extra={document ? <Tag color={statusColor}>{statusLabel}</Tag> : undefined}
    >
      {loading ? <Skeleton active paragraph={{ rows: 6 }} /> : <Space direction="vertical" size={22} style={{ width: "100%" }}>
        {document && (
          <>
            <div>
              <Typography.Title level={4}>{document.name}</Typography.Title>
              <Typography.Text type="secondary">最后更新 {document.updatedAt}</Typography.Text>
            </div>

            <section className={styles.previewSection} aria-label="原文件预览">
              <div className={styles.previewHeader}>
                <div>
                  <Typography.Title level={5}>原文件预览</Typography.Title>
                  <Typography.Text type="secondary">
                    {isImage
                      ? "支持缩放查看图片原件"
                      : isPdf
                        ? "支持直接查看 PDF 原件"
                        : isDocx
                          ? "支持直接查看 DOCX 原件"
                          : "当前格式提供原文件打开入口"}
                  </Typography.Text>
                </div>
                {previewUrl && (!isPreviewable || previewStatus === "ready") && (
                  <Button
                    type="link"
                    href={previewUrl}
                    target="_blank"
                    rel="noreferrer"
                    icon={<ExternalLink size={15} />}
                  >
                    新窗口打开
                  </Button>
                )}
              </div>
              {previewStatus === "checking" ? (
                <div className={styles.previewLoading}><Skeleton.Image active /></div>
              ) : previewStatus === "unavailable" && isPreviewable ? (
                <Alert
                  type="warning"
                  showIcon
                  icon={<FileImage size={16} />}
                  message="原文件暂不可预览"
                  description="该历史文档的原文件已不在当前存储位置，请重新上传后再查看。"
                />
              ) : previewUrl && isImage ? (
                <div className={styles.imagePreview}>
                  <Image
                    src={previewUrl}
                    alt={document.name}
                    preview
                    onError={() => setPreviewStatus("unavailable")}
                  />
                </div>
              ) : previewUrl && isPdf ? (
                <iframe className={styles.pdfPreview} src={previewUrl} title={`${document.name} PDF 预览`} />
              ) : previewUrl && isDocx ? (
                <DocxPreview previewUrl={previewUrl} />
              ) : (
                <div className={styles.previewUnavailable}>
                  <FileText size={20} />
                  <Typography.Text type="secondary">
                    {previewUrl
                      ? document.type === "DOC"
                        ? "旧版 DOC 需先转换为 DOCX 或 PDF，请使用“新窗口打开”查看原文件。"
                        : "该文件格式暂不支持在线预览，请使用“新窗口打开”查看原文件。"
                      : "当前环境未配置原文件预览地址。"}
                  </Typography.Text>
                </div>
              )}
            </section>

            <Descriptions
              column={2}
              size="small"
              bordered
              items={[
                { key: "type", label: "文件类型", children: document.type },
                { key: "size", label: "文件大小", children: document.size },
                { key: "category", label: "文档分类", children: document.category },
                { key: "version", label: "当前版本", children: document.version },
                { key: "chunks", label: "向量切片", children: document.chunks ? `${document.chunks.toLocaleString()} chunks` : "待处理" },
                { key: "updatedBy", label: "更新人员", children: document.updatedBy },
              ]}
            />

            {document.error && (
              <Alert
                type="error"
                showIcon
                message="处理失败"
                description={document.error}
                action={
                  <Button size="small" icon={<RefreshCw size={13} />} onClick={() => onRetry(document.id)}>
                    重新处理
                  </Button>
                }
              />
            )}

            <div>
              <Typography.Title level={5}>处理流水线</Typography.Title>
              <Steps direction="vertical" size="small" items={steps} />
            </div>
          </>
        )}
      </Space>}
    </Drawer>
  );
}

function DocxPreview({ previewUrl }: { previewUrl: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [renderStatus, setRenderStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    const container = containerRef.current;
    if (!container) return undefined;

    container.replaceChildren();
    setRenderStatus("loading");
    void Promise.all([
      fetch(previewUrl, { signal: controller.signal }).then(async (response) => {
        if (!response.ok) throw new Error(`DOCX 原文件不可用 (${response.status})`);
        return response.arrayBuffer();
      }),
      import("docx-preview"),
    ]).then(async ([file, { renderAsync }]) => {
      if (controller.signal.aborted) return;
      await renderAsync(file, container, undefined, {
        breakPages: true,
        inWrapper: true,
        renderComments: false,
        renderEndnotes: true,
        renderFooters: true,
        renderHeaders: true,
      });
      if (!controller.signal.aborted) setRenderStatus("ready");
    }).catch(() => {
      if (!controller.signal.aborted) setRenderStatus("error");
    });

    return () => controller.abort();
  }, [previewUrl]);

  return <div className={styles.docxPreview}>
    {renderStatus === "loading" && <div className={styles.previewLoading}><Skeleton active paragraph={{ rows: 5 }} /></div>}
    {renderStatus === "error" && <Alert type="warning" showIcon message="DOCX 渲染失败" description="可使用“新窗口打开”查看原文件。" />}
    <div className={renderStatus === "ready" ? styles.docxContent : styles.docxContentHidden} ref={containerRef} />
  </div>;
}
