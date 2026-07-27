import { useEffect, useRef, useState } from "react";
import {
  Archive,
  Bot,
  Check,
  ChevronDown,
  Clipboard,
  FileText,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Plus,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Workflow,
} from "lucide-react";

import { useChat } from "../hooks/useChat";
import styles from "./ChatPage.module.css";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  citations?: string[];
  metrics?: string;
  request?: string;
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [failedRequest, setFailedRequest] = useState<string | null>(null);
  const chatMutation = useChat();
  const isThinking = chatMutation.isPending;
  const messageStreamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stream = messageStreamRef.current;
    if (stream) stream.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
  }, [messages, isThinking]);

  const handleNewConversation = () => {
    setActiveConversation("new-conversation");
    setMessages([]);
    setInputValue("");
    setErrorMessage(null);
    setFailedRequest(null);
  };

  const handleConversationSelect = (conversationId: string) => {
    setActiveConversation(conversationId);
    setMessages(conversationId === "tender-response" ? initialMessages : []);
    setInputValue("");
    setErrorMessage(null);
    setFailedRequest(null);
  };

  const handleSend = async (suggestion?: string) => {
    const content = (suggestion ?? inputValue).trim();
    if (!content || isThinking) return;

    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content, timestamp: `今天 ${now}` },
    ]);
    setInputValue("");
    setErrorMessage(null);
    setFailedRequest(null);

    try {
      const result = await chatMutation.mutateAsync(content);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: result.answer,
          timestamp: `今天 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`,
          metrics: `${result.model} · ${result.durationMs}ms${result.totalTokens === null ? "" : ` · ${result.totalTokens} tokens`}`,
          request: content,
        },
      ]);
      setFailedRequest(null);
    } catch (error) {
      const apiError = error as { message?: string };
      setErrorMessage(apiError.message ?? "LLM 请求失败，请稍后重试。");
      setFailedRequest(content);
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
          <Plus size={16} />
          新建对话
        </button>

        <label className={styles.conversationSearch}>
          <Search size={14} />
          <input aria-label="搜索会话" placeholder="搜索会话" />
        </label>

        <div className={styles.listSectionLabel}>最近对话</div>
        <div className={styles.conversationItems}>
          {conversationItems.map((conversation) => (
            <button
              className={`${styles.conversationItem} ${activeConversation === conversation.id ? styles.conversationItemActive : ""}`}
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
          <Archive size={14} />
          <span>当前不保存会话历史</span>
        </div>
      </aside>

      <section className={styles.chatWorkspace}>
        <header className={styles.chatHeader}>
          <div className={styles.agentIdentity}>
            <div className={styles.agentIcon}><Bot size={19} /></div>
            <div>
              <div className={styles.agentTitle}>LLM 助手 <span className={styles.statusDot} /> 在线</div>
              <div className={styles.agentSubtitle}>单轮模型调用验证</div>
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
              <p>发送一条消息，验证后端 LangChain 与 GLM 的单轮调用。</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} onCopy={handleCopy} onRetry={() => handleSend(message.request ?? message.content)} />
          ))}
          {isThinking && (
            <div className={styles.assistantRow}>
              <div className={styles.messageAvatar}><Bot size={16} /></div>
              <div className={styles.thinkingBubble}><span /><span /><span /><em>正在请求模型</em></div>
            </div>
          )}
        </div>

        <footer className={styles.composerArea}>
          <div className={styles.suggestionRow}>
            {promptSuggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => handleSend(suggestion)}>
                <Sparkles size={13} /> {suggestion}
              </button>
            ))}
          </div>
          <div className={styles.composer}>
            <textarea
              aria-label="发送消息"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              placeholder="输入你想了解的内容..."
              rows={2}
            />
            <div className={styles.composerToolbar}>
              <div className={styles.composerTools}>
                <button type="button" title="添加附件" aria-label="添加附件"><Paperclip size={16} /></button>
                <button type="button" title="添加工作流" aria-label="添加工作流"><Workflow size={16} /></button>
                <span className={styles.composerHint}>Enter 发送 · Shift + Enter 换行</span>
              </div>
              <button className={styles.sendButton} type="button" title="发送消息" aria-label="发送消息" onClick={() => handleSend()} disabled={isThinking || !inputValue.trim()}>
                <Send size={16} />
              </button>
            </div>
          </div>
          {errorMessage && (
            <div className={styles.errorMessage} role="alert">
              <span>{errorMessage}</span>
              <button className={styles.retryButton} type="button" onClick={() => handleSend(failedRequest ?? undefined)} disabled={isThinking || !failedRequest}>
                <RotateCcw size={12} /> 重试
              </button>
            </div>
          )}
        </footer>
      </section>

      <aside className={styles.inspector} aria-label="LLM 调用信息">
        <div className={styles.inspectorHeading}>
          <div><span className={styles.eyebrow}>LLM TEST</span><h2>调用信息</h2></div>
          <button className={styles.iconButton} type="button" title="收起上下文" aria-label="收起上下文"><ChevronDown size={16} /></button>
        </div>

        <div className={styles.inspectorSection}>
          <div className={styles.sectionTitle}><span>调用模式</span></div>
          <div className={styles.sourceCard}>
            <div className={styles.sourceIcon}><Sparkles size={16} /></div>
            <div className={styles.sourceCopy}><strong>独立 LLM 调用</strong><small>单轮 · 无上下文 · 无工具</small></div>
          </div>
          <div className={styles.contextNote}>当前只验证模型文本响应</div>
        </div>

        <div className={styles.inspectorSection}>
          <div className={styles.sectionTitle}><span>当前模型</span><button type="button" className={styles.textButton}>切换</button></div>
          <div className={styles.modelCard}>
            <div className={styles.modelMark}>GLM</div>
            <div className={styles.sourceCopy}><strong>GLM</strong><small>LangChain 后端适配 · 单轮调用</small></div>
            <Check size={15} color="#2aa77c" />
          </div>
        </div>

        <div className={styles.inspectorSection}>
          <div className={styles.sectionTitle}><span>响应设置</span></div>
          <div className={styles.parameterRow}><span>温度</span><strong>0.2</strong></div>
          <div className={styles.parameterTrack}><span style={{ width: "20%" }} /></div>
          <div className={styles.parameterRow}><span>上下文记忆</span><strong>未接入</strong></div>
          <div className={styles.parameterRow}><span>工具调用</span><strong>未接入</strong></div>
        </div>

        <div className={styles.langchainNote}>
          <div className={styles.langchainIcon}><Workflow size={15} /></div>
          <div><strong>LangChain 技术验证</strong><p>当前只验证通用 LLM 的单轮调用。</p></div>
        </div>
      </aside>
    </div>
  );
}

