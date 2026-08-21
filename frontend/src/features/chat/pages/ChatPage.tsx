import { useEffect, useRef, useState } from "react";
import {
  Archive,
  Bot,
  Check,
  Clipboard,
  Download,
  FileText,
  LoaderCircle,
  MessageSquare,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Workflow,
  X,
} from "lucide-react";

import { useIntentProposalResponse } from "../../interaction/hooks/useIntentInteraction";
import { useInteractionChatStream } from "../../interaction/hooks/useInteractionChatStream";
import type {
  InteractionGatewayResult,
  InteractionStreamApproval,
} from "../../interaction/types";
import { AttachmentPicker } from "../../attachment/components/AttachmentPicker";
import type { AttachmentRef, AttachmentUploadItem } from "../../attachment/types";
import { appConfig } from "../../../app/appConfig";
import { useDeltaRenderQueue } from "../hooks/useDeltaRenderQueue";
import styles from "./ChatPage.module.css";

type ChatRole = "user" | "assistant";
type ChatMessageStatus =
  | "connecting"
  | "streaming"
  | "awaiting_confirmation"
  | "confirming"
  | "cancelling"
  | "needs_clarification"
  | "unrecognized"
  | "completed"
  | "cancelled"
  | "rejected"
  | "failed";

type ChatAttachmentSummary = Pick<AttachmentRef, "fileName" | "mediaType" | "sizeBytes">;

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  request?: string;
  providedInputs?: Record<string, unknown>;
  attachmentSummaries?: readonly ChatAttachmentSummary[];
  approval?: InteractionStreamApproval;
  agentResult?: Record<string, unknown>;
  status?: ChatMessageStatus;
};

const initialMessages: ChatMessage[] = [];
const conversationItems: Array<{ id: string; title: string; meta: string }> = [];
const promptSuggestions = [
  "介绍一下你的能力",
  "解释什么是 LangChain",
  "给我一个技术方案思路",
];

