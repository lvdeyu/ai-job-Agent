import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Input, Tag, Typography } from "antd";
import { Bot, Loader2, Send, User } from "lucide-react";

import { API_BASE, type InterviewSession } from "../App";

const { Text } = Typography;

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  phase?: string;
  streaming?: boolean;
}

interface InterviewChatProps {
  session: InterviewSession;
  token: string;
  onSessionUpdate: (session: InterviewSession) => void;
  onFinish: () => void;
  finishLoading?: boolean;
}

interface AgentEventItem {
  id: string;
  event_type: string;
  node_name?: string | null;
  detail_json?: string;
  created_at?: string;
}

const PHASE_LABELS: Record<string, string> = {
  opening: "破冰/自我介绍",
  probing: "提问",
  wrap_up: "用户反问",
  report: "结束"
};

export default function InterviewChat({
  session,
  token,
  onSessionUpdate,
  onFinish,
  finishLoading
}: InterviewChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<string>("probing");
  const [events, setEvents] = useState<AgentEventItem[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/interviews/${session.id}/messages`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const data = (await response.json()) as Array<{
          id: string;
          role: string;
          content: string;
          phase?: string | null;
        }>;
        if (cancelled) return;
        const loaded = data.map((item) => ({
          id: item.id,
          role: item.role as "user" | "assistant",
          content: item.content,
          phase: item.phase ?? undefined
        }));
        setMessages(loaded);
        if (loaded.length > 0 && loaded[loaded.length - 1].phase) {
          setPhase(loaded[loaded.length - 1].phase as string);
        }
      } catch {
        // 消息加载失败时保持空列表，不打断页面。
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session.id, token]);

  useEffect(() => {
    if (messages.length === 0 && session.current_turn && session.status === "running") {
      setMessages([
        {
          id: `turn:${session.current_turn.id}`,
          role: "assistant",
          content: session.current_turn.question_text,
          phase: session.current_turn.question_type ?? "probing"
        }
      ]);
      setPhase(session.current_turn.question_type ?? "probing");
    }
  }, [messages.length, session.current_turn, session.status]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  useEffect(() => {
    if (session.status !== "completed") return;
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(`${API_BASE}/interviews/${session.id}/events`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const data = (await response.json()) as AgentEventItem[];
        if (!cancelled) setEvents(data);
      } catch {
        // 过程还原加载失败时静默忽略。
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session.id, session.status, token]);

  const sendMessage = useCallback(async () => {
    const content = input.trim();
    if (!content || sending) return;
    setInput("");
    setError(null);
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content }
    ]);
    const controller = new AbortController();
    try {
      const response = await fetch(`${API_BASE}/interviews/${session.id}/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ content }),
        signal: controller.signal
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
          | { error?: { message?: string }; detail?: string }
          | null;
        throw new Error(body?.error?.message ?? body?.detail ?? "对话请求失败");
      }
      if (!response.body) {
        throw new Error("当前浏览器不支持流式响应");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantStarted = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data:")) continue;
            let event: {
              type?: string;
              message?: string;
              phase?: string;
              session?: InterviewSession;
              tool?: string;
              summary?: string;
            };
            try {
              event = JSON.parse(line.slice(5).trim());
            } catch {
              continue;
            }
            if (event.type === "assistant_message") {
              if (!assistantStarted) {
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `assistant-${Date.now()}`,
                    role: "assistant",
                    content: "",
                    phase: event.phase,
                    streaming: true
                  }
                ]);
                assistantStarted = true;
              }
              setMessages((prev) =>
                prev.map((item) =>
                  item.streaming
                    ? { ...item, content: item.content + (event.message ?? "") }
                    : item
                )
              );
            } else if (event.type === "phase") {
              setPhase(event.phase ?? "probing");
            } else if (event.type === "session_state" && event.session) {
              onSessionUpdate(event.session);
              if (event.session.status === "completed") {
                setPhase("report");
              }
            } else if (event.type === "error") {
              setError(event.message ?? "对话失败，请稍后重试。");
            } else if (event.type === "done") {
              setMessages((prev) =>
                prev.map((item) => (item.streaming ? { ...item, streaming: false } : item))
              );
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setSending(false);
    }
  }, [input, sending, session.id, token, onSessionUpdate]);

  return (
    <div className="interview-chat">
      <div className="chat-toolbar">
        <Tag color="purple">{PHASE_LABELS[phase] ?? "面试中"}</Tag>
        <Button onClick={onFinish} loading={finishLoading} size="small">
          结束面试并生成报告
        </Button>
      </div>
      <div className="chat-messages">
        {messages.map((item) => (
          <div key={item.id} className={`chat-message ${item.role}`}>
            <div className="chat-avatar">
              {item.role === "assistant" ? <Bot size={16} /> : <User size={16} />}
            </div>
            <div className="chat-bubble">
              <Text>{item.content}</Text>
              {item.streaming && <Loader2 size={14} className="chat-streaming" />}
            </div>
          </div>
        ))}
        {sending && (
          <div className="chat-message assistant">
            <div className="chat-avatar">
              <Bot size={16} />
            </div>
            <div className="chat-bubble chat-thinking">
              <Loader2 size={14} className="chat-streaming" />
              面试官思考中...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {error && <div className="chat-error">{error}</div>}
      {events.length > 0 && (
        <div className="chat-replay">
          <Text strong>过程还原</Text>
          <div className="chat-replay-list">
            {events.map((event) => (
              <div key={event.id} className="chat-replay-item">
                <Tag>{event.event_type}</Tag>
                <Text type="secondary">{event.node_name ?? "—"}</Text>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="chat-composer">
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入你的回答，尽量包含项目证据、实现步骤和边界说明。"
          autoSize={{ minRows: 2, maxRows: 5 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              void sendMessage();
            }
          }}
        />
        <Button
          type="primary"
          icon={<Send size={14} />}
          loading={sending}
          onClick={() => void sendMessage()}
        >
          发送
        </Button>
      </div>
    </div>
  );
}
