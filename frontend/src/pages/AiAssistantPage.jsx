import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout.jsx'
import ChatMessage from '../components/chat/ChatMessage.jsx'
import ChatInput from '../components/chat/ChatInput.jsx'
import ChatEmptyState from '../components/chat/ChatEmptyState.jsx'
import LoadingBubble from '../components/chat/LoadingBubble.jsx'
import { suggestedPrompts } from '../constants/dummyData.js'

export default function AiAssistantPage() {
  const [messages, setMessages] = useState([])
  const [isThinking, setIsThinking] = useState(false)

  const handleSend = (text) => {
    setMessages((prev) => [...prev, { id: Date.now(), role: 'user', text }])
    setIsThinking(true)
    // UI-only placeholder reply. Replace with a real API call once the AI endpoint exists.
    setTimeout(() => {
      setIsThinking(false)
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          text: 'This is a sample response. Once connected, answers here will be grounded in your real NetSuite data.',
        },
      ])
    }, 1000)
  }

  return (
    <DashboardLayout title="AI Assistant">
      <div className="flex h-[calc(100vh-8rem)] flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)]">
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6">
          {messages.length === 0 ? (
            <ChatEmptyState prompts={suggestedPrompts} onSelectPrompt={handleSend} />
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} role={message.role} text={message.text} />
              ))}
              {isThinking && <LoadingBubble />}
            </>
          )}
        </div>
        <div className="bg-[var(--color-surface)]">
          <ChatInput onSend={handleSend} disabled={isThinking} />
        </div>
      </div>
    </DashboardLayout>
  )
}
