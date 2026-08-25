import { useEffect, useRef, useState } from "react";
import { message } from "antd";
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
  Pin,
  Pencil,
  Trash2,
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
import type { ConversationHistoryMessage } from "../api/conversationHistoryApi";
import type { ConversationSummary } from "../api/conversationListApi";
import { useDeltaRenderQueue } from "../hooks/useDeltaRenderQueue";
import { useActiveConversation } from "../hooks/useActiveConversation";
import {
  useConversationList,
  useCreateConversation,
  useDeleteConversation,
  useUpdateConversationPin,
  useUpdateConversationTopicSummary,
} from "../hooks/useConversationList";
import { useConversationHistory } from "../hooks/useConversationHistory";
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
const promptSuggestions = [
  "介绍一下你的能力",
  "解释什么是 LangChain",
  "给我一个技术方案思路",
];

export function ChatPage() {
  const {
    activeConversation,
    setActiveConversation,
    clearActiveConversation,
  } = useActiveConversation();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [attachments, setAttachments] = useState<AttachmentRef[]>([]);
  const [attachmentItems, setAttachmentItems] = useState<readonly AttachmentUploadItem[]>([]);
  const [attachmentPickerKey, setAttachmentPickerKey] = useState(0);
  const interactionStream = useInteractionChatStream();
  const proposalResponse = useIntentProposalResponse();
  const deltaRenderer = useDeltaRenderQueue();
  const conversationList = useConversationList();
  const createConversationMutation = useCreateConversation();
  const deleteConversationMutation = useDeleteConversation();
  const updatePinMutation = useUpdateConversationPin();
  const updateTopicSummaryMutation = useUpdateConversationTopicSummary();
  const conversationHistory = useConversationHistory(activeConversation);
  const [conversationActionError, setConversationActionError] = useState<string | null>(null);
  const [topicSummaryError, setTopicSummaryError] = useState<string | null>(null);
  const [openConversationMenu, setOpenConversationMenu] = useState<string | null>(null);
  const [renameConversationId, setRenameConversationId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleteInProgress, setDeleteInProgress] = useState(false);
  const [listActionNotice, setListActionNotice] = useState<string | null>(null);
  const respondingProposalIds = useRef(new Set<string>());
  const messageStreamRef = useRef<HTMLDivElement>(null);
  const historyConversationRef = useRef<string | null>(null);
  const historyMessagesRef = useRef<ChatMessage[]>([]);
  const historyMessageIdsRef = useRef(new Set<string>());
  const hasPendingApproval = messages.some((message) => message.status === "awaiting_confirmation");
  const isStreaming = interactionStream.isActive || deltaRenderer.isRendering;
  const hasAttachmentUploadInProgress = attachmentItems.some(
    (item) => item.status === "selected" || item.status === "uploading",
  );
  const hasFailedAttachmentUpload = attachmentItems.some((item) => item.status === "failed");
  const isInteractionBusy = isStreaming || proposalResponse.isPending || hasPendingApproval;
  const isComposerBusy = isInteractionBusy || hasAttachmentUploadInProgress || hasFailedAttachmentUpload;
  const isAttachmentInteractionDisabled = isInteractionBusy || hasAttachmentUploadInProgress;
  const attachmentConversationId = activeConversation ?? undefined;
  const historyUnavailable = isConversationUnavailableError(conversationHistory.error);
  const conversationSummaries = conversationList.data?.pages.flatMap((page) => page.conversations) ?? [];
  const showHistoryLoading = activeConversation !== null
    && conversationHistory.isPending
    && messages.length === 0;
  const showHistoryError = activeConversation !== null
    && conversationHistory.isError
    && !historyUnavailable;

  useEffect(() => {
    if (historyConversationRef.current === activeConversation) return;
    historyConversationRef.current = activeConversation;
    historyMessagesRef.current = [];
    historyMessageIdsRef.current = new Set();
  }, [activeConversation]);

  useEffect(() => {
    if (!openConversationMenu) return;

    const closeMenuOnOutsidePointer = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest("[data-conversation-menu]")) return;
      setOpenConversationMenu(null);
    };

    document.addEventListener("pointerdown", closeMenuOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeMenuOnOutsidePointer);
  }, [openConversationMenu]);

  useEffect(() => {
    if (activeConversation === null) return;
    if (isStreaming) return;
    if (conversationHistory.isError) {
      if (historyUnavailable) {
        clearActiveConversation();
        historyMessagesRef.current = [];
        historyMessageIdsRef.current = new Set();
        setMessages([]);
      }
      return;
    }
    if (!conversationHistory.data) return;

    const incomingMessages = conversationHistory.data.pages
      .flatMap((page) => page.messages)
      .map(historyMessageToChatMessage)
      .filter((message) => !historyMessageIdsRef.current.has(message.id));
    if (incomingMessages.length === 0) return;

    incomingMessages.forEach((message) => historyMessageIdsRef.current.add(message.id));
    historyMessagesRef.current = [...historyMessagesRef.current, ...incomingMessages];
    const incomingKeys = new Set(incomingMessages.map(messageKey));
    setMessages((current) => [
      ...historyMessagesRef.current,
      ...current.filter((message) => (
        !historyMessageIdsRef.current.has(message.id)
        && (!isLocalMessage(message) || !incomingKeys.has(messageKey(message)))
      )),
    ]);
  }, [
    activeConversation,
    clearActiveConversation,
    conversationHistory.data,
    conversationHistory.isError,
    historyUnavailable,
    isStreaming,
  ]);

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

  const handleNewConversation = async () => {
    if (createConversationMutation.isPending) return;
    interactionStream.cancel();
    setConversationActionError(null);
    try {
      const conversation = await createConversationMutation.mutateAsync();
      setActiveConversation(conversation.id);
      setMessages([]);
      setInputValue("");
      resetAttachments();
      await conversationList.refetch();
    } catch (error) {
      setConversationActionError(apiErrorMessage(error, "创建会话失败，请重试。"));
    }
  };

  const handleConversationSelect = (conversationId: string) => {
    interactionStream.cancel();
    setConversationActionError(null);
    setActiveConversation(conversationId);
    setMessages(conversationId === "tender-response" ? initialMessages : []);
    setInputValue("");
    resetAttachments();
  };

  const beginRename = (conversation: ConversationSummary) => {
    setOpenConversationMenu(null);
    setRenameConversationId(conversation.id);
    setRenameDraft(conversation.topicSummary ?? "");
    setTopicSummaryError(null);
  };

  const cancelRename = () => {
    if (updateTopicSummaryMutation.isPending) return;
    setRenameConversationId(null);
    setRenameDraft("");
    setTopicSummaryError(null);
  };

  const saveRename = async () => {
    if (!renameConversationId || updateTopicSummaryMutation.isPending) return;
    setTopicSummaryError(null);
    try {
      await updateTopicSummaryMutation.mutateAsync({
        conversationId: renameConversationId,
        topicSummary: renameDraft.trim() || null,
      });
      setRenameConversationId(null);
      setRenameDraft("");
      setListActionNotice("会话名称已更新");
    } catch (error) {
      setTopicSummaryError(apiErrorMessage(error, "会话名称保存失败，请重试。"));
    }
  };

  const togglePin = async (conversation: ConversationSummary) => {
    if (updatePinMutation.isPending) return;
    setOpenConversationMenu(null);
    try {
      await updatePinMutation.mutateAsync({
        conversationId: conversation.id,
        isPinned: !conversation.isPinned,
      });
      setListActionNotice(conversation.isPinned ? "已取消置顶" : "已置顶会话");
    } catch (error) {
      message.error(apiErrorMessage(error, "置顶操作失败，请重试。"));
    }
  };

  const requestDelete = (conversationId: string) => {
    setOpenConversationMenu(null);
    setDeleteConfirmId(conversationId);
  };

  const confirmDelete = async () => {
    if (deleteInProgress || !deleteConfirmId) return;
    const conversationId = deleteConfirmId;
    setDeleteInProgress(true);
    try {
      await deleteConversationMutation.mutateAsync(conversationId);
      if (activeConversation === conversationId) {
        clearActiveConversation();
        setMessages([]);
        setRenameConversationId(null);
        setRenameDraft("");
      }
      setDeleteConfirmId(null);
      setListActionNotice("会话已删除");
      await conversationList.refetch();
    } catch {
      setDeleteConfirmId(null);
      message.error("会话删除失败，请重试。");
    } finally {
      setDeleteInProgress(false);
    }
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
        onMeta: (meta) => {
          setActiveConversation(meta.conversationId);
          void conversationList.refetch();
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
        <button
          className={styles.newConversationButton}
          type="button"
          onClick={() => void handleNewConversation()}
          disabled={createConversationMutation.isPending}
        >
          <Plus size={16} /> 新建对话
        </button>
        {conversationActionError && (
          <div className={styles.conversationListError} role="alert">
            {conversationActionError}
          </div>
        )}
        <label className={styles.conversationSearch}>
          <Search size={14} />
          <input aria-label="搜索会话" placeholder="搜索会话" />
        </label>
        <div className={styles.listSectionLabel}>最近对话</div>
        {listActionNotice && (
          <div className={styles.listActionNotice} role="status">
            <span>{listActionNotice}</span>
            <button type="button" aria-label="关闭提示" onClick={() => setListActionNotice(null)}><X size={12} /></button>
          </div>
        )}
        <div className={styles.conversationItems}>
          {conversationList.isPending && (
            <div className={styles.conversationListStatus} role="status">正在加载会话</div>
          )}
          {conversationList.isError && (
            <div className={styles.conversationListError} role="alert">
              <span>会话列表暂时无法加载。</span>
              <button
                className={styles.retryButton}
                type="button"
                onClick={() => void conversationList.refetch()}
                disabled={conversationList.isFetching}
              >
                <RotateCcw size={12} /> 重试
              </button>
            </div>
          )}
          {!conversationList.isPending && !conversationList.isError && conversationSummaries.length === 0 && (
            <div className={styles.conversationListStatus}>暂无历史会话</div>
          )}
          {conversationSummaries.map((conversation) => (
            <div
              className={styles.conversationItemRow}
              key={conversation.id}
              data-conversation-id={conversation.id}
              data-menu-open={openConversationMenu === conversation.id || undefined}
            >
              {renameConversationId === conversation.id ? (
                <div
                  className={styles.conversationItem + " " + styles.conversationItemEditing + (activeConversation === conversation.id ? " " + styles.conversationItemActive : "")}
                >
                  <MessageSquare size={15} />
                  <div className={styles.conversationCopy}>
                    <div className={styles.conversationRenameControls}>
                      <input
                        aria-label="会话名称"
                        autoFocus
                        maxLength={80}
                        value={renameDraft}
                        onChange={(event) => setRenameDraft(event.target.value)}
                        placeholder="输入会话名称"
                        disabled={updateTopicSummaryMutation.isPending}
                      />
                      {conversation.isPinned && <Pin className={styles.conversationPinnedIcon} size={11} aria-label="已置顶" />}
                      <button
                        type="button"
                        title="保存会话名称"
                        aria-label="保存会话名称"
                        onClick={() => void saveRename()}
                        disabled={updateTopicSummaryMutation.isPending}
                      >
                        <Check size={13} />
                      </button>
                      <button
                        type="button"
                        title="取消重命名"
                        aria-label="取消重命名"
                        onClick={cancelRename}
                        disabled={updateTopicSummaryMutation.isPending}
                      >
                        <X size={13} />
                      </button>
                    </div>
                    {topicSummaryError && (
                      <div className={styles.conversationRenameError} role="alert">
                        {topicSummaryError}
                      </div>
                    )}
                    <small>{conversationMeta(conversation)}</small>
                  </div>
                </div>
              ) : (
                <button
                  className={styles.conversationItem + (activeConversation === conversation.id ? " " + styles.conversationItemActive : "")}
                  type="button"
                  onClick={() => handleConversationSelect(conversation.id)}
                >
                  <MessageSquare size={15} />
                  <span className={styles.conversationCopy}>
                    <strong>{conversationTitle(conversation)} {conversation.isPinned && <Pin size={11} aria-label="已置顶" />}</strong>
                    <small>{conversationMeta(conversation)}</small>
                  </span>
                </button>
              )}
              <div className={styles.conversationMenuWrap} data-conversation-menu>
                  <button
                    className={styles.conversationMenuButton}
                    type="button"
                    aria-label={`会话操作：${conversationTitle(conversation)}`}
                    title="更多操作"
                    onClick={(event) => {
                      event.stopPropagation();
                      setOpenConversationMenu((current) => current === conversation.id ? null : conversation.id);
                    }}
                  >
                    <MoreHorizontal size={15} />
                  </button>
                  {openConversationMenu === conversation.id && (
                    <div className={styles.conversationMenu} role="menu">
                      <button type="button" role="menuitem" onClick={() => beginRename(conversation)}><Pencil size={14} /> 重命名</button>
                      <button type="button" role="menuitem" onClick={() => void togglePin(conversation)} disabled={updatePinMutation.isPending}><Pin size={14} /> {conversation.isPinned ? "取消置顶" : "置顶"}</button>
                      <button type="button" role="menuitem">分享</button>
                      <button className={styles.dangerMenuItem} type="button" role="menuitem" onClick={() => requestDelete(conversation.id)}><Trash2 size={14} /> 删除</button>
                    </div>
                  )}
                </div>
            </div>
          ))}
          {conversationList.hasNextPage && (
            <button
              className={styles.textButton}
              type="button"
              onClick={() => void conversationList.fetchNextPage()}
              disabled={conversationList.isFetchingNextPage}
            >
              {conversationList.isFetchingNextPage ? "正在加载" : "加载更多会话"}
            </button>
          )}
        </div>
        {deleteConfirmId && (
          <div className={styles.deleteConfirmBackdrop} role="presentation">
            <div
              className={styles.deleteConfirmDialog}
              role="dialog"
              aria-modal="true"
              aria-labelledby="delete-conversation-title"
            >
              <div className={styles.deleteConfirmIcon}><Trash2 size={18} /></div>
              <h2 id="delete-conversation-title">
                删除这个会话？
              </h2>
              <p>删除后会话消息和相关记录将一并移除，且无法恢复。</p>
              <div className={styles.deleteConfirmActions}>
                <button
                  type="button"
                  className={styles.deleteCancelButton}
                  onClick={() => setDeleteConfirmId(null)}
                  disabled={deleteInProgress}
                >
                  取消
                </button>
                <button
                  type="button"
                  className={styles.deleteConfirmButton}
                  onClick={() => void confirmDelete()}
                  disabled={deleteInProgress}
                >
                  {deleteInProgress ? <LoaderCircle size={14} className={styles.spinIcon} /> : <Trash2 size={14} />}
                  {deleteInProgress ? "删除中" : "确认删除"}
                </button>
              </div>
            </div>
          </div>
        )}
        <div className={styles.storageHint}>
          <Archive size={14} /> <span>会话历史已保存</span>
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
          {showHistoryLoading && (
            <div className={styles.thinkingBubble} role="status">
              <span /><span /><span /><em>正在加载会话历史</em>
            </div>
          )}
          {showHistoryError && (
            <div className={styles.errorMessage} role="alert">
              <span>会话历史暂时无法加载。</span>
              <button
                className={styles.retryButton}
                type="button"
                onClick={() => void conversationHistory.refetch()}
                disabled={conversationHistory.isFetching}
              >
                <RotateCcw size={12} /> 重试加载
              </button>
            </div>
          )}
          {messages.length === 0 && activeConversation === null && (
            <div className={styles.emptyConversation}>
              <div className={styles.emptyIcon}><Sparkles size={20} /></div>
              <h2>开始一段新的工作对话</h2>
              <p>发送一条消息开始工作。</p>
            </div>
          )}
          {messages.length === 0 && activeConversation !== null && conversationHistory.isSuccess && (
            <div className={styles.emptyConversation}>
              <div className={styles.emptyIcon}><MessageSquare size={20} /></div>
              <h2>这是一个空会话</h2>
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
          {activeConversation !== null && conversationHistory.hasNextPage && (
            <div className={styles.historyPagination}>
              <button
                className={styles.textButton}
                type="button"
                onClick={() => void conversationHistory.fetchNextPage()}
                disabled={conversationHistory.isFetchingNextPage}
              >
                {conversationHistory.isFetchingNextPage ? "正在加载" : "加载更多消息"}
              </button>
            </div>
          )}
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

function historyMessageToChatMessage(message: ConversationHistoryMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    timestamp: historyMessageTimestamp(message.createdAt),
    status: "completed",
  };
}

function historyMessageTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function conversationTitle(summary: ConversationSummary): string {
  return summary.topicSummary?.trim() || `会话 ${formatConversationDate(summary.createdAt)}`;
}

function conversationMeta(summary: ConversationSummary): string {
  return `更新于 ${formatConversationDate(summary.updatedAt)}`;
}

function formatConversationDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "未知时间";
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

function isLocalMessage(message: ChatMessage): boolean {
  return message.id.startsWith("user-") || message.id.startsWith("assistant-");
}

function messageKey(message: Pick<ChatMessage, "role" | "content">): string {
  return `${message.role}:${message.content}`;
}

function isConversationUnavailableError(error: unknown): boolean {
  if (!error || typeof error !== "object" || !("status" in error)) return false;
  const status = (error as { status?: unknown }).status;
  return status === 403 || status === 404;
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
