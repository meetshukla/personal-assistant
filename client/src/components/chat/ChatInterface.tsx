"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Trash2, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SettingsModal, { useSettings } from "../SettingsModal";

interface Message {
  id: string;
  role: "user" | "assistant" | "specialist";
  content: string;
  timestamp: string;
  specialistsUsed?: number;
}

interface ChatResponse {
  message: string;
  success: boolean;
  specialists_used: number;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { settings, setSettings } = useSettings();

  // Get user ID from localStorage or fallback to "web_user"
  const getUserId = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem('personal_assistant_user_id') || "web_user";
    }
    return "web_user";
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Load chat history on component mount
  useEffect(() => {
    loadChatHistory();
  }, []);

  // Poll for new notifications every 30 seconds
  useEffect(() => {
    let lastTimestamp = new Date().toISOString();

    const pollForNotifications = async () => {
      try {
        const response = await fetch(`http://localhost:8001/api/chat/notifications?session_id=${getUserId()}&since_timestamp=${lastTimestamp}`);
        if (response.ok) {
          const data = await response.json();
          if (data.messages && data.messages.length > 0) {
            // Filter out any messages that might already exist (only keep assistant messages for notifications)
            const notificationMessages = data.messages.filter((msg: any) => msg.role === 'assistant');

            if (notificationMessages.length > 0) {
              const newMessages = notificationMessages.map((msg: any, index: number) => ({
                id: `notif-${Date.now()}-${index}`,
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp || new Date().toISOString(),
              }));

              // Only add messages that don't already exist based on content similarity
              setMessages(prev => {
                const existingContents = prev.map(m => m.content);
                const trulyNewMessages = newMessages.filter((newMsg: Message) =>
                  !existingContents.some(existing => existing === newMsg.content)
                );
                return trulyNewMessages.length > 0 ? [...prev, ...trulyNewMessages] : prev;
              });

              // Update timestamp to the latest message timestamp
              if (notificationMessages.length > 0) {
                const latestMsg = notificationMessages[notificationMessages.length - 1];
                lastTimestamp = latestMsg.timestamp || new Date().toISOString();
              }

              // Show browser notification if supported (only for new messages)
              if (newMessages.length > 0 && 'Notification' in window && Notification.permission === 'granted') {
                new Notification('Personal Assistant Reminder', {
                  body: newMessages[0]?.content?.substring(0, 100) + '...',
                  icon: '/favicon.ico'
                });
              }
            }
          }
        }
      } catch (error) {
        console.error("Failed to poll for notifications:", error);
      }
    };

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    // Start polling
    const interval = setInterval(pollForNotifications, 30000); // Poll every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const loadChatHistory = async () => {
    try {
      const response = await fetch(`http://localhost:8001/api/chat/history?session_id=${getUserId()}`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages.map((msg: any, index: number) => ({
          id: `${index}`,
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp || new Date().toISOString(),
        })));
      }
    } catch (error) {
      console.error("Failed to load chat history:", error);
      // Don't show error to user for history loading
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    const messageContent = input.trim();
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8001/api/chat/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageContent,
          session_id: getUserId()
        }),
      });

      if (response.ok) {
        const data: ChatResponse = await response.json();

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.message,
          timestamp: new Date().toISOString(),
          specialistsUsed: data.specialists_used,
        };

        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error("Failed to send message");
      }
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      const response = await fetch(`http://localhost:8001/api/chat/history?session_id=${getUserId()}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setMessages([]);
      }
    } catch (error) {
      console.error("Failed to clear history:", error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const isToday = date.toDateString() === now.toDateString();

      if (isToday) {
        return date.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit'
        });
      } else {
        return date.toLocaleDateString([], {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit'
        });
      }
    } catch (error) {
      return '';
    }
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-background via-background to-muted/20">
      {/* Main Chat Container */}
      <div className="flex-1 flex flex-col max-w-5xl mx-auto">
        {/* Header */}
        <header className="flex items-center justify-between p-6 border-b border-border/40 bg-background/80 backdrop-blur-sm">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <Bot className="h-8 w-8 text-primary" />
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full ring-2 ring-background"></div>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground">Personal Assistant</h1>
              <p className="text-sm text-muted-foreground">AI-powered productivity companion</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSettingsOpen(true)}
              className="h-9 w-9 p-0 hover:bg-muted/50"
            >
              <Settings className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearHistory}
              className="h-9 w-9 p-0 hover:bg-muted/50 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6" ref={scrollAreaRef}>
            <div className="py-6 space-y-6">
              {messages.length === 0 && (
                <div className="text-center py-20">
                  <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                    <Bot className="h-10 w-10 text-primary" />
                  </div>
                  <h3 className="text-lg font-medium text-foreground mb-2">Welcome to your Personal Assistant</h3>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    I can help you manage emails, set reminders, schedule tasks, and more. Just type a message to get started!
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2 text-sm text-muted-foreground">
                    <span className="bg-muted/50 px-3 py-1 rounded-full">📧 "Check my emails"</span>
                    <span className="bg-muted/50 px-3 py-1 rounded-full">⏰ "Remind me at 6pm"</span>
                    <span className="bg-muted/50 px-3 py-1 rounded-full">📅 "Schedule a meeting"</span>
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <div
                  key={message.id}
                  className={`flex items-start gap-4 group ${
                    message.role === "user" ? "flex-row-reverse" : ""
                  }`}
                >
                  {/* Avatar */}
                  <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted border-2 border-background shadow-sm"
                  }`}>
                    {message.role === "user" ? (
                      <User className="h-5 w-5" />
                    ) : (
                      <Bot className="h-5 w-5 text-primary" />
                    )}
                  </div>

                  {/* Message Content */}
                  <div className={`flex-1 max-w-[75%] ${message.role === "user" ? "text-right" : ""}`}>
                    {/* Timestamp - positioned at top */}
                    <div className={`text-xs text-muted-foreground mb-2 ${
                      message.role === "user" ? "text-right" : "text-left"
                    }`}>
                      {formatTimestamp(message.timestamp)}
                      {message.specialistsUsed && message.specialistsUsed > 0 && (
                        <Badge variant="secondary" className="ml-2 text-xs h-5">
                          {message.specialistsUsed} specialist{message.specialistsUsed > 1 ? 's' : ''}
                        </Badge>
                      )}
                    </div>

                    {/* Message Bubble */}
                    <div
                      className={`inline-block p-4 rounded-2xl max-w-full ${
                        message.role === "user"
                          ? "bg-primary text-primary-foreground rounded-br-md shadow-lg shadow-primary/20"
                          : "bg-card border border-border/40 rounded-bl-md shadow-sm"
                      }`}
                    >
                      {message.role === "user" ? (
                        <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
                      ) : (
                        <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              h1: ({ children }) => <h1 className="text-base font-bold mb-3 text-foreground">{children}</h1>,
                              h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                              h3: ({ children }) => <h3 className="text-sm font-medium mb-2 text-foreground">{children}</h3>,
                              p: ({ children }) => <p className="mb-3 last:mb-0 text-foreground leading-relaxed">{children}</p>,
                              ul: ({ children }) => <ul className="list-disc list-inside mb-3 space-y-1.5 text-foreground">{children}</ul>,
                              ol: ({ children }) => <ol className="list-decimal list-inside mb-3 space-y-1.5 text-foreground">{children}</ol>,
                              li: ({ children }) => <li className="leading-relaxed text-foreground">{children}</li>,
                              code: ({ children, className }) => {
                                const isInline = !className;
                                return isInline ? (
                                  <code className="bg-muted/70 px-1.5 py-0.5 rounded text-xs font-mono text-foreground">{children}</code>
                                ) : (
                                  <code className="block bg-muted/70 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap overflow-x-auto text-foreground">{children}</code>
                                );
                              },
                              blockquote: ({ children }) => <blockquote className="border-l-4 border-primary/30 pl-4 italic mb-3 text-muted-foreground">{children}</blockquote>,
                              strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                              em: ({ children }) => <em className="italic text-foreground">{children}</em>,
                              a: ({ children, href }) => <a href={href} className="text-primary underline hover:no-underline font-medium" target="_blank" rel="noopener noreferrer">{children}</a>,
                              table: ({ children }) => <table className="border-collapse border border-border mb-3 text-sm rounded-lg overflow-hidden">{children}</table>,
                              th: ({ children }) => <th className="border border-border px-3 py-2 bg-muted font-medium text-left text-foreground">{children}</th>,
                              td: ({ children }) => <td className="border border-border px-3 py-2 text-foreground">{children}</td>,
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-muted border-2 border-background shadow-sm flex items-center justify-center">
                    <Bot className="h-5 w-5 text-primary" />
                  </div>
                  <div className="bg-card border border-border/40 p-4 rounded-2xl rounded-bl-md shadow-sm">
                    <div className="flex items-center space-x-2">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                        <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                      </div>
                      <span className="text-sm text-muted-foreground">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Input Area */}
          <div className="p-6 border-t border-border/40 bg-background/80 backdrop-blur-sm">
            <div className="flex gap-3 max-w-4xl mx-auto">
              <div className="relative flex-1">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your message..."
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  className="pr-12 h-12 text-sm bg-background border-border/60 focus:border-primary/60 rounded-xl shadow-sm"
                />
                <Button
                  onClick={sendMessage}
                  disabled={isLoading || !input.trim()}
                  size="sm"
                  className="absolute right-1 top-1 h-10 w-10 p-0 rounded-lg shadow-sm"
                >
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSave={setSettings}
      />
    </div>
  );
}