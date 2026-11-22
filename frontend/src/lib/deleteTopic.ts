import { discussions, type Workspace } from './workspace.svelte'

/** Delete a topic, after asking first when it holds PDFs or discussions. */
export function confirmDeleteTopic(workspace: Workspace, id: string, name: string) {
  const topic = workspace.topics.find((t) => t.id === id)
  const pdfs = topic?.docIds.length ?? 0
  const chats = topic ? discussions(topic).length : 0
  if (!pdfs && !chats) return workspace.deleteTopic(id)
  const discussed = chats === 1 ? ' and its discussion' : chats ? ` and its ${chats} discussions` : ''
  const closed = pdfs === 1 ? 'close its PDF' : pdfs ? `close its ${pdfs} PDFs` : ''
  const question = closed && discussed ? `“${name}”${discussed}, and ${closed}` : `“${name}”${discussed}${closed && ` and ${closed}`}`
  if (confirm(`Delete ${question}?`)) workspace.deleteTopic(id)
}