export function ChatPage() {
  const [activeConversation, setActiveConversation] = useState("new-conversation");
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [attachments, setAttachments] = useState<AttachmentRef[]>([]);
  const [attachmentItems, setAttachmentItems] = useState<readonly AttachmentUploadItem[]>([]);
  const [attachmentPickerKey, setAttachmentPickerKey] = useState(0);
  const interactionStream = useInteractionChatStream();
  const proposalResponse = useIntentProposalResponse();
  const deltaRenderer = useDeltaRenderQueue();
  const respondingProposalIds = useRef(new Set<string>());
  const messageStreamRef = useRef<HTMLDivElement>(null);
  const hasPendingApproval = messages.some((message) => message.status === "awaiting_confirmation");
  const isStreaming = interactionStream.isActive || deltaRenderer.isRendering;
  const hasAttachmentUploadInProgress = attachmentItems.some(
    (item) => item.status === "selected" || item.status === "uploading",
  );
  const hasFailedAttachmentUpload = attachmentItems.some((item) => item.status === "failed");
  const isInteractionBusy = isStreaming || proposalResponse.isPending || hasPendingApproval;
  const isComposerBusy = isInteractionBusy || hasAttachmentUploadInProgress || hasFailedAttachmentUpload;
  const isAttachmentInteractionDisabled = isInteractionBusy || hasAttachmentUploadInProgress;
  const attachmentConversationId = activeConversation === "new-conversation"
    ? undefined
    : activeConversation;

  useEffect(() => {
    const stream = messageStreamRef.current;
    if (stream && typeof stream.scrollTo === "function") {
      stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isComposerBusy]);

  const updateAssistant = (assistantId: string, update: (message: ChatMessage) => ChatMessage) => {
    setMessages((current) => current.map((message) => (
      message.id === assistantId ? update(message) : message
    )));
  };

  const settleAssistant = (
    assistantId: string,
    status: "completed" | "cancelled" | "failed",
    fallbackContent: string,
  ) => {
    deltaRenderer.settle(() => {
      updateAssistant(assistantId, (message) => ({
        ...message,
        status,
        content: message.content || fallbackContent,
      }));
    });
  };

  const handleNewConversation = () => {
    interactionStream.cancel();
    setActiveConversation("new-conversation");
    setMessages([]);
    setInputValue("");
    resetAttachments();
  };

  const handleConversationSelect = (conversationId: string) => {
    interactionStream.cancel();
    setActiveConversation(conversationId);
    setMessages(conversationId === "tender-response" ? initialMessages : []);
    setInputValue("");
    resetAttachments();
  };

  const resetAttachments = () => {
    setAttachments([]);
    setAttachmentItems([]);
    setAttachmentPickerKey((current) => current + 1);
  };

  const handleSend = async (
    suggestion?: string,
    providedInputsOverride?: Record<string, unknown>,
    attachmentSummariesOverride?: readonly ChatAttachmentSummary[],
  ) => {
    const content = (suggestion ?? inputValue).trim();
    if (!content || isComposerBusy) return;

    const requestId = Date.now().toString();
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const assistantId = "assistant-" + requestId;
    const isRetry = providedInputsOverride !== undefined;
    const providedInputs = providedInputsOverride ?? chatProvidedInputs(attachments);
    const attachmentSummaries = attachmentSummariesOverride ?? attachmentSummariesFor(attachments);
    setMessages((current) => [
      ...current,
      {
        id: "user-" + requestId,
        role: "user",
        content,
        timestamp: "今天 " + now,
        attachmentSummaries,
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: "今天 " + now,
        request: content,
        providedInputs,
        attachmentSummaries,
        status: "connecting",
      },
    ]);
    setInputValue("");
    if (!isRetry) resetAttachments();
    deltaRenderer.start((delta) => {
      updateAssistant(assistantId, (message) => ({
        ...message,
        status: "streaming",
        content: message.content + delta,
      }));
    });

    try {
      const terminal = await interactionStream.send(content, {
        onMeta: () => {
          updateAssistant(assistantId, (message) => ({ ...message, status: "streaming" }));
        },
        onDelta: (delta) => deltaRenderer.enqueue(delta),
        onComplete: () => {
          settleAssistant(assistantId, "completed", "模型未返回可显示内容。");
        },
        onApprovalRequired: (approval) => {
          if (approval.conversationId) {
            setActiveConversation(approval.conversationId);
          }
          updateAssistant(assistantId, (message) => ({
            ...message,
            status: "awaiting_confirmation",
            content: "这项操作会调用业务能力，请先确认后再执行。",
            approval,
          }));
        },
        onResult: (result) => {
          updateAssistant(assistantId, (message) => ({
            ...message,
            status: result.status,
            content: result.message || "请求已处理。",
          }));
        },
      }, attachmentConversationId, providedInputs);
      if (terminal === undefined) {
        settleAssistant(assistantId, "cancelled", "已取消本次回答。");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "请求暂时无法处理，请稍后重试。";
      settleAssistant(assistantId, "failed", message);
    }
  };

  const handleCancelStream = () => {
    if (!interactionStream.isActive) return;
    interactionStream.cancel();
    const activeAssistant = [...messages].reverse().find((message) => (
      message.role === "assistant" && (message.status === "connecting" || message.status === "streaming")
    ));
    if (activeAssistant) {
      updateAssistant(activeAssistant.id, (message) => ({ ...message, status: "cancelling" }));
    }
  };

  const handleProposalResponse = async (messageId: string, action: "confirm" | "cancel") => {
    const message = messages.find((item) => item.id === messageId);
    const proposalId = message?.approval?.proposalId;
    if (!proposalId || message?.status !== "awaiting_confirmation" || respondingProposalIds.current.has(proposalId)) return;

    respondingProposalIds.current.add(proposalId);
    updateAssistant(messageId, (item) => ({
      ...item,
      status: action === "confirm" ? "confirming" : "cancelling",
      content: action === "confirm" ? "正在执行已批准的请求…" : "正在取消请求…",
    }));

    try {
      const result = await proposalResponse.mutateAsync({ proposalId, action });
      updateAssistant(messageId, (item) => applyConfirmationResult(item, result));
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "请求暂时无法处理，请稍后重试。";
      updateAssistant(messageId, (item) => ({ ...item, status: "failed", content: messageText }));
    } finally {
      respondingProposalIds.current.delete(proposalId);
    }
  };

  const handleCopy = async (content: string) => {
    await navigator.clipboard?.writeText(content);
  };

  return (
    <div className={styles.page}>
      <aside className={styles.conversationList} aria-label="历史会话">
        <div className={styles.listHeading}>
          <div>
            <span className={styles.eyebrow}>CONVERSATIONS</span>
            <h1>对话</h1>
          </div>
          <button className={styles.iconButton} type="button" title="更多会话操作" aria-label="更多会话操作">
            <MoreHorizontal size={17} />
          </button>
        </div>
        <button className={styles.newConversationButton} type="button" onClick={handleNewConversation}>
          <Plus size={16} /> 新建对话
        </button>
        <label className={styles.conversationSearch}>
          <Search size={14} />
          <input aria-label="搜索会话" placeholder="搜索会话" />
        </label>
        <div className={styles.listSectionLabel}>最近对话</div>
        <div className={styles.conversationItems}>
          {conversationItems.map((conversation) => (
            <button
              className={styles.conversationItem + (activeConversation === conversation.id ? " " + styles.conversationItemActive : "")}
              key={conversation.id}
              type="button"
              onClick={() => handleConversationSelect(conversation.id)}
            >
              <MessageSquare size={15} />
              <span className={styles.conversationCopy}>
                <strong>{conversation.title}</strong>
                <small>{conversation.meta}</small>
              </span>
            </button>
          ))}
        </div>
        <div className={styles.storageHint}>
          <Archive size={14} /> <span>当前不保存会话历史</span>
        </div>
      </aside>

      <section className={styles.chatWorkspace}>
        <header className={styles.chatHeader}>
          <div className={styles.agentIdentity}>
            <div className={styles.agentIcon}><Bot size={19} /></div>
            <div>
              <div className={styles.agentTitle}>LLM 助手 <span className={styles.statusDot} /> 在线</div>
              <div className={styles.agentSubtitle}>准备就绪</div>
            </div>
          </div>
          <div className={styles.chatHeaderActions}>
            <button className={styles.secondaryButton} type="button" onClick={() => setMessages([])}><RotateCcw size={14} /> 清空上下文</button>
            <button className={styles.iconButton} type="button" title="对话设置" aria-label="对话设置"><MoreHorizontal size={17} /></button>
          </div>
        </header>

        <div className={styles.messageStream} ref={messageStreamRef}>
          {messages.length === 0 && (
            <div className={styles.emptyConversation}>
              <div className={styles.emptyIcon}><Sparkles size={20} /></div>
              <h2>开始一段新的工作对话</h2>
              <p>发送一条消息开始工作。</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              conversationId={attachmentConversationId}
              isProposalResponding={proposalResponse.isPending}
              onCopy={handleCopy}
              onProposalResponse={handleProposalResponse}
              onRetry={() => handleSend(
                message.request ?? message.content,
                message.providedInputs,
                message.attachmentSummaries,
              )}
            />
          ))}
        </div>

        <footer className={styles.composerArea}>
          <div className={styles.suggestionRow}>
            {promptSuggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => handleSend(suggestion)} disabled={isComposerBusy}>
                <Sparkles size={13} /> {suggestion}
              </button>
            ))}
          </div>
          <div className={styles.composer}>
            <AttachmentPicker
              key={attachmentPickerKey}
              value={attachments}
              onChange={setAttachments}
              onUploadStateChange={setAttachmentItems}
              conversationId={attachmentConversationId}
              maxCount={1}
              disabled={isAttachmentInteractionDisabled}
              layout="composer"
            />
            <textarea
              aria-label="发送消息"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="输入你想了解的内容…"
              rows={2}
              disabled={isInteractionBusy}
            />
            <div className={styles.composerToolbar}>
              <div className={styles.composerTools}>
                <button className={styles.workflowButton} type="button" title="添加工作流" aria-label="添加工作流" disabled={isComposerBusy}><Workflow size={16} /></button>
              </div>
              {isStreaming ? (
                <button className={styles.cancelButton} type="button" onClick={handleCancelStream}>取消生成</button>
              ) : isInteractionBusy || hasAttachmentUploadInProgress ? (
                <span className={styles.processingLabel}><LoaderCircle size={14} /> 处理中</span>
              ) : (
                <button className={styles.sendButton} type="button" title="发送消息" aria-label="发送消息" onClick={() => void handleSend()} disabled={!inputValue.trim() || isComposerBusy}>
                  <Send size={16} />
                </button>
              )}
            </div>
          </div>
        </footer>
      </section>
    </div>
  );
}

