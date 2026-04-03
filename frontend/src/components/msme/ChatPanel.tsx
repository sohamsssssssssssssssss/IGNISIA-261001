import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  ArrowUp,
  ChevronLeft,
  Sparkles,
  X,
} from 'lucide-react';
import styles from './ChatPanel.module.css';
import SourcesPanel from './SourcesPanel';
import type { AppliedRule, GuidelineReference, SimilarCase } from '../../types/sources';

interface LegacyChatSource {
  caseId: string;
  summary: string;
  similarity: number;
}

interface StructuredChatSources {
  similarCases?: SimilarCase[];
  rulesApplied?: AppliedRule[];
  guidelinesReferenced?: GuidelineReference[];
}

type ChatSources = LegacyChatSource[] | StructuredChatSources;

export interface ChatResponse {
  reply: string;
  sessionId: string;
  sources?: ChatSources;
  isStreaming?: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'ai';
  text: string;
  sources?: ChatSources;
  timestamp: Date;
  isStreaming?: boolean;
}

interface ChatPanelProps {
  applicationId: string;
  applicantName: string;
  creditScore: number;
  onSendMessage: (payload: {
    message: string;
    sessionId: string | null;
    applicationId: string;
  }) => Promise<ChatResponse>;
  onStreamMessage?: (
    payload: {
      message: string;
      sessionId: string | null;
      applicationId: string;
    },
    onChunk: (chunk: string) => void,
    onDone: (finalResponse: ChatResponse) => void,
    onError: (err: Error) => void
  ) => void;
  isOpen: boolean;
  onToggle: () => void;
}

