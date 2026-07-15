import { useState, useEffect, useRef, useCallback } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import ChatMessage from '../components/chat/ChatMessage.jsx'
import ChatInput from '../components/chat/ChatInput.jsx'
import ChatEmptyState from '../components/chat/ChatEmptyState.jsx'
import LoadingBubble from '../components/chat/LoadingBubble.jsx'
import ConversationList from '../components/chat/ConversationList.jsx'
import { suggestedPrompts } from '../constants/dummyData.js'
import { aiApi } from '../services/ai.js'
import ErrorState from '../components/ui/ErrorState.jsx'
import Skeleton from '../components/ui/Skeleton.jsx'

export default function AiAssistantPage() {
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [isThinking, setIsThinking] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const [messagesError, setMessagesError] = useState(null)
  const messagesEndRef = useRef(null)

  const loadHistory = useCallback(async () => {
    setIsLoadingHistory(true)
    setHistoryError(null)
    try {
      const data = await aiApi.getHistory()
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
      const data = await aiApi.getMessages(conversationId)
      setMessages(data.map((m) => ({ id: m.id, role: m.role.toLowerCase(), text: m.content })))
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

  const handleSend = async (text) => {
    setMessagesError(null)
    const userMessage = { id: `temp-${Date.now()}`, role: 'user', text }
    setMessages((prev) => [...prev, userMessage])
    setIsThinking(true)

    try {
      const res = await aiApi.chat(text, activeConversationId)
      const assistantMessage = {
        id: res.conversation_id ? `res-${res.conversation_id}` : `temp-${Date.now() + 1}`,
        role: 'assistant',
        text: res.answer,
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
    }
  }

  const handleSelectConversation = (id) => {
    setActiveConversationId(id)
    setMessagesError(null)
  }

  const handleNewConversation = () => {
    setActiveConversationId(null)
    setMessages([])
    setMessagesError(null)
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
      return <ChatEmptyState prompts={suggestedPrompts} onSelectPrompt={handleSend} />
    }
    return (
      <>
        {messages.map((message) => (
          <ChatMessage key={message.id} role={message.role} text={message.text} />
        ))}
        {isThinking && <LoadingBubble />}
        <div ref={messagesEndRef} />
      </>
    )
  }

  return (
    <DashboardLayout title="AI Assistant">
      <div className="flex h-[calc(100vh-8rem)] overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)]">
        <ConversationList
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          isLoading={isLoadingHistory}
          error={historyError}
          onRetry={loadHistory}
        />
        <div className="flex flex-1 flex-col min-w-0">
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6">
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
            <ChatInput onSend={handleSend} disabled={isThinking || isLoadingMessages} />
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
