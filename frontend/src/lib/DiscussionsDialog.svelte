<script lang="ts">
  import { tick } from 'svelte'
  import { lastChatLabel } from './lastChat'
  import { chatTitle, discussions, type Chat, type Topic, type Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    /** The topic whose "View all" opened it: the only one picked in the filter at first. */
    topicId: string
    /** A discussion was picked: show it, in its topic. */
    onpick: (topicId: string, chatId: string) => void
    onclose: () => void
  }

  let { workspace, topicId, onpick, onclose }: Props = $props()

  type Sort = 'activity' | 'name'
  const SORTS: { id: Sort; label: string }[] = [
    { id: 'activity', label: 'Last activity' },
    { id: 'name', label: 'Name' },
  ]

  // svelte-ignore state_referenced_locally
  let picked = $state<string[]>([topicId])
  let sort = $state<Sort>('activity')

  // Archived topics after the others, as in the sidebar.
  const topics = $derived([...workspace.topics.filter((t) => !t.archived), ...workspace.topics.filter((t) => t.archived)])

  const rows = $derived.by(() => {
    const list: { topic: Topic; chat: Chat }[] = []
    for (const topic of topics) {
      if (!picked.includes(topic.id)) continue
      for (const chat of discussions(topic)) list.push({ topic, chat })
    }
    if (sort === 'name') list.sort((a, b) => chatTitle(a.chat).localeCompare(chatTitle(b.chat)))
    else list.sort((a, b) => b.chat.updatedAt - a.chat.updatedAt)
    return list
  })

  function togglePicked(id: string) {
    picked = picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id]
  }

  // The filter button's menu, and which of its two lists is showing beside it.
  let filterOpen = $state(false)
  let sub = $state<'topic' | 'sort'>()
  let filterEl = $state<HTMLElement>()
  let hideTimer: ReturnType<typeof setTimeout> | undefined
  $effect(() => () => clearTimeout(hideTimer))

  const menuItems = (selector: string) => Array.from(filterEl?.querySelectorAll<HTMLElement>(selector) ?? [])

  // Opened by the keyboard, the first item takes focus; opened by the pointer, nothing is shaded until hovered.
  async function toggleFilter(event: MouseEvent) {
    filterOpen = !filterOpen
    sub = undefined
    if (filterOpen && event.detail === 0) {
      await tick()
      setTimeout(() => menuItems('.filter-menu > .sub > [role="menuitem"]')[0]?.focus())
    }
  }

  function closeFilter(refocus = false) {
    filterOpen = false
    sub = undefined
    if (refocus) filterEl?.querySelector<HTMLElement>('.filter')?.focus()
  }

  async function showSub(which: 'topic' | 'sort', focus: boolean) {
    clearTimeout(hideTimer)
    sub = which
    if (!focus) return
    await tick()
    menuItems('.sub-menu [role^="menuitem"]')[0]?.focus()
  }

  // Leaving a row for its list crosses a small gap, so the list waits a moment before going.
  function leaveSub() {
    hideTimer = setTimeout(() => (sub = undefined), 150)
  }

  $effect(() => {
    if (!filterOpen) return
    const outside = (event: PointerEvent) => {
      if (!filterEl?.contains(event.target as Node)) closeFilter()
    }
    window.addEventListener('pointerdown', outside, true)
    return () => window.removeEventListener('pointerdown', outside, true)
  })

  function step(list: HTMLElement[], event: KeyboardEvent): boolean {
    const i = list.indexOf(document.activeElement as HTMLElement)
    if (event.key === 'ArrowDown') list[(i + 1) % list.length]?.focus()
    else if (event.key === 'ArrowUp') list[(i - 1 + list.length) % list.length]?.focus()
    else return false
    return true
  }

  function onkeydown(event: KeyboardEvent) {
    const target = event.target as Element
    if (filterOpen && target.closest('.sub-menu')) {
      if (step(menuItems('.sub-menu [role^="menuitem"]'), event)) {
        // moved
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight' || event.key === 'Escape') {
        const which = sub
        sub = undefined
        menuItems(`.sub[data-sub="${which}"] > [role="menuitem"]`)[0]?.focus()
      } else return
    } else if (filterOpen && target.closest('.filter-menu')) {
      if (step(menuItems('.filter-menu > .sub > [role="menuitem"]'), event)) {
        // moved
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        const which = target.closest<HTMLElement>('.sub')?.dataset.sub as 'topic' | 'sort' | undefined
        if (which) showSub(which, true)
      } else if (event.key === 'Escape') closeFilter(true)
      else return
    } else if (event.key === 'Escape') onclose()
    else return
    event.preventDefault()
    event.stopPropagation()
  }

  let card = $state<HTMLElement>()
  // Back to wherever focus was (the View all row) once it closes.
  const returnTo = document.activeElement as HTMLElement | null
  $effect(() => {
    card?.focus()
    return () => returnTo?.focus?.()
  })
</script>

