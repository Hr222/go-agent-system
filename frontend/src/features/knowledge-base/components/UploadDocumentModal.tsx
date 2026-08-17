import { InboxOutlined } from "@ant-design/icons";
import { Alert, App, Descriptions, Form, Modal, Select, Space, Tag, Typography, Upload } from "antd";
import type { UploadFile } from "antd";
import { useState } from "react";

import type { KnowledgeUploadPreview, UploadDocumentRequest } from "../types";

const { Dragger } = Upload;

export function UploadDocumentModal({
  open,
  loading,
  onClose,
  onPreview,
  onConfirm,
}: {
  open: boolean;
  loading: boolean;
  onClose: () => void;
  onPreview: (request: UploadDocumentRequest) => Promise<KnowledgeUploadPreview>;
  onConfirm: (preview: KnowledgeUploadPreview) => Promise<void>;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<UploadDocumentRequest>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [preview, setPreview] = useState<KnowledgeUploadPreview | null>(null);

  function handleClose() {
    form.resetFields();
    setFileList([]);
    setPreview(null);
    onClose();
  }

  async function handlePreview(values: UploadDocumentRequest) {
    const file = fileList[0]?.originFileObj;
    if (!file) {
      message.warning("请先选择要导入的文档");
      return;
    }
    const nextPreview = await onPreview({ ...values, file });
    setPreview(nextPreview);
  }

  async function handleConfirm() {
    if (!preview) return;
    await onConfirm(preview);
    handleClose();
  }

  function handleModalCancel() {
    if (preview) {
      setPreview(null);
      return;
    }
    handleClose();
  }

  return (
    <Modal
      title={preview ? "确认知识文档" : "导入知识文档"}
      open={open}
      onCancel={handleModalCancel}
      okText={preview ? "确认入库" : "预览文件"}
      cancelText={preview ? "返回修改" : "取消"}
      confirmLoading={loading}
      okButtonProps={{ disabled: Boolean(preview && !preview.isAllowed) }}
      onOk={() => (preview ? void handleConfirm() : form.submit())}
      destroyOnHidden
    >
      {preview ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div>
            <Typography.Title level={5}>{preview.fileName}</Typography.Title>
            <Typography.Text type="secondary">
              {preview.policyNameGuess ?? "未识别制度名称"} · {preview.category}
            </Typography.Text>
          </div>
          <Descriptions
            bordered
            size="small"
            column={2}
            items={[
              { key: "version", label: "版本", children: preview.versionLabel ?? "系统推断" },
              { key: "size", label: "文件大小", children: formatBytes(preview.fileSizeBytes) },
              { key: "sections", label: "章节数", children: preview.sectionCount },
              { key: "chunks", label: "预计切片", children: preview.chunkCount },
            ]}
          />
          <Tag color={preview.isAllowed ? "success" : "error"}>
            {preview.isAllowed ? "文件校验通过" : "文件不符合入库条件"}
          </Tag>
          {preview.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              message="预览提示"
              description={preview.warnings.join("；")}
            />
          )}
        </Space>
      ) : (
        <Form form={form} layout="vertical" initialValues={{ category: "业务制度" }} onFinish={handlePreview}>
          <Form.Item label="文档文件">
            <Dragger
              accept=".doc,.docx,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
              maxCount={1}
              beforeUpload={() => false}
              fileList={fileList}
              onChange={({ fileList: next }) => setFileList(next)}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽文件到这里</p>
              <p className="ant-upload-hint">支持 DOC、DOCX、PDF 及常见图片扫描件，单个文件最大 50 MB</p>
            </Dragger>
          </Form.Item>
          <Form.Item
            label="文档分类"
            name="category"
            rules={[{ required: true, message: "请选择文档分类" }]}
          >
            <Select options={["业务制度", "采购管理", "风险管理", "项目管理", "档案管理"].map((value) => ({ value, label: value }))} />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
}

function formatBytes(value?: number) {
  if (value === undefined) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
