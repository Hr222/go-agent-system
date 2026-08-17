import { Eye, MoreHorizontal, RefreshCw, Search, Upload } from "lucide-react";
import { Button, Card, Empty, Input, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { KnowledgeDocument, KnowledgeDocumentStatus } from "../types";
import styles from "../pages/KnowledgeBasePage.module.css";

const statusText: Record<KnowledgeDocumentStatus, string> = { ready: "已就绪", processing: "处理中", failed: "处理失败" };
const statusColor: Record<KnowledgeDocumentStatus, string> = { ready: "success", processing: "processing", failed: "error" };

export function DocumentTable({ documents, search, statuses, category, categories, loading, total, currentPage, pageSize, isRecent, onPageChange, onSearchChange, onStatusesChange, onCategoryChange, onUpload, onOpen, onRetry, onViewAll }: { documents: KnowledgeDocument[]; search: string; statuses: KnowledgeDocumentStatus[]; category?: string; categories: string[]; loading: boolean; total?: number; currentPage: number; pageSize: number; isRecent: boolean; onPageChange: (page: number, pageSize: number) => void; onSearchChange: (value: string) => void; onStatusesChange: (value: KnowledgeDocumentStatus[]) => void; onCategoryChange: (value?: string) => void; onUpload: () => void; onOpen: (document: KnowledgeDocument) => void; onRetry: (documentId: number) => void; onViewAll: () => void }) {
  const columns: ColumnsType<KnowledgeDocument> = [
    { title: "文档名称", dataIndex: "name", key: "name", render: (_, document) => <div className={styles.documentName}><FileTypeBadge type={document.type} /><div><Typography.Text strong ellipsis={{ tooltip: document.name }}>{document.name}</Typography.Text><Typography.Text type="secondary">{document.size} · {document.updatedBy}</Typography.Text></div></div> },
    { title: "分类 / 版本", key: "category", render: (_, document) => <Space size={6}><Typography.Text type="secondary">{document.category}</Typography.Text><Tag color="processing">{document.version}</Tag></Space> },
    { title: "切片数量", key: "chunks", render: (_, document) => <div><Typography.Text strong>{document.status === "processing" ? "—" : document.chunks.toLocaleString()}</Typography.Text><Typography.Text type="secondary">{document.status === "processing" ? "处理中" : "chunks"}</Typography.Text></div> },
    { title: "处理状态", key: "status", render: (_, document) => <StatusTag document={document} /> },
    { title: "最近更新", dataIndex: "updatedAt", key: "updatedAt", render: (value: string) => <Typography.Text type="secondary">{value}</Typography.Text> },
    { title: "操作", key: "actions", align: "right", render: (_, document) => <Space size={2}><Tooltip title="查看文档"><Button type="text" size="small" icon={<Eye size={15} />} onClick={() => onOpen(document)} /></Tooltip>{document.status === "failed" && <Tooltip title="重新处理"><Button type="text" size="small" icon={<RefreshCw size={15} />} onClick={() => onRetry(document.id)} /></Tooltip>}<Tooltip title="更多操作"><Button type="text" size="small" icon={<MoreHorizontal size={15} />} onClick={() => onOpen(document)} /></Tooltip></Space> },
  ];

  return (
    <Card
      className={styles.documentPanel}
      title={<div><Typography.Title level={5}>{isRecent ? "最近文档" : "文档管理"}</Typography.Title><Typography.Text type="secondary">知识库中的文档及其处理状态</Typography.Text></div>}
      extra={isRecent ? <Button type="link" onClick={onViewAll}>查看全部 <span>›</span></Button> : undefined}
    >
      <div className={styles.documentToolbar}>
        <Input
          size="large"
          className={styles.documentSearch}
          prefix={<Search size={16} />}
          allowClear
          placeholder="搜索文档名称..."
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <Space size={12}>
          <Select
            size="large"
            mode="multiple"
            allowClear
            maxTagCount="responsive"
            placeholder="处理状态"
            value={statuses}
            onChange={onStatusesChange}
            options={[{ value: "ready", label: "已就绪" }, { value: "processing", label: "处理中" }, { value: "failed", label: "处理失败" }]}
          />
          <Select
            size="large"
            allowClear
            placeholder="文档分类"
            value={category}
            onChange={onCategoryChange}
            options={categories.map((item) => ({ value: item, label: item }))}
          />
          <Button size="large" icon={<Upload size={16} />} onClick={onUpload}>导入</Button>
        </Space>
      </div>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={documents}
        pagination={total === undefined ? false : { current: currentPage, pageSize, total, showSizeChanger: true, pageSizeOptions: ["10", "20", "50"], showTotal: (value) => `共 ${value} 条`, onChange: onPageChange }}
        onRow={(document) => ({ onClick: () => onOpen(document) })}
        locale={{ emptyText: <Empty description="没有找到匹配的文档" /> }}
      />
    </Card>
  );
}

function FileTypeBadge({ type }: { type: KnowledgeDocument["type"] }) {
  const tone = ["JPG", "PNG", "BMP", "TIF", "WEBP"].includes(type)
    ? "image"
    : type === "FILE"
      ? "file"
      : type.toLowerCase();
  return <span className={`${styles.fileType} ${styles[tone]}`}>{type}</span>;
}

function StatusTag({ document }: { document: KnowledgeDocument }) {
  return <Tag color={statusColor[document.status]}>{statusText[document.status]}{document.status === "processing" && ` ${document.progress ?? 0}%`}</Tag>;
}
