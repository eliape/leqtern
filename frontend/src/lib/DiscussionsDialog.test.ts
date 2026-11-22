import { fireEvent, render, screen, within } from '@testing-library/svelte'
import { describe, expect, it, vi } from 'vitest'
import TopicsSidebar from './TopicsSidebar.svelte'
import { Workspace, type Topic } from './workspace.svelte'

const HOUR = 3600_000

/** A topic with `n` discussions, the first asked most recently. */
function addTopic(ws: Workspace, name: string, n: number, title = (i: number) => `${name} ${i + 1}`): Topic {
  const topic = ws.createTopic(name)
  topic.chats = Array.from({ length: n }, (_, i) => ({
    id: `${name}-${i}`,
    title: title(i),
    mode: 'normal' as const,
    updatedAt: Date.now() - (i + 1) * HOUR,
    messages: [{ role: 'user' as const, content: 'q' }],
  })) as unknown as Topic['chats']
  topic.chatId = topic.chats[0].id
  return topic
}

function sidebar(ws: Workspace, onopenchat = vi.fn()) {
  render(TopicsSidebar, { workspace: ws, open: true, pinned: true, onopenchat })
  return onopenchat
}

describe('Discussions in the sidebar', () => {
  it('lists up to 9, then ends in View all', () => {
    const ws = new Workspace()
    addTopic(ws, 'Calc', 9)
    sidebar(ws)
    expect(screen.queryByRole('button', { name: 'View all' })).not.toBeInTheDocument()
  })

  it('opens every discussion from View all, and opens the one picked in its topic', async () => {
    const ws = new Workspace()
    const algebra = addTopic(ws, 'Algebra', 2)
    const calc = addTopic(ws, 'Calc', 12)
    const opened = sidebar(ws)
    const sidebarRows = within(document.querySelector<HTMLElement>('.discussions')!).getAllByRole('button')
    expect(sidebarRows.filter((b) => /^Calc \d+$/.test(b.textContent!.trim()))).toHaveLength(9)
    await fireEvent.click(screen.getByRole('button', { name: 'View all' }))

    const dialog = within(screen.getByRole('dialog', { name: 'Discussions' }))
    const rows = () => dialog.getAllByRole('button', { name: /h ago/ }).map((b) => b.querySelector('.title')!.textContent)
    // Only the topic it was opened from, newest first.
    expect(rows()).toHaveLength(12)
    expect(rows()[0]).toBe('Calc 1')

    // The filter adds a topic and sorts by name.
    await fireEvent.click(dialog.getByRole('button', { name: 'Filter' }))
    await fireEvent.click(dialog.getByRole('menuitem', { name: /Topic/ }))
    expect(dialog.getByRole('menuitemcheckbox', { name: 'Calc' })).toHaveAttribute('aria-checked', 'true')
    expect(dialog.getByRole('menuitemcheckbox', { name: 'Algebra' })).toHaveAttribute('aria-checked', 'false')
    await fireEvent.click(dialog.getByRole('menuitemcheckbox', { name: 'Algebra' }))
    expect(rows()).toHaveLength(14)
    await fireEvent.click(dialog.getByRole('menuitem', { name: /Sort by/ }))
    await fireEvent.click(dialog.getByRole('menuitemradio', { name: 'Name' }))
    expect(rows().slice(0, 3)).toEqual(['Algebra 1', 'Algebra 2', 'Calc 1'])

    // Picking one opens its topic and discussion, and closes the dialog.
    await fireEvent.click(dialog.getByRole('button', { name: /^Algebra 2/ }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(ws.activeTopicId).toBe(algebra.id)
    expect(algebra.chatId).toBe('Algebra-1')
    expect(opened).toHaveBeenCalled()
    expect(calc.chats).toHaveLength(12)
  })
})
