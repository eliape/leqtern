import type { Chat } from './workspace.svelte'

/** When a question was last sent in a discussion, as "18 h ago". */
export function lastChatLabel(chat: Chat, now = Date.now()): string {
  if (chat.messages.length === 0) return 'No messages yet'
  // Saved before times were recorded.
  if (!chat.updatedAt) return 'Not known'
  const minutes = Math.floor((now - chat.updatedAt) / 60_000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`
  const days = Math.floor(minutes / (24 * 60))
  if (days < 30) return `${days} ${days === 1 ? 'day' : 'days'} ago`
  return new Date(chat.updatedAt).toLocaleDateString(undefined, { dateStyle: 'medium' })
}