function MessageBubble({ message, onCopy, onRetry }: { message: ChatMessage; onCopy: (content: string) => void; onRetry: () => void }) {
  if (message.role === "user") {
    return <div className={styles.userMessageRow}><div className={styles.userMessage}><p>{message.content}</p><small>{message.timestamp}</small></div></div>;
  }

  return (
    <div className={styles.assistantRow}>
      <div className={styles.messageAvatar}><Bot size={16} /></div>
      <div className={styles.assistantMessageGroup}>
        <div className={styles.assistantMessage}>
          <div className={styles.assistantLabel}>LLM 助手 <span>已完成</span></div>
          <p>{message.content}</p>
          {message.citations && <div className={styles.citations}>{message.citations.map((citation) => <button key={citation} type="button"><FileText size={13} />{citation}</button>)}</div>}
        </div>
        <div className={styles.messageActions}>
          <button type="button" title="复制回答" aria-label="复制回答" onClick={() => onCopy(message.content)}><Clipboard size={13} /></button>
          <button type="button" title="回答有帮助" aria-label="回答有帮助"><ThumbsUp size={13} /></button>
          <button type="button" title="回答没有帮助" aria-label="回答没有帮助"><ThumbsDown size={13} /></button>
          <button type="button" title="重新生成" aria-label="重新生成" onClick={onRetry}><RotateCcw size={13} /></button>
          {message.metrics && <span>{message.metrics}</span>}
        </div>
      </div>
    </div>
  );
}
