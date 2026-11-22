<script lang="ts">
  import { tick } from 'svelte'
  import type { Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    /** Pick a PDF from the computer, as Upload source in the sidebar does. */
    onupload: () => void
  }

  let { workspace, onupload }: Props = $props()

  let open = $state(false)
  // The list of the topic's sources beside "Open source".
  let subOpen = $state(false)
  let root = $state<HTMLElement>()

  const topic = $derived(workspace.activeTopic)
  const sources = $derived(topic?.docIds ?? [])

  const items = (selector: string) => Array.from(root?.querySelectorAll<HTMLElement>(selector) ?? [])
  const mainItems = () => items('.main-menu > [role="menuitem"], .main-menu > .sub > [role="menuitem"]')
  const subItems = () => items('.sub-menu [role="menuitem"]')

  // Opened by the keyboard, the first item takes focus; opened by the pointer, nothing is shaded until hovered.
  function toggle(event: MouseEvent) {
    open = !open
    subOpen = false
    if (open && event.detail === 0) {
      const host = (event.currentTarget as HTMLElement).parentElement
      // The menu is drawn by the next turn, even when opened from inside a key press.
      setTimeout(() => host?.querySelector<HTMLElement>('.main-menu [role="menuitem"]')?.focus())
    }
  }

  function close(refocus = false) {
    open = false
    subOpen = false
    if (refocus) root?.querySelector<HTMLElement>('.add-tab')?.focus()
  }

  // Leaving the row for the list crosses a small gap, so the list waits a moment before going.
  let hideTimer: ReturnType<typeof setTimeout> | undefined
  function leaveSources() {
    hideTimer = setTimeout(() => (subOpen = false), 150)
  }
  $effect(() => () => clearTimeout(hideTimer))

  async function showSources(focus: boolean) {
    clearTimeout(hideTimer)
    subOpen = true
    if (!focus) return
    await tick()
    subItems()[0]?.focus()
  }

  function pick(id: string) {
    close()
    workspace.openDoc(id)
  }

  function upload() {
    close()
    onupload()
  }

  $effect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (!root?.contains(event.target as Node)) close()
    }
    const blur = () => close()
    window.addEventListener('pointerdown', outside, true)
    window.addEventListener('blur', blur)
    return () => {
      window.removeEventListener('pointerdown', outside, true)
      window.removeEventListener('blur', blur)
    }
  })

  function move(list: HTMLElement[], event: KeyboardEvent) {
    const i = list.indexOf(document.activeElement as HTMLElement)
    if (event.key === 'ArrowDown') list[(i + 1) % list.length]?.focus()
    else if (event.key === 'ArrowUp') list[(i - 1 + list.length) % list.length]?.focus()
    else if (event.key === 'Home') list[0]?.focus()
    else if (event.key === 'End') list.at(-1)?.focus()
    else return false
    return true
  }

  function onkeydown(event: KeyboardEvent) {
    const inSub = (event.target as Element).closest('.sub-menu')
    if (inSub) {
      if (move(subItems(), event)) {
        // handled
      } else if (event.key === 'ArrowLeft' || event.key === 'Escape') {
        subOpen = false
        root?.querySelector<HTMLElement>('.sub > [role="menuitem"]')?.focus()
      } else if (event.key === 'Tab') close()
      else return
    } else if (move(mainItems(), event)) {
      // handled
    } else if (event.key === 'ArrowRight' && (event.target as Element).closest('.sub')) {
      showSources(true)
    } else if (event.key === 'Escape') close(true)
    else if (event.key === 'Tab') close()
    else return
    event.preventDefault()
    event.stopPropagation()
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="add-source" bind:this={root} {onkeydown}>
  <button
    type="button"
    class="chrome-button add-tab"
    class:pressed={open}
    aria-label={`Add a source to ${topic?.name ?? 'this topic'}`}
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={toggle}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
  </button>
  {#if open}
    <div class="popup-menu main-menu" role="menu" aria-label="Add a source">
      <div class="sub" role="none" onpointerenter={() => showSources(false)} onpointerleave={leaveSources}>
        <button
          type="button"
          role="menuitem"
          aria-haspopup="menu"
          aria-expanded={subOpen}
          class:shown={subOpen}
          onclick={(e) => showSources(e.detail === 0)}
        >
          <span class="label">Open source</span>
          <svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
        </button>
        {#if subOpen}
          <div class="popup-menu sub-menu" role="menu" aria-label={`Sources in ${topic?.name ?? 'this topic'}`}>
            {#each sources as id (id)}
              <button type="button" role="menuitem" onclick={() => pick(id)}>
                <span class="label">{workspace.docName(id)}</span>
              </button>
            {:else}
              <div class="empty">No sources yet</div>
            {/each}
          </div>
        {/if}
      </div>
      <button type="button" role="menuitem" onclick={upload}>
        <span class="label">Upload source…</span>
      </button>
    </div>
  {/if}
</div>

<style>
  .add-source {
    position: relative;
    flex-shrink: 0;
  }
  .add-tab {
    color: var(--muted);
  }
  .add-tab:hover,
  .add-tab.pressed {
    color: inherit;
  }

  .main-menu {
    position: absolute;
    top: calc(100% + 0.25rem);
    left: 0;
    z-index: 5;
    min-width: 11rem;
  }
  .sub {
    position: relative;
    display: flex;
    flex-direction: column;
  }
  /* Rows like the shared menu's, for the ones inside the "Open source" wrapper too. */
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

  /* Beside the "Open source" row, its first row level with it. */
  .sub-menu {
    position: absolute;
    top: -0.25rem;
    left: calc(100% + 0.25rem);
    width: max-content;
    min-width: 10rem;
    max-width: 18rem;
    max-height: 60vh;
    overflow-y: auto;
  }
  .empty {
    padding: 0.3rem 0.5rem;
    color: var(--muted);
  }
</style>