function createMessageId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatTimestamp(timestamp: Date): string {
  return timestamp.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function clampSimilarity(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function isLegacyChatSources(value: ChatSources | undefined): value is LegacyChatSource[] {
  return Array.isArray(value);
}

function normalizeMessageSources(value: ChatSources | undefined): {
  similarCases: SimilarCase[];
  rulesApplied: AppliedRule[];
  guidelinesReferenced: GuidelineReference[];
} | null {
  if (!value) {
    return null;
  }

  if (isLegacyChatSources(value)) {
    if (value.length === 0) {
      return null;
    }

    return {
      similarCases: value.map((source) => ({
        existsInHistory: false,
        gstin: source.caseId,
        outcome: 'pending',
        score: Number.NaN,
        similarityScore: clampSimilarity(source.similarity),
        summary: source.summary,
      } as SimilarCase)),
      rulesApplied: [],
      guidelinesReferenced: [],
    };
  }

  const similarCases = value.similarCases ?? [];
  const rulesApplied = value.rulesApplied ?? [];
  const guidelinesReferenced = value.guidelinesReferenced ?? [];

  if (!similarCases.length && !rulesApplied.length && !guidelinesReferenced.length) {
    return null;
  }

  return {
    similarCases,
    rulesApplied,
    guidelinesReferenced,
  };
}

export default function ChatPanel({
  applicationId,
  applicantName,
  creditScore,
  onSendMessage,
  onStreamMessage,
  isOpen,
  onToggle,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);

  const messageContainerRef = useRef<HTMLDivElement | null>(null);
  const bottomSentinelRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const waitTimeoutRef = useRef<number | null>(null);
  const nearBottomRef = useRef(true);

  const starterChips = useMemo(() => ([
    `Why did ${applicantName} score ${creditScore}?`,
    'What documents would improve the score?',
    'Should I approve this loan?',
    'How does this compare to similar businesses?',
  ]), [applicantName, creditScore]);

  const persistSessionId = (nextSessionId: string) => {
    setSessionId(nextSessionId);
    sessionStorage.setItem(`chat_session_${applicationId}`, nextSessionId);
  };

  const clearWaitTimeout = () => {
    if (waitTimeoutRef.current !== null) {
      window.clearTimeout(waitTimeoutRef.current);
      waitTimeoutRef.current = null;
    }
  };

  useEffect(() => {
    const existing = sessionStorage.getItem(`chat_session_${applicationId}`);
    setMessages([]);
    setSessionId(existing);
    setInputValue('');
    setIsWaiting(false);
    clearWaitTimeout();

    return () => {
      clearWaitTimeout();
    };
  }, [applicationId]);

  useEffect(() => {
    if (isOpen) {
      const timer = window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 220);

      return () => window.clearTimeout(timer);
    }

    return undefined;
  }, [isOpen]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  }, [inputValue]);

  useEffect(() => {
    if (!nearBottomRef.current) return;
    bottomSentinelRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, [messages, isWaiting]);

  const handleScroll = () => {
    const container = messageContainerRef.current;
    if (!container) return;

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    nearBottomRef.current = distanceFromBottom <= 80;
  };

  const submitMessage = async (rawText: string) => {
    const trimmed = rawText.trim();
    if (!trimmed || isWaiting) return;

    const payload = {
      applicationId,
      message: trimmed,
      sessionId,
    };

    const userMessage: Message = {
      id: createMessageId('user'),
      role: 'user',
      text: trimmed,
      timestamp: new Date(),
    };

    setMessages((current) => [...current, userMessage]);
    setInputValue('');
    setIsWaiting(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = '40px';
    }

    if (onStreamMessage) {
      const aiMessageId = createMessageId('ai-stream');
      const placeholder: Message = {
        id: aiMessageId,
        role: 'ai',
        text: '',
        timestamp: new Date(),
        isStreaming: true,
      };

      setMessages((current) => [...current, placeholder]);
      setIsWaiting(false);

      onStreamMessage(
        payload,
        (chunk) => {
          setMessages((current) => current.map((message) => (
            message.id === aiMessageId
              ? { ...message, text: `${message.text}${chunk}` }
              : message
          )));
        },
        (finalResponse) => {
          setMessages((current) => current.map((message) => (
            message.id === aiMessageId
              ? {
                ...message,
                isStreaming: false,
                sources: finalResponse.sources,
                text: finalResponse.reply || message.text,
                timestamp: new Date(),
              }
              : message
          )));
          persistSessionId(finalResponse.sessionId);
          setIsWaiting(false);
        },
        (err) => {
          setMessages((current) => current.map((message) => (
            message.id === aiMessageId
              ? {
                ...message,
                isStreaming: false,
                text: err.message || 'The AI is taking longer than expected. Please try again.',
                timestamp: new Date(),
              }
              : message
          )));
          setIsWaiting(false);
        }
      );

      return;
    }

    const fallbackMessageId = createMessageId('ai-timeout');
    waitTimeoutRef.current = window.setTimeout(() => {
      setIsWaiting(false);
      setMessages((current) => {
        if (current.some((message) => message.id === fallbackMessageId)) {
          return current;
        }

        return [
          ...current,
          {
            id: fallbackMessageId,
            role: 'ai',
            text: 'The AI is taking longer than expected. Please try again.',
            timestamp: new Date(),
          },
        ];
      });
    }, 3000);

    try {
      const response = await onSendMessage(payload);
      clearWaitTimeout();
      persistSessionId(response.sessionId);

      const replyMessage: Message = {
        id: fallbackMessageId,
        role: 'ai',
        text: response.reply,
        timestamp: new Date(),
        sources: response.sources,
      };

      setMessages((current) => {
        const existingIndex = current.findIndex((message) => message.id === fallbackMessageId);
        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = replyMessage;
          return next;
        }

        return [...current, replyMessage];
      });
      setIsWaiting(false);
    } catch (error) {
      clearWaitTimeout();
      const errorText = error instanceof Error
        ? error.message
        : 'The AI is taking longer than expected. Please try again.';

      setMessages((current) => {
        const existingIndex = current.findIndex((message) => message.id === fallbackMessageId);
        const errorMessage: Message = {
          id: fallbackMessageId,
          role: 'ai',
          text: errorText,
          timestamp: new Date(),
        };

        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = errorMessage;
          return next;
        }

        return [...current, errorMessage];
      });
      setIsWaiting(false);
    }
  };

  const handleTextareaKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void submitMessage(inputValue);
    }
  };

  const renderPanel = (showMobileClose: boolean) => (
    <section className={styles.panel} aria-label="AI Chat Panel">
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <Sparkles size={16} color="var(--cp-accent)" />
          <div className={`${styles.headingFont} ${styles.headerTitle}`}>
            AI Assistant · {applicantName}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className={`${styles.statusBadge} ${sessionId ? styles.statusActive : styles.statusNew}`}>
            {sessionId ? 'Active' : 'New Session'}
          </span>
          {showMobileClose ? (
            <button
              type="button"
              onClick={onToggle}
              className={styles.mobileClose}
              aria-label="Close AI panel"
            >
              <X size={18} />
            </button>
          ) : null}
        </div>
      </header>

      <div
        ref={messageContainerRef}
        className={styles.messages}
        role="log"
        aria-live="polite"
        aria-busy={isWaiting}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className={styles.starterWrap}>
            <div className={`${styles.bodyFont} ${styles.starterPrompt}`}>
              What would you like to know about this application?
            </div>
            <div className={styles.chips}>
              {starterChips.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className={styles.chip}
                  onClick={() => { void submitMessage(chip); }}
                  disabled={isWaiting}
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((message) => {
          const isUser = message.role === 'user';
          const normalizedSources = !isUser ? normalizeMessageSources(message.sources) : null;

          return (
            <div
              key={message.id}
              className={`${styles.messageRow} ${isUser ? styles.messageUser : styles.messageAi} ${isUser ? styles.userEntry : styles.aiEntry}`}
            >
              <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleAi}`}>
                {message.text}
                {!isUser && message.isStreaming ? <span className={styles.cursor}>|</span> : null}
              </div>

              <div className={`${styles.timestamp} ${isUser ? styles.timestampUser : styles.timestampAi}`}>
                {formatTimestamp(message.timestamp)}
              </div>

              {!isUser && normalizedSources ? (
                <div className={styles.sourcesWrap}>
                  <SourcesPanel
                    similarCases={normalizedSources.similarCases}
                    rulesApplied={normalizedSources.rulesApplied}
                    guidelinesReferenced={normalizedSources.guidelinesReferenced}
                  />
                </div>
              ) : null}
            </div>
          );
        })}

        {isWaiting ? (
          <div className={`${styles.messageRow} ${styles.messageAi} ${styles.aiEntry}`}>
            <div className={`${styles.bubble} ${styles.bubbleAi} ${styles.typingBubble}`} aria-label="AI is typing">
              <span className={styles.dot} />
              <span className={styles.dot} />
              <span className={styles.dot} />
            </div>
          </div>
        ) : null}

        <div ref={bottomSentinelRef} className={styles.sentinel} />
      </div>

      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          onKeyDown={handleTextareaKeyDown}
          className={`${styles.textarea} ${isWaiting ? styles.textareaDisabled : ''}`}
          placeholder="Ask about this application…"
          disabled={isWaiting}
          rows={1}
        />
        <button
          type="button"
          onClick={() => { void submitMessage(inputValue); }}
          className={`${styles.sendButton} ${isWaiting || !inputValue.trim() ? styles.sendButtonDisabled : ''}`}
          disabled={!inputValue.trim() || isWaiting}
          aria-label="Send message"
        >
          <ArrowUp size={18} />
        </button>
      </div>
    </section>
  );

  return (
    <div className={`${styles.root} ${styles.bodyFont}`}>
      <div className={styles.desktopShell}>
        <div className={`${styles.desktopWrapper} ${isOpen ? styles.desktopWrapperOpen : ''}`}>
          <button
            type="button"
            onClick={onToggle}
            className={styles.desktopTab}
            aria-expanded={isOpen}
            aria-label={isOpen ? 'Close AI panel' : 'Open AI panel'}
          >
            <span className={styles.tabInner}>
              {isOpen ? <ChevronLeft size={16} className={styles.tabIcon} /> : <Sparkles size={16} className={styles.tabIcon} />}
              <span>{isOpen ? 'Close' : 'Ask AI'}</span>
            </span>
          </button>
          <div className={styles.desktopPanel}>
            {renderPanel(false)}
          </div>
        </div>
      </div>

      <div className={styles.mobileOnly}>
        {!isOpen ? (
          <button
            type="button"
            onClick={onToggle}
            className={styles.mobileFab}
            aria-expanded={isOpen}
            aria-label="Open AI panel"
          >
            <Sparkles size={22} />
          </button>
        ) : (
          <div className={`${styles.mobileOverlay} ${styles.mobileOverlayOpen}`}>
            <div className={styles.mobileModal}>
              {renderPanel(true)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