function MessageBubble({
  message,
  conversationId,
  isProposalResponding,
  onCopy,
  onProposalResponse,
  onRetry,
}: {
  message: ChatMessage;
  conversationId?: string;
  isProposalResponding: boolean;
  onCopy: (content: string) => void;
  onProposalResponse: (messageId: string, action: "confirm" | "cancel") => void;
  onRetry: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className={styles.userMessageRow}>
        <div className={styles.userMessage}>
          <p>{message.content}</p>
          {message.attachmentSummaries?.map((attachment) => (
            <div
              className={styles.userAttachment}
              key={`${attachment.fileName}-${attachment.sizeBytes}`}
              aria-label={`附件 ${attachment.fileName}`}
            >
              <FileText size={14} aria-hidden="true" />
              <span>{attachment.fileName}</span>
              <small>{attachment.mediaType} · {formatAttachmentSize(attachment.sizeBytes)}</small>
            </div>
          ))}
          <small>{message.timestamp}</small>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.assistantRow}>
      <div className={styles.messageAvatar}><Bot size={16} /></div>
      <div className={styles.assistantMessageGroup}>
        <div className={styles.assistantMessage}>
          <div className={styles.assistantLabel}>LLM 助手 <span>{statusLabel(message.status)}</span></div>
          {message.content && <p>{message.content}{message.status === "streaming" && <span className={styles.streamingCaret} />}</p>}
          {message.status === "awaiting_confirmation" && message.approval && (
            <div className={styles.confirmationCard}>
              <div className={styles.confirmationHeading}><ShieldCheck size={16} /><strong>需要你的批准</strong></div>
              <p className={styles.confirmationSummary}>{message.approval.summary}</p>
              <span className={styles.confirmationPrompt}>{message.approval.confirmationPrompt}</span>
              <div className={styles.confirmationActions}>
                <button className={styles.confirmButton} type="button" onClick={() => onProposalResponse(message.id, "confirm")} disabled={isProposalResponding}>
                  <Check size={14} /> 批准执行
                </button>
                <button className={styles.declineButton} type="button" onClick={() => onProposalResponse(message.id, "cancel")} disabled={isProposalResponding}>
                  <X size={14} /> 取消
                </button>
              </div>
            </div>
          )}
          {(message.status === "completed" || message.status === "failed") && message.agentResult && (
            <AgentResultSummary result={message.agentResult} conversationId={conversationId} />
          )}
        </div>
        <div className={styles.messageActions}>
          {message.status === "completed" && (
            <>
              <button type="button" title="复制回答" aria-label="复制回答" onClick={() => onCopy(message.content)}><Clipboard size={13} /></button>
              <button type="button" title="回答有帮助" aria-label="回答有帮助"><ThumbsUp size={13} /></button>
              <button type="button" title="回答没有帮助" aria-label="回答没有帮助"><ThumbsDown size={13} /></button>
            </>
          )}
          {message.status === "failed" && (
            <button className={styles.inlineRetryButton} type="button" onClick={onRetry} disabled={isProposalResponding}>
              <RotateCcw size={12} /> 再次尝试
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function applyConfirmationResult(message: ChatMessage, result: InteractionGatewayResult): ChatMessage {
  const answer = result.execution_result?.answer;
  const agentResult = recordValue(result.execution_result?.agent_result)
    ?? (result.status === "completed" ? result.execution_result : null);
  return {
    ...message,
    status: result.status === "pending" ? "awaiting_confirmation" : result.status,
    content: result.status === "completed" && typeof answer === "string" && answer.trim()
      ? answer
      : result.message || "请求已处理。",
    approval: result.status === "pending" && result.proposal
      ? {
        proposalId: result.proposal.proposal_id,
        state: result.proposal.state,
        summary: result.proposal.summary,
        confirmationPrompt: result.proposal.confirmation_prompt,
      }
      : undefined,
    agentResult: agentResult ?? undefined,
  };
}

function chatProvidedInputs(attachments: readonly AttachmentRef[]): Record<string, unknown> {
  const attachment = attachments[0];
  return attachment ? { source_document: attachment.attachmentId } : {};
}

function attachmentSummariesFor(attachments: readonly AttachmentRef[]): ChatAttachmentSummary[] {
  return attachments.map(({ fileName, mediaType, sizeBytes }) => ({ fileName, mediaType, sizeBytes }));
}

function formatAttachmentSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${Math.ceil(sizeBytes / 1024)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function AgentResultSummary({
  result,
  conversationId,
}: {
  result: Record<string, unknown>;
  conversationId?: string;
}) {
  const analysis = recordValue(result.analysis);
  const summary = typeof analysis?.summary === "string" ? analysis.summary : null;
  const artifacts = artifactValues(result);
  if (!summary && artifacts.length === 0) return null;

  return (
    <div className={styles.agentResultCard} aria-label="Agent 执行结果">
      <strong>执行结果</strong>
      {summary && <p>{summary}</p>}
      {artifacts.map((artifact, index) => (
        <div className={styles.agentArtifact} key={artifact.resourceId || `${artifact.fileName}-${index}`}>
          <div className={styles.agentArtifactInfo}>
            <span>{artifact.fileName}</span>
            <small>{artifact.mediaType}{artifact.size === null ? "" : ` · ${artifact.size} 字节`}</small>
          </div>
          {artifact.resourceId && conversationId && isAttachmentResourceId(artifact.resourceId) && (
            <a
              className={styles.agentArtifactDownload}
              href={artifactDownloadUrl(artifact.resourceId, conversationId)}
              title="下载文件"
              aria-label="下载文件"
            >
              <Download size={14} />
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function isAttachmentResourceId(resourceId: string): boolean {
  return /^[0-9a-f]{32}$/i.test(resourceId);
}

function artifactDownloadUrl(resourceId: string, conversationId: string): string {
  const apiBaseUrl = appConfig.apiBaseUrl.replace(/\/$/, "");
  return `${apiBaseUrl}/v1/attachments/${encodeURIComponent(resourceId)}/download?conversation_id=${encodeURIComponent(conversationId)}`;
}

function artifactValues(result: Record<string, unknown>) {
  const values = Array.isArray(result.artifacts)
    ? result.artifacts
    : result.artifact ? [result.artifact] : [];
  return values.flatMap((value) => {
    const artifact = recordValue(value);
    if (!artifact) return [];
    const fileName = typeof artifact.file_name === "string" ? artifact.file_name : "生成文件";
    const mediaType = typeof artifact.media_type === "string" ? artifact.media_type : "未知类型";
    const size = typeof artifact.size === "number" ? artifact.size : null;
    const resourceId = typeof artifact.resource_id === "string" ? artifact.resource_id : null;
    return [{ fileName, mediaType, size, resourceId }];
  });
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function statusLabel(status: ChatMessage["status"]): string {
  if (status === "connecting") return "连接中";
  if (status === "streaming") return "输出中";
  if (status === "awaiting_confirmation") return "等待批准";
  if (status === "confirming") return "正在执行";
  if (status === "cancelling") return "正在取消";
  if (status === "needs_clarification") return "需要补充";
  if (status === "unrecognized") return "未能理解";
  if (status === "cancelled") return "已取消";
  if (status === "rejected") return "无法继续";
  if (status === "failed") return "处理失败";
  return "已完成";
}
