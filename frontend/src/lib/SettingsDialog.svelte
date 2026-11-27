<script lang="ts" module>
  // The category the dialog was last left on, for the rest of the visit.
  let lastCategory: 'appearance' | 'chat' | 'tutoring' | 'archive' = 'appearance'
</script>

<script lang="ts">
  import { saveZoomFollowsChat } from './chatZoom'
  import { quizMask, quizTyped, setHideQuizChoices, setTypedQuizShare } from './quizMask.svelte'
  import { applyTheme, savedTheme, THEMES, type Theme } from './theme'
  import { confirmDeleteTopic } from './deleteTopic'
  import type { Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    /** Whether the PDF's zoom follows the chat opening and closing. */
    zoomFollowsChat: boolean
    onclose: () => void
  }

  let { workspace, zoomFollowsChat = $bindable(), onclose }: Props = $props()

  let theme = $state<Theme>(savedTheme())

  function pick(next: Theme) {
    theme = next
    applyTheme(next)
  }

  function pickZoom(follow: boolean) {
    zoomFollowsChat = follow
    saveZoomFollowsChat(follow)
  }

  const CATEGORIES = [
    { id: 'appearance', name: 'Appearance' },
    { id: 'chat', name: 'Chat bot' },
    { id: 'tutoring', name: 'Tutoring' },
    { id: 'archive', name: 'Archive' },
  ] as const
  type Category = (typeof CATEGORIES)[number]['id']
  let category = $state<Category>(lastCategory)

  function show(next: Category) {
    category = next
    lastCategory = next
  }

  const archived = $derived(workspace.topics.filter((t) => t.archived))

  /** Open an archived topic: it shows, still archived, and Settings closes. */
  function openArchived(id: string) {
    workspace.selectTopic(id)
    onclose()
  }

  let card = $state<HTMLElement>()
  // Back to wherever focus was (the Settings button) once it closes.
  const returnTo = document.activeElement as HTMLElement | null
  $effect(() => {
    // Focus the picked category, not a field, so nothing starts in typing mode.
    card?.querySelector<HTMLElement>('nav [aria-current="page"]')?.focus()
    return () => returnTo?.focus?.()
  })

  function onkeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      onclose()
    }
  }
</script>

<!-- Pressing the dimmed backdrop closes it, like Escape; the × does the same by keyboard. -->
<div
  class="backdrop settings-dialog"
  role="presentation"
  onpointerdown={(e) => e.target === e.currentTarget && onclose()}
  {onkeydown}
