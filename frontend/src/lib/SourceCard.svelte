<script lang="ts">
  import type { CardHover } from './cardHover.svelte'
  import type { Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    hover: CardHover
    /** Beside the sidebar, centred on the row; or below a tab, from its left edge. */
    placement: 'right' | 'below'
    /** Called as the pointer comes onto the card and leaves it. */
    onhover?: (inside: boolean) => void
  }

  let { workspace, hover, placement, onhover }: Props = $props()

  /** The page count after the kind, once known. While indexing, the kind line already counts pages. */
  function pagesLabel(id: string): string {
    const state = workspace.indexing[id]
    if (!state?.pageCount || state.status === 'indexing') return ''
    return ` · ${state.pageCount} ${state.pageCount === 1 ? 'page' : 'pages'}`
  }

  function kindLabel(id: string): string {
    const state = workspace.indexing[id]
    if (state?.kind) return state.kind[0].toUpperCase() + state.kind.slice(1)
    switch (state?.status) {
      case 'uploading':
      case 'queued':
        return 'Not indexed yet'
      case 'indexing':
        return state.pageCount ? `Indexing, ${state.pagesDone} of ${state.pageCount} pages` : 'Indexing…'
      case 'error':
        return 'Could not be indexed'
      default:
        // Indexed before kinds were recorded, or not known to the backend yet.
        return state?.status === 'ready' ? 'PDF' : 'Not indexed yet'
    }
  }

  /** When a question was last sent in any of the topic's discussions, as "18 h ago". */
  function lastChatLabel(topicId: string): string {
    const topic = workspace.topics.find((t) => t.id === topicId)
    const chats = topic?.chats.filter((c) => c.messages.length) ?? []
    if (chats.length === 0) return 'No chats yet'
    const last = Math.max(...chats.map((c) => c.updatedAt))
    // Saved before times were recorded.
    if (!last) return 'Last chat: not known'
    const minutes = Math.floor((Date.now() - last) / 60_000)
    if (minutes < 1) return 'Last chat just now'
    if (minutes < 60) return `Last chat ${minutes} min ago`
    if (minutes < 24 * 60) return `Last chat ${Math.floor(minutes / 60)} h ago`
    const days = Math.floor(minutes / (24 * 60))
    if (days < 30) return `Last chat ${days} ${days === 1 ? 'day' : 'days'} ago`
    return `Last chat ${new Date(last).toLocaleDateString(undefined, { dateStyle: 'medium' })}`
  }

  function uploadedLabel(seconds: number | undefined): string {
    if (!seconds) return 'Not known yet'
    return new Date(seconds * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  }
</script>

{#if hover.spot && workspace.topics.some((t) => t.id === hover.spot?.id)}
  {@const topic = workspace.topics.find((t) => t.id === hover.spot?.id)!}
  <div
    class="source-card topic-card {placement}"
    role="tooltip"
    style:top="{hover.spot.y}px"
    style:left="{hover.spot.x}px"
    onpointerenter={() => {
      hover.keep()
      onhover?.(true)
    }}
    onpointerleave={() => {
      hover.leave()
      onhover?.(false)
    }}
  >
    <div class="source-title">{topic.name}</div>
    <div class="source-kind">{lastChatLabel(topic.id)}</div>
  </div>
{:else if hover.spot && workspace.docs[hover.spot.id]}
  {@const id = hover.spot.id}
  {@const state = workspace.indexing[id]}
  <div
    class="source-card {placement}"
    role="tooltip"
    style:top="{hover.spot.y}px"
    style:left="{hover.spot.x}px"
    onpointerenter={() => {
      hover.keep()
      onhover?.(true)
    }}
    onpointerleave={() => {
      hover.leave()
      onhover?.(false)
    }}
  >
    <div class="source-title">{workspace.docName(id)}</div>
    <div class="source-kind">{kindLabel(id)}{pagesLabel(id)}</div>
    <!-- The file it came from, on a second card while the icon (or that card) is hovered. -->
    <div class="info">
      <button type="button" class="info-button" aria-label="File details">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
      </button>
      <div class="info-card">
        <div class="info-label">File</div>
        <div class="info-value">{state?.fileName ?? workspace.docs[id].name}</div>
        <div class="info-label">Uploaded</div>
        <div class="info-value">{uploadedLabel(state?.uploaded)}</div>
      </div>
    </div>
  </div>
{/if}

<style>
  .source-card {
    position: fixed;
    /* Under the sidebar (30) and the tab row (26), so it slides out from beneath them. */
    z-index: 25;
    /* Always this wide: a long title wraps rather than widening the card. */
    box-sizing: border-box;
    width: 16rem;
    padding: 0.5rem 2rem 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 4px 14px rgb(0 0 0 / 0.12);
    white-space: normal;
  }
  /* Beside the sidebar, centred on the row, sliding from one source to the next. */
  .source-card.right {
    transform: translateY(-50%);
    transition: top 0.15s ease;
    animation: card-in-right 0.15s ease-out;
  }
  /* Below a tab, sliding along the row from one tab to the next. */
  .source-card.below {
    transition: left 0.15s ease;
    animation: card-in-below 0.15s ease-out;
  }
  /* On appearing, it starts 90% in place and fades in: from the sidebar's side, or from the tab row. */
  @keyframes card-in-right {
    from {
      opacity: 0;
      transform: translate(-10%, -50%);
    }
  }
  @keyframes card-in-below {
    from {
      opacity: 0;
      transform: translateY(-10%);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .source-card {
      transition: none;
      animation: none !important;
    }
  }
  /* No (i) icon in the corner, so no room kept for it. */
  .source-card.topic-card {
    padding-right: 0.75rem;
  }
  .source-title {
    font-size: 0.85rem;
    font-weight: 600;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }
  .source-kind {
    margin-top: 0.125rem;
    font-size: 0.75rem;
    color: var(--muted);
  }

  /* The icon sits in the card's top right corner; its card is placed against the whole card. */
  .info-button {
    position: absolute;
    top: 0.375rem;
    right: 0.375rem;
    display: grid;
    place-items: center;
    width: 1.25rem;
    height: 1.25rem;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: none;
    color: var(--muted);
    cursor: default;
  }
  .info-button:hover,
  .info:focus-within .info-button {
    color: inherit;
    background: var(--hover);
  }
  .info-button svg {
    width: 0.95rem;
    height: 0.95rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
  /* Another card beside this one (below it, for a tab). An invisible strip bridges the gap, so the pointer can cross to it. */
  .info-card {
    display: none;
    position: absolute;
    top: -1px;
    left: calc(100% + 0.5rem);
    box-sizing: border-box;
    /* As wide as the card itself. */
    width: calc(100% + 2px);
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 4px 14px rgb(0 0 0 / 0.12);
  }
  .info-card::before {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    right: 100%;
    width: 0.75rem;
  }
  .below .info-card {
    top: calc(100% + 0.5rem);
    left: -1px;
  }
  .below .info-card::before {
    top: auto;
    bottom: 100%;
    right: 0;
    left: 0;
    width: auto;
    height: 0.75rem;
  }
  .info:hover .info-card,
  .info:focus-within .info-card {
    display: block;
  }
  .info-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
  }
  .info-value {
    margin-bottom: 0.375rem;
    font-size: 0.8rem;
    overflow-wrap: anywhere;
  }
  .info-value:last-child {
    margin-bottom: 0;
  }
</style>