<!-- Pressing the dimmed backdrop closes it, like Escape; the × does the same by keyboard. -->
<div class="backdrop" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && onclose()} {onkeydown}>
  <div bind:this={card} class="card" role="dialog" aria-modal="true" aria-labelledby="discussions-title" tabindex="-1">
    <header>
      <h2 id="discussions-title">Discussions</h2>
      <div class="filter-wrap" bind:this={filterEl}>
        <button
          type="button"
          class="chrome-button filter"
          class:pressed={filterOpen}
          aria-label="Filter"
          aria-haspopup="menu"
          aria-expanded={filterOpen}
          onclick={toggleFilter}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16l-6 7.5V19l-4-2v-4.5z" /></svg>
        </button>
        {#if filterOpen}
          <div class="popup-menu filter-menu" role="menu" aria-label="Filter">
            {#each [{ id: 'topic', label: 'Topic' }, { id: 'sort', label: 'Sort by' }] as const as row (row.id)}
              <div class="sub" data-sub={row.id} role="none" onpointerenter={() => showSub(row.id, false)} onpointerleave={leaveSub}>
                <button
                  type="button"
                  role="menuitem"
                  aria-haspopup="menu"
                  aria-expanded={sub === row.id}
                  class:shown={sub === row.id}
                  onclick={(e) => showSub(row.id, e.detail === 0)}
                >
                  <span class="label">{row.label}</span>
                  <svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
                </button>
                {#if sub === row.id && row.id === 'topic'}
                  <div class="popup-menu sub-menu" role="menu" aria-label="Topics">
                    {#each topics as topic (topic.id)}
                      <button type="button" role="menuitemcheckbox" aria-checked={picked.includes(topic.id)} onclick={() => togglePicked(topic.id)}>
                        <svg class="check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                        <span class="label">{topic.name}</span>
                      </button>
                    {/each}
                  </div>
                {:else if sub === row.id}
                  <div class="popup-menu sub-menu" role="menu" aria-label="Sort by">
                    {#each SORTS as s (s.id)}
                      <button type="button" role="menuitemradio" aria-checked={sort === s.id} onclick={() => (sort = s.id)}>
                        <svg class="check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                        <span class="label">{s.label}</span>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
      <button type="button" class="chrome-button close" aria-label="Close discussions" onclick={onclose}>×</button>
    </header>

    <ul class="rows" aria-label="Discussions">
      {#each rows as { topic, chat } (chat.id)}
        <li>
          <button type="button" onclick={() => onpick(topic.id, chat.id)}>
            <span class="title">{chatTitle(chat)}</span>
            <span class="meta">{picked.length > 1 ? `${topic.name} · ` : ''}{lastChatLabel(chat)}</span>
          </button>
        </li>
      {:else}
        <li class="empty">{picked.length ? 'No discussions yet.' : 'Pick a topic in the filter.'}</li>
      {/each}
    </ul>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: center;
    /* One track the size of the window, so the card's height can't stretch it and shift the card. */
    grid-template: minmax(0, 1fr) / minmax(0, 1fr);
    padding: 1rem;
    background: rgb(0 0 0 / 0.35);
  }
  /* Like the Settings dialog, but only the list scrolls, so the filter menu isn't cut off. */
  .card {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: min(44rem, 100%);
    height: min(36rem, 100%);
    box-sizing: border-box;
    padding: 1rem 1.25rem 1.5rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    box-shadow: 0 16px 48px rgb(0 0 0 / 0.3);
    outline: none;
  }
  header {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }
  h2 {
    flex: 1;
    margin: 0;
    font-size: 1.1rem;
  }
  .close {
    font-size: 1.25rem;
  }
  .filter svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linejoin: round;
  }
  .filter {
    color: var(--muted);
  }
  .filter:hover,
  .filter.pressed {
    color: inherit;
  }

  .filter-wrap {
    position: relative;
  }
  .filter-menu {
    position: absolute;
    top: calc(100% + 0.25rem);
    right: 0;
    z-index: 2;
    min-width: 9rem;
  }
  .sub {
    position: relative;
    display: flex;
    flex-direction: column;
  }
  .sub > button,
  .sub-menu > button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.5rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
    outline: none;
  }
  .sub > button:hover,
  .sub > button:focus-visible,
  .sub > button.shown {
    background: var(--hover);
  }
  .label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .chevron {
    color: var(--muted);
  }
  /* To the left of the menu, which sits at the dialog's right edge. */
  .sub-menu {
    position: absolute;
    top: -0.25rem;
    right: calc(100% + 0.25rem);
    width: max-content;
    min-width: 9rem;
    max-width: 16rem;
    max-height: 50vh;
    overflow-y: auto;
  }
  .check {
    visibility: hidden;
  }
  [aria-checked='true'] .check {
    visibility: visible;
  }

  .rows {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    margin: 0 -0.5rem;
    padding: 0;
    list-style: none;
    scrollbar-width: thin;
  }
  .rows button {
    display: flex;
    flex-direction: column;
    gap: 0.0625rem;
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .rows button:hover,
  .rows button:focus-visible {
    background: var(--hover);
    outline: none;
  }
  .title {
    font-size: 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    font-size: 0.75rem;
    color: var(--muted);
  }
  .empty {
    padding: 0.5rem;
    font-size: 0.85rem;
    color: var(--muted);
  }
</style>