>
  <div bind:this={card} class="card" role="dialog" aria-modal="true" aria-labelledby="settings-title">
    <header>
      <h2 id="settings-title">Settings</h2>
      <button type="button" class="chrome-button close" aria-label="Close settings" onclick={onclose}>×</button>
    </header>

    <div class="body">
      <nav aria-label="Settings categories">
        {#each CATEGORIES as c (c.id)}
          <button type="button" class:bottom={c.id === 'archive'} aria-current={category === c.id ? 'page' : undefined} onclick={() => show(c.id)}>
            {c.name}{#if c.id === 'archive' && archived.length}<span class="count">{archived.length}</span>{/if}
          </button>
        {/each}
      </nav>

      <section class="pane" aria-label={CATEGORIES.find((c) => c.id === category)?.name}>
        {#if category === 'appearance'}
          <div class="field">
            <span class="label" id="theme-label">Theme</span>
            <div class="segments" role="radiogroup" aria-labelledby="theme-label">
              {#each THEMES as t (t.id)}
                <button type="button" role="radio" aria-checked={theme === t.id} onclick={() => pick(t.id)}>{t.name}</button>
              {/each}
            </div>
          </div>

          <div class="field">
            <span class="label" id="names-label">Source names</span>
            <span class="hint">
              {workspace.indexTitles
                ? 'Sources go by the title found when they were indexed, until you rename them.'
                : 'Sources go by their file name, until you rename them.'}
            </span>
            <div class="segments" role="radiogroup" aria-labelledby="names-label">
              <button type="button" role="radio" aria-checked={workspace.indexTitles} onclick={() => workspace.setIndexTitles(true)}>Title from the index</button>
              <button type="button" role="radio" aria-checked={!workspace.indexTitles} onclick={() => workspace.setIndexTitles(false)}>File name</button>
            </div>
          </div>

          <div class="field">
            <span class="label" id="zoom-label">PDF size with the chat</span>
            <span class="hint">
              {zoomFollowsChat
                ? 'The PDF opens a little bigger and shrinks to fit beside the chat when it opens, then grows back.'
                : 'The PDF keeps one size that already leaves room for the chat beside it.'}
            </span>
            <div class="segments" role="radiogroup" aria-labelledby="zoom-label">
              <button type="button" role="radio" aria-checked={zoomFollowsChat} onclick={() => pickZoom(true)}>Fit to chat</button>
              <button type="button" role="radio" aria-checked={!zoomFollowsChat} onclick={() => pickZoom(false)}>Fixed size</button>
            </div>
          </div>
        {:else if category === 'chat'}
          <label class="field">
            <span class="label">About you</span>
            <span class="hint">Helps the model pitch answers at your level, like your education, your field and courses you have already done.</span>
            <textarea rows="4" bind:value={workspace.about} placeholder="Nothing yet"></textarea>
          </label>
          <label class="field">
            <span class="label">Instructions for every answer</span>
            <span class="hint">Added to what the model is told in every topic, like “Answer in Swedish” or “I'm preparing for an exam”.</span>
            <textarea rows="6" bind:value={workspace.instructions} placeholder="Nothing yet"></textarea>
          </label>
        {:else if category === 'tutoring'}
          <div class="field">
            <span class="label" id="quiz-mask-label">Quiz choices</span>
            <span class="hint">
              {quizMask.hideChoices
                ? 'Each question’s choices stay covered until you click them, so you think of an answer first.'
                : 'Each question shows its choices right away.'}
            </span>
            <div class="segments" role="radiogroup" aria-labelledby="quiz-mask-label">
              <button type="button" role="radio" aria-checked={quizMask.hideChoices} onclick={() => setHideQuizChoices(true)}>Hidden until clicked</button>
              <button type="button" role="radio" aria-checked={!quizMask.hideChoices} onclick={() => setHideQuizChoices(false)}>Shown</button>
            </div>
          </div>

          <div class="field">
            <label class="label" for="typed-share">Typed answers in quizzes</label>
            <div class="slider">
              <input
                id="typed-share"
                type="range"
                min="0"
                max="100"
                step="10"
                value={Math.round(quizTyped.share * 100)}
                aria-valuetext={`At most ${Math.round(quizTyped.share * 100)}%`}
                oninput={(e) => setTypedQuizShare(Number(e.currentTarget.value) / 100)}
              />
              <span class="value">{quizTyped.share ? `Up to ${Math.round(quizTyped.share * 100)}%` : 'None'}</span>
            </div>
            <span class="hint">Research shows that typing short answers yourself helps you remember more than picking from choices.</span>
          </div>
        {:else}
          <!-- The archived topics: open one, bring it back, or delete it. -->
          {#if archived.length === 0}
            <p class="hint">No archived topics. Archive one from its ⋮ menu in the sidebar to tidy it away.</p>
          {:else}
            <ul class="archived" aria-label="Archived topics">
              {#each archived as topic (topic.id)}
                <li>
                  <button type="button" class="archived-name" onclick={() => openArchived(topic.id)}>{topic.name}</button>
                  <button type="button" class="chrome-button" aria-label={`Unarchive ${topic.name}`} title="Unarchive" onclick={() => workspace.unarchiveTopic(topic.id)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h18v4H3zM5 8v12h14V8M12 17v-6M9 14l3-3 3 3" /></svg>
                  </button>
                  <button type="button" class="chrome-button danger" aria-label={`Delete ${topic.name}`} title="Delete" onclick={() => confirmDeleteTopic(workspace, topic.id, topic.name)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5" /></svg>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      </section>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: center;
    padding: 1rem;
    background: rgb(0 0 0 / 0.35);
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: min(44rem, 100%);
    max-height: 100%;
    box-sizing: border-box;
    overflow-y: auto;
    padding: 1rem 1.25rem 1.5rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    box-shadow: 0 16px 48px rgb(0 0 0 / 0.3);
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .close {
    font-size: 1.25rem;
  }
  .body {
    display: flex;
    gap: 1.25rem;
    min-height: 22rem;
  }
  nav {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    flex: none;
    width: 9rem;
  }
  nav button {
    padding: 0.375rem 0.625rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: var(--muted);
    font: inherit;
    font-size: 0.9rem;
    text-align: left;
    cursor: pointer;
  }
  nav button:hover {
    background: var(--hover);
    color: inherit;
  }
  nav button[aria-current='page'] {
    background: var(--hover);
    color: inherit;
    font-weight: 600;
  }
  /* Archive sits apart at the bottom of the list, as it holds topics rather than settings. */
  nav button.bottom {
    margin-top: auto;
    display: flex;
    align-items: center;
  }
  .count {
    margin-left: auto;
    font-size: 0.75rem;
    font-weight: normal;
    color: var(--muted);
  }
  .archived {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .archived li {
    display: flex;
    align-items: center;
    gap: 0.125rem;
    border-radius: var(--radius);
  }
  .archived li:hover {
    background: var(--hover);
  }
  .archived-name {
    flex: 1;
    min-width: 0;
    padding: 0.375rem 0.625rem;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    font-size: 0.9rem;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }
  .archived svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .archived .chrome-button {
    color: var(--muted);
  }
  .archived .chrome-button:hover {
    color: inherit;
  }
  .archived .danger:hover {
    color: var(--danger);
  }
  nav button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .pane {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    flex: 1;
    min-width: 0;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .label {
    font-size: 0.9rem;
    font-weight: 600;
  }
  .hint {
    font-size: 0.8rem;
    color: var(--muted);
  }
  textarea {
    margin-top: 0.25rem;
    padding: 0.5rem 0.625rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    font-size: 0.9rem;
    resize: vertical;
  }
  textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--ring);
  }
  /* Three buttons joined into one control, the picked one raised. */
  .segments {
    display: flex;
    gap: 0.125rem;
    width: fit-content;
    margin-top: 0.25rem;
    padding: 0.1875rem;
    border-radius: 0.5rem;
    background: var(--hover);
  }
  .segments button {
    padding: 0.25rem 0.875rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: var(--muted);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .segments button:hover {
    color: inherit;
  }
  .segments button[aria-checked='true'] {
    background: var(--surface);
    color: inherit;
    font-weight: 600;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.15);
  }
  .segments button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .slider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .slider input {
    flex: 1;
    accent-color: var(--accent);
  }
  .slider .value {
    min-width: 5.5rem;
    font-size: 0.85rem;
    font-variant-numeric: tabular-nums;
  }
</style>
