import { useState, useEffect, useRef, useCallback } from 'react'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import ChatMessage from '../../components/chat/ChatMessage.jsx'
import ChatInput from '../../components/chat/ChatInput.jsx'
import ChatEmptyState from '../../components/chat/ChatEmptyState.jsx'
import LoadingBubble from '../../components/chat/LoadingBubble.jsx'
import ConversationList from '../../components/chat/ConversationList.jsx'
import SuggestedPrompts from '../../components/chat/SuggestedPrompts.jsx'
import { suggestedPrompts, businessPrompts } from '../../constants/dummyData.js'
import ErrorState from '../../components/ui/ErrorState.jsx'
import Skeleton from '../../components/ui/Skeleton.jsx'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

export default function AiAssistantPage() {
  const { netSuiteConnected } = useAuth()
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isThinking, setIsThinking] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const [messagesError, setMessagesError] = useState(null)
  const [lastUserMessage, setLastUserMessage] = useState(null)
  const messagesEndRef = useRef(null)
  const chatInputRef = useRef(null)

  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true)
    setHistoryError(null)
    try {
      const data = await clientApi.getAiHistory()
      setConversations(data)
    } catch (err) {
      setHistoryError(err.payload?.message || err.message || 'Failed to load conversations')
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  const loadMessages = useCallback(async (conversationId) => {
    setIsLoadingMessages(true)
    setMessagesError(null)
    try {
      const data = await clientApi.getAiMessages(conversationId)
      const formatted = (data || []).map((m) => ({
        id: m.id,
        role: (m.role || 'assistant').toLowerCase(),
        text: m.content,
        timestamp: m.created_at,
      }))
      setMessages(formatted)
    } catch (err) {
      setMessagesError(err.payload?.message || err.message || 'Failed to load messages')
    } finally {
      setIsLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId)
    } else {
      setMessages([])
      setMessagesError(null)
    }
  }, [activeConversationId, loadMessages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const focusInput = useCallback(() => {
    chatInputRef.current?.focus()
  }, [])

  const handleSend = async (text) => {
    setMessagesError(null)
    const userMessage = { id: `temp-${Date.now()}`, role: 'user', text, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMessage])
    setLastUserMessage(text)
    setIsThinking(true)

    try {
      const res = await clientApi.chat(text, activeConversationId)
      const assistantMessage = {
        id: res.conversation_id ? `res-${res.conversation_id}` : `temp-${Date.now() + 1}`,
        role: 'assistant',
        text: res.answer,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])
      if (!activeConversationId) {
        setActiveConversationId(res.conversation_id)
      }
      loadHistory()
    } catch (err) {
      setMessagesError(err.payload?.message || err.message || 'Failed to send message')
    } finally {
      setIsThinking(false)
      focusInput()
    }
  }

  const handleRegenerate = async () => {
    if (!lastUserMessage || isThinking) return
    setMessages((prev) => prev.filter((m) => !m.id.startsWith('temp-')))
    await handleSend(lastUserMessage)
  }

  const handleSelectConversation = (id) => {
    setActiveConversationId(id)
    setMessagesError(null)
  }

  const handleNewConversation = () => {
    setActiveConversationId(null)
    setMessages([])
    setMessagesError(null)
    setLastUserMessage(null)
  }

  const renderMessageArea = () => {
    if (isLoadingMessages) {
      return (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-3/4" />
          ))}
        </div>
      )
    }
    if (messages.length === 0) {
      return (
        <ChatEmptyState prompts={[...suggestedPrompts, ...businessPrompts]} onSelectPrompt={handleSend} />
      )
    }
    return (
      <>
        {messages.map((message, idx) => {
          const isLastAssistant = message.role === 'assistant' && idx === messages.length - 1
          return (
            <ChatMessage
              key={message.id}
              role={message.role}
              text={message.text}
              timestamp={message.timestamp}
              onRegenerate={isLastAssistant ? handleRegenerate : undefined}
              showContextBadge={isLastAssistant && netSuiteConnected}
            />
          )
        })}
        {isThinking && <LoadingBubble />}
        <div ref={messagesEndRef} />
      </>
    )
  }

  return (
    <ClientLayout title="AI Assistant" breadcrumb="AI Assistant">
      <div className="flex h-[calc(100vh-13rem)] overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)]">
        <ConversationList
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          isLoading={isLoadingHistory}
          error={historyError}
          onRetry={loadHistory}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
            {messagesError ? (
              <ErrorState
                message={messagesError}
                onRetry={activeConversationId ? () => loadMessages(activeConversationId) : undefined}
              />
            ) : (
              renderMessageArea()
            )}
          </div>
          <div className="bg-[var(--color-surface)]">
            <div className="border-t border-[var(--color-border)] px-4 pt-3 pb-1">
              <SuggestedPrompts prompts={[...suggestedPrompts, ...businessPrompts]} onSelect={handleSend} />
            </div>
            <ChatInput ref={chatInputRef} onSend={handleSend} disabled={isThinking || isLoadingMessages} />
          </div>
        </div>
      </div>
    </ClientLayout>
  )
}
