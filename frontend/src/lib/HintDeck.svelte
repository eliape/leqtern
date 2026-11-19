<script lang="ts">
  import { type CitableDocs, renderMarkdown } from './markdown'
  import type { Hints } from './api'

  type Props = {
    hints: Hints
    /** The reader turned over the next hint. */
    onreveal: () => void
    /** What the hints' citations can point at, as in answers. */
    docs?: CitableDocs
  }

  let { hints, onreveal, docs }: Props = $props()

  const total = $derived(hints.items.length)
  // Which card is on top: the newest one turned over, or the first while none are.
  const newest = () => Math.max(0, Math.min(hints.revealed, hints.items.length) - 1)
  let shown = $state(newest())
  // The next card face down can be looked at, but nothing past it.
  const last = $derived(Math.min(hints.revealed, total - 1))
  const faceDown = $derived(shown >= hints.revealed)
  // Cards still under the top one, drawn as edges behind it (at most two).
  const under = $derived(Math.min(2, total - 1 - shown))

  function reveal() {
    if (!faceDown) return
    onreveal()
  }

  function go(step: number) {
    shown = Math.max(0, Math.min(last, shown + step))
  }

  function key(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') go(-1)
    else if (event.key === 'ArrowRight') go(1)
    else return
    event.preventDefault()
  }
</script>

<div class="hints" role="group" aria-label="Hints">
  <div class="head">
    <span class="title">Hints</span>
    <span class="progress">{hints.revealed} of {total} shown</span>
  </div>

  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_static_element_interactions -->
  <div class="deck" style:--under={under} tabindex="0" onkeydown={key} aria-label="Hint cards, arrow keys move between them">
    {#each { length: under } as _, i (i)}
      <div class="edge" style:--n={i + 1} aria-hidden="true"></div>
    {/each}
    {#key `${shown}/${faceDown}`}
      {#if faceDown}
        <button type="button" class="card back" onclick={reveal}>
          <span class="number">Hint {shown + 1}</span>
          <span class="cta">{shown === 0 ? 'Click to see the first hint' : 'Click to see the next hint'}</span>
          {#if shown === total - 1 && total > 1}<span class="note">The last and most helpful one</span>{/if}
        </button>
      {:else}
        <div class="card face" aria-live="polite">
          <span class="number">Hint {shown + 1} of {total}</span>
          <div class="markdown">{@html renderMarkdown(hints.items[shown], docs)}</div>
        </div>
      {/if}
    {/key}
  </div>

  <div class="nav">
    <button type="button" class="arrow" aria-label="Previous hint" disabled={shown === 0} onclick={() => go(-1)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6" /></svg>
    </button>
    <div class="dots" aria-hidden="true">
      {#each hints.items as _, i (i)}
        <span class="dot" class:seen={i < hints.revealed} class:current={i === shown}></span>
      {/each}
    </div>
    <button type="button" class="arrow" aria-label="Next hint" disabled={shown >= last} onclick={() => go(1)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
    </button>
  </div>
</div>

<style>
  .hints {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
  }
  .title {
    font-weight: 600;
    color: var(--hint);
  }
  .progress {
    font-size: 0.8rem;
    color: var(--muted);
  }

  .deck {
    position: relative;
    isolation: isolate;
    display: grid;
    /* Room below for the edges of the cards underneath. */
    padding-bottom: calc(var(--under) * 5px);
    border-radius: var(--radius);
  }
  .deck:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .edge {
    position: absolute;
    left: calc(var(--n) * 6px);
    right: calc(var(--n) * 6px);
    bottom: calc((var(--under) - var(--n)) * 5px);
    height: 2rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    z-index: calc(-1 * var(--n));
  }
  .card {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    min-height: 5.5rem;
    padding: 0.65rem 0.8rem;
    border: 1px solid color-mix(in srgb, var(--hint) 40%, var(--border));
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.08);
    animation: flip 0.28s cubic-bezier(0.33, 1, 0.68, 1);
    text-align: left;
    color: inherit;
    font: inherit;
  }
  @keyframes flip {
    from {
      transform: perspective(600px) rotateY(-70deg);
      opacity: 0.3;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      animation: none;
    }
  }
  .back {
    align-items: center;
    justify-content: center;
    text-align: center;
    cursor: pointer;
    background: repeating-linear-gradient(
        135deg,
        transparent 0 10px,
        color-mix(in srgb, var(--hint) 6%, transparent) 10px 20px
      ),
      color-mix(in srgb, var(--hint) 8%, var(--surface));
  }
  .back:hover {
    border-color: var(--hint);
  }
  .back:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .number {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--hint);
  }
  .cta {
    font-weight: 600;
  }
  .note {
    font-size: 0.8rem;
    color: var(--muted);
  }
  .face .markdown :global(p:first-child) {
    margin-top: 0;
  }
  .face .markdown :global(p:last-child) {
    margin-bottom: 0;
  }

  .nav {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
  }
  .arrow {
    display: grid;
    place-items: center;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--surface);
    color: inherit;
    cursor: pointer;
  }
  .arrow:hover:not(:disabled) {
    background: var(--hover);
  }
  .arrow:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .arrow:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .arrow svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .dots {
    display: flex;
    gap: 0.35rem;
  }
  .dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--hint) 60%, var(--border));
  }
  .dot.seen {
    background: color-mix(in srgb, var(--hint) 55%, transparent);
  }
  .dot.current {
    background: var(--hint);
    border-color: var(--hint);
  }
</style>
