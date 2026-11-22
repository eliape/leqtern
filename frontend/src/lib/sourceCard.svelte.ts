/**
 * When a source's hover card shows, for the sources in the sidebar and the tabs. It appears after
 * a short rest on one, then moves straight to the next one hovered, and goes only once the pointer
 * has been off the sources and the card for a moment, so it can be moved onto the card.
 */
export type CardSpot = { id: string; x: number; y: number }

const DELAY_MS = 400
const GRACE_MS = 120

export class CardHover {
  spot = $state<CardSpot>()
  private showTimer: ReturnType<typeof setTimeout> | undefined
  private hideTimer: ReturnType<typeof setTimeout> | undefined

  /** Hovering a source: `place` says where its card goes, measured when it shows. */
  show(id: string, place: () => { x: number; y: number }) {
    this.clear()
    const put = () => (this.spot = { id, ...place() })
    if (this.spot) put()
    else this.showTimer = setTimeout(put, DELAY_MS)
  }

  /** The pointer left a source or the card. */
  leave() {
    clearTimeout(this.showTimer)
    if (this.spot) this.hideTimer = setTimeout(() => (this.spot = undefined), GRACE_MS)
  }

  /** The pointer came onto the card: it stays. */
  keep() {
    clearTimeout(this.hideTimer)
  }

  close() {
    this.clear()
    this.spot = undefined
  }

  clear() {
    clearTimeout(this.showTimer)
    clearTimeout(this.hideTimer)
  }
}
