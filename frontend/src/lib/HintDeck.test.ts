import { fireEvent, render, screen } from '@testing-library/svelte'
import { describe, expect, it, vi } from 'vitest'
import HintDeck from './HintDeck.svelte'

const items = ['First nudge', 'Second', 'Nearly there']
const next = () => screen.getByLabelText('Next hint') as HTMLButtonElement

describe('HintDeck', () => {
  it('shows hints face down until clicked, and moves only as far as the next one', async () => {
    const onreveal = vi.fn()
    const { rerender } = render(HintDeck, { hints: { items, revealed: 0 }, onreveal })
    expect(screen.queryByText('First nudge')).toBeNull()
    expect(next().disabled).toBe(true)
    await fireEvent.click(screen.getByText('Click to see the first hint'))
    expect(onreveal).toHaveBeenCalledOnce()
    await rerender({ hints: { items, revealed: 1 }, onreveal })
    expect(screen.getByText('First nudge')).toBeTruthy()
    await fireEvent.click(next())
    expect(screen.getByText('Click to see the next hint')).toBeTruthy()
    expect(next().disabled).toBe(true)
    await fireEvent.click(screen.getByLabelText('Previous hint'))
    expect(screen.getByText('First nudge')).toBeTruthy()
  })

  it('opens on the newest hint turned over', () => {
    render(HintDeck, { hints: { items, revealed: 3 }, onreveal: () => {} })
    expect(screen.getByText('Nearly there')).toBeTruthy()
    expect(next().disabled).toBe(true)
  })
})
