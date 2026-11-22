import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'
import SourceCard from './SourceCard.svelte'
import { CardHover } from './cardHover.svelte'
import type { Workspace } from './workspace.svelte'

function chat(id: string, title: string, updatedAt: number, messages = 2) {
  return { id, title, mode: 'normal', updatedAt, messages: Array.from({ length: messages }, () => ({ role: 'user', content: 'q' })) }
}

function showFor(id: string, chats: ReturnType<typeof chat>[]) {
  const workspace = { topics: [{ id: 't', name: 'Calculus', chats }], docs: {}, indexing: {} } as unknown as Workspace
  const hover = new CardHover()
  hover.spot = { id, x: 0, y: 0 }
  render(SourceCard, { workspace, hover, placement: 'right' })
  return screen.getByRole('tooltip')
}

describe('SourceCard for a discussion', () => {
  it('shows its full title and how long ago it was last chatted in', () => {
    const card = showFor('c1', [chat('c1', 'Limits of rational functions', Date.now() - 18 * 3600_000)])
    expect(card).toHaveTextContent('Limits of rational functions')
    expect(card).toHaveTextContent('18 h ago')
  })

  it('counts minutes under an hour', () => {
    expect(showFor('c', [chat('c', 'a', Date.now() - 5 * 60_000)])).toHaveTextContent('5 min ago')
  })

  it('counts days after a day', () => {
    expect(showFor('c', [chat('c', 'a', Date.now() - 3 * 86_400_000)])).toHaveTextContent('3 days ago')
  })
})
