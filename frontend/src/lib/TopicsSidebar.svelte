<script lang="ts">
  import { tick } from 'svelte'
  import { slide } from 'svelte/transition'
  import { FLASHCARD_ICON } from './flashcards'

  // A box with a lid.
  const ARCHIVE_ICON = 'M3 4h18v4H3zM5 8v12h14V8M10 12h4'
  import { marquee } from './marquee'
  import { confirmDeleteTopic } from './deleteTopic'
  import DiscussionsDialog from './DiscussionsDialog.svelte'
  import SourceCard from './SourceCard.svelte'
  import { CardHover } from './cardHover.svelte'
  import { chatOf, chatTitle, discussions, type Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    /** Whether the sidebar is showing, either peeking (hovered) or pinned. Hidden, it is gone entirely. */
    open?: boolean
    /** Pinned by its button: opaque and without a shadow, and it stays until unpinned. */
    pinned?: boolean
    /** Called as the pointer comes into and leaves the sidebar, so a peek can end when it leaves. */
    onhover?: (inside: boolean) => void
    /** Called when a discussion is picked, to show it in the chat. */
    onopenchat?: () => void
    /** Whether the chat is showing. Only then is its discussion marked as the open one. */
    chatOpen?: boolean
    /** Called by the Settings button at the bottom. */
    onopensettings?: () => void
    /** Called by the Upload source row: ask for PDFs to add to the open topic. */
    onupload?: () => void
    /** Called by Scope and conventions in a topic's menu. */
    onopenprofile?: (topicId: string) => void
    /** Called by Flashcards in a topic's menu: open its deck. */
    onopenflashcards?: (topicId: string) => void
  }

  let {
    workspace,
    open = false,
    pinned = false,
    onhover,
    onopenchat,
    chatOpen = false,
    onopensettings,
    onupload,
    onopenprofile,
    onopenflashcards,
  }: Props = $props()

  // Archived topics are listed in Settings, under Archive.
  const shown = $derived(workspace.topics.filter((t) => !t.archived))
  const archived = $derived(workspace.topics.filter((t) => t.archived))
  // A topic's discussions slide open and shut, quickly, unless motion is reduced.
  const listSlide = () => ({
    duration: typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 150,
  })

  const expanded = $derived(open)

  // The topic or discussion whose actions menu (the three dots) is open.
  let menuId = $state<string>()

  // The card beside the sidebar for the discussion or source under the pointer: its full title,
  // and when it was last chatted in or what kind of document it is.
  let sidebar: HTMLElement | undefined = $state()
  const card = new CardHover()
  function showCard(id: string, row: HTMLElement) {
    card.show(id, () => {
      const box = row.getBoundingClientRect()
      return { x: (sidebar?.getBoundingClientRect().right ?? box.right) + 8, y: box.top + box.height / 2 }
    })
  }
  const closeCard = () => card.close()
  $effect(() => {
    if (!expanded || menuId) card.close()
  })
  $effect(() => () => card.clear())

  function closeMenu(event: Event) {
    const target = event.target as Element | null
    if (menuId && !target?.closest?.('.topic-menu, .dots')) menuId = undefined
  }

  let renamingId = $state<string>()
  // What is being renamed: a topic, or one of the open topic's discussions or sources.
  let renamingKind = $state<'topic' | 'chat' | 'doc'>('topic')
  let renamingTopic: string | undefined
  let draft = $state('')
  let renameInput = $state<HTMLInputElement>()

  async function startRename(id: string, name: string, kind: 'topic' | 'chat' | 'doc' = 'topic', topicId?: string) {
    renamingId = id
    renamingKind = kind
    renamingTopic = topicId
    draft = name
    await tick()
    renameInput?.select()
  }

  // The topic whose first name is being typed. Naming it is the last step of creating it.
  let creatingId: string | undefined
  // What was open before it, to go back to if the new topic is cancelled.
  let topicBeforeCreating: string | undefined

  function finishRename(save: boolean) {
    const id = renamingId
    // Renaming ends first, so the box going away can't finish it a second time.
    renamingId = undefined
    const creating = id !== undefined && id === creatingId
    creatingId = undefined
    if (!id) return
    if (renamingKind === 'chat') {
      if (save && renamingTopic) workspace.renameChat(renamingTopic, id, draft)
      return
    }
    if (renamingKind === 'doc') {
      if (save) workspace.renameDoc(id, draft)
      return
    }
    if (creating && !save) {
      // Cancelling a new topic takes the placeholder away again and leaves the sidebar as it was.
      workspace.deleteTopic(id)
      if (topicBeforeCreating) workspace.selectTopic(topicBeforeCreating)
      return
    }
    if (save) workspace.renameTopic(id, draft)
    // A new topic is ready once it is named: get out of the way of the PDF.
  }

  /** Take a PDF out of its topic. Unlike closing its tab, the model no longer sees it. */
  function removeSource(id: string, name: string) {
    const others = workspace.otherTopicsWith(id).map((t) => `“${t.name}”`)
    const stays = others.length ? ` It stays in ${others.join(', ')}.` : ''
    if (confirm(`Delete “${name}” from this topic? The chat will no longer draw on it.${stays}`)) workspace.removeDoc(id)
  }

  const remove = (id: string, name: string) => confirmDeleteTopic(workspace, id, name)

  function openChat(topicId: string, chatId: string) {
    workspace.selectTopic(topicId)
    workspace.selectChat(topicId, chatId)
    onopenchat?.()
  }

  // Past this many, the list ends in "View all", which opens every discussion in a dialog.
  const MAX_LISTED = 9
  let allDiscussionsFrom = $state<string>()

  function newDiscussion(topicId: string) {
    workspace.newChat(topicId)
    onopenchat?.()
  }

  function removeChat(topicId: string, chatId: string, title: string) {
    if (confirm(`Delete the discussion “${title}”?`)) workspace.deleteChat(topicId, chatId)
  }

  async function newTopic() {
    topicBeforeCreating = workspace.activeTopicId
    const topic = workspace.createTopic()
    creatingId = topic.id
    await startRename(topic.id, topic.name)
  }
</script>

<svelte:window onpointerdown={closeMenu} onkeydown={(e) => e.key === 'Escape' && (menuId = undefined)} />

<aside
  bind:this={sidebar}
  class="topics-sidebar"
  class:closed={!open}
  class:pinned
  id="topics-sidebar"
  aria-label="Topics"
  inert={!open}
  onscrollcapture={closeCard}
  onpointerenter={() => onhover?.(true)}
  onpointerleave={() => onhover?.(false)}
>
  <!-- The sidebar button itself stays in the corner above this, outside the sidebar, so it never moves. -->
  <div class="top">
    <h1>Leqtern</h1>
  </div>

  <button type="button" class="new new-topic" aria-label="New topic" onclick={newTopic}>
    <span class="plus" aria-hidden="true">＋</span>
    <span>New topic</span>
  </button>

  {#if expanded}
    <div id="topics-list" class="list">

      {#if shown.length === 0 && archived.length === 0}
        <p class="hint">Topics group the PDFs you study together, like lecture notes, old exams and the course book.</p>
      {/if}

      <ul aria-label="Topics">
        {#each shown as topic (topic.id)}
          <li class:active={topic.id === workspace.activeTopicId}>
            {#if renamingId === topic.id}
              <form
                onsubmit={(e) => {
                  e.preventDefault()
                  finishRename(true)
                }}
              >
                <input
                  bind:this={renameInput}
                  bind:value={draft}
                  aria-label="Topic name"
                  onblur={() => finishRename(true)}
                  onkeydown={(e) => e.key === 'Escape' && finishRename(false)}
                />
              </form>
            {:else}
              <button
                type="button"
                class="topic"
                aria-current={topic.id === workspace.activeTopicId ? 'true' : undefined}
                onclick={() => workspace.selectTopic(topic.id)}
              >
                <span class="name" use:marquee><span>{topic.name}</span></span>
                <span class="count">{topic.docIds.length}</span>
              </button>
              <button
                type="button"
                class="dots"
                aria-label={`Actions for ${topic.name}`}
                aria-haspopup="menu"
                aria-expanded={menuId === topic.id}
                onclick={() => (menuId = menuId === topic.id ? undefined : topic.id)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="5" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="12" cy="19" r="1.4" />
                </svg>
              </button>
              {#if menuId === topic.id}
                <div class="topic-menu" role="menu" aria-label={`Actions for ${topic.name}`}>
                  <button
                    type="button"
                    role="menuitem"
                    onclick={() => {
                      menuId = undefined
                      startRename(topic.id, topic.name)
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
                    Rename
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onclick={() => {
                      menuId = undefined
                      onopenprofile?.(topic.id)
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7" /></svg>
                    Scope and conventions
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onclick={() => {
                      menuId = undefined
                      onopenflashcards?.(topic.id)
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={FLASHCARD_ICON} /></svg>
                    Flashcards
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onclick={() => {
                      menuId = undefined
                      workspace.archiveTopic(topic.id)
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={ARCHIVE_ICON} /></svg>
                    Archive
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    class="danger"
                    onclick={() => {
                      menuId = undefined
                      remove(topic.id, topic.name)
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5" /></svg>
                    Delete
                  </button>
                </div>
              {/if}
            {/if}
          </li>
          {#if topic.id === workspace.activeTopicId && !(renamingId === topic.id && renamingKind === 'topic')}
            {@const listed = discussions(topic)}
            {@const visible = listed.length > MAX_LISTED ? listed.slice(0, MAX_LISTED) : listed}
            {@const discussionsOpen = topic.discussionsOpen !== false}
            {@const sourcesOpen = !!topic.sourcesOpen}
            <!-- The open topic's discussions, on a soft line that forks out to each title. -->
            <li class="discussions" transition:slide={listSlide()}>
              <h3>
                <button
                  type="button"
                  class="list-toggle"
                  id={`discussions-${topic.id}`}
                  aria-expanded={discussionsOpen}
                  onclick={() => (topic.discussionsOpen = !discussionsOpen)}
                >
                  Discussions
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
                </button>
              </h3>
              {#if discussionsOpen}
              <ul aria-labelledby={`discussions-${topic.id}`} transition:slide={listSlide()}>
                <!-- Opens an empty discussion in the chat. Never marked: it is an action, not a discussion. -->
                <li class="discussion">
                  <div class="row">
                    <button type="button" class="topic new-discussion" onclick={() => newDiscussion(topic.id)}>
                      <span aria-hidden="true">＋</span>
                      <span class="name">New discussion</span>
                    </button>
                  </div>
                </li>
                {#each visible as chat (chat.id)}
                  {@const title = chatTitle(chat)}
                  {@const current = chatOpen && chat.id === chatOf(topic).id}
                  <li class="discussion">
                    {#if renamingId === chat.id}
                      <form
                        class="rename"
                        onsubmit={(e) => {
                          e.preventDefault()
                          finishRename(true)
                        }}
                      >
                        <input
                          bind:this={renameInput}
                          bind:value={draft}
                          aria-label="Discussion name"
                          onblur={() => finishRename(true)}
                          onkeydown={(e) => e.key === 'Escape' && finishRename(false)}
                        />
                      </form>
                    {:else}
                    <div
                      class="row"
                      class:active={current}
                      role="presentation"
                      onpointerenter={(e) => showCard(chat.id, e.currentTarget)}
                      onpointerleave={() => card.leave()}
                    >
                      <button
                        type="button"
                        class="topic"
                        aria-current={current ? 'true' : undefined}
                        onclick={() => openChat(topic.id, chat.id)}
                      >
                        <span class="name" use:marquee><span>{title}</span></span>
                      </button>
                      <button
                        type="button"
                        class="dots"
                        aria-label={`Actions for ${title}`}
                        aria-haspopup="menu"
                        aria-expanded={menuId === chat.id}
                        onclick={() => (menuId = menuId === chat.id ? undefined : chat.id)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <circle cx="12" cy="5" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="12" cy="19" r="1.4" />
                        </svg>
                      </button>
                      {#if menuId === chat.id}
                        <div class="topic-menu" role="menu" aria-label={`Actions for ${title}`}>
                          <button
                            type="button"
                            role="menuitem"
                            onclick={() => {
                              menuId = undefined
                              startRename(chat.id, title, 'chat', topic.id)
                            }}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
                            Rename
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            class="danger"
                            onclick={() => {
                              menuId = undefined
                              removeChat(topic.id, chat.id, title)
                            }}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5" /></svg>
                            Delete
                          </button>
                        </div>
                      {/if}
                    </div>
                    {/if}
                  </li>
                {/each}
                {#if visible.length < listed.length}
                  <li class="discussion">
                    <div class="row">
                      <button type="button" class="topic view-all" onclick={() => (allDiscussionsFrom = topic.id)}>
                        <span class="name">View all</span>
                      </button>
                    </div>
                  </li>
                {/if}
              </ul>
              {/if}
            </li>
            <!-- The topic's PDFs. Closing a tab only takes it off the tab row; it stays here to reopen. -->
            <li class="discussions sources" transition:slide={listSlide()}>
              <h3>
                <button
                  type="button"
                  class="list-toggle"
                  id={`sources-${topic.id}`}
                  aria-expanded={sourcesOpen}
                  onclick={() => (topic.sourcesOpen = !sourcesOpen)}
                >
                  Sources
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
                </button>
              </h3>
              {#if sourcesOpen}
              <ul aria-labelledby={`sources-${topic.id}`} transition:slide={listSlide()}>
                <!-- Asks for PDFs to add to the topic. An action, never marked. -->
                <li class="discussion">
                  <div class="row">
                    <button type="button" class="topic new-discussion" onclick={() => onupload?.()}>
                      <span aria-hidden="true">＋</span>
                      <span class="name">Upload source</span>
                    </button>
                  </div>
                </li>
                {#each topic.docIds as id (id)}
                  {@const name = workspace.docName(id)}
                  <li class="discussion">
                    {#if renamingId === id}
                      <form
                        class="rename"
                        onsubmit={(e) => {
                          e.preventDefault()
                          finishRename(true)
                        }}
                      >
                        <input
                          bind:this={renameInput}
                          bind:value={draft}
                          aria-label="Source name"
                          onblur={() => finishRename(true)}
                          onkeydown={(e) => e.key === 'Escape' && finishRename(false)}
                        />
                      </form>
                    {:else}
                    <div
                      class="row"
                      role="presentation"
                      onpointerenter={(e) => showCard(id, e.currentTarget)}
                      onpointerleave={() => card.leave()}
                    >
                      <button type="button" class="topic" onclick={() => workspace.openDoc(id)}>
                        <span class="name" use:marquee><span>{name}</span></span>
                      </button>
                      <button
                        type="button"
                        class="dots"
                        aria-label={`Actions for ${name}`}
                        aria-haspopup="menu"
                        aria-expanded={menuId === id}
                        onclick={() => (menuId = menuId === id ? undefined : id)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <circle cx="12" cy="5" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="12" cy="19" r="1.4" />
                        </svg>
                      </button>
                      {#if menuId === id}
                        <div class="topic-menu" role="menu" aria-label={`Actions for ${name}`}>
                          <button
                            type="button"
                            role="menuitem"
                            onclick={() => {
                              menuId = undefined
                              startRename(id, name, 'doc')
                            }}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
                            Rename
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            class="danger"
                            onclick={() => {
                              menuId = undefined
                              removeSource(id, name)
                            }}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5" /></svg>
                            Delete
                          </button>
                        </div>
                      {/if}
                    </div>
                    {/if}
                  </li>
                {/each}
              </ul>
              {/if}
            </li>
          {/if}
        {/each}
      </ul>
    </div>
  {/if}

  <!-- At the bottom, in the same fixed cell as the plus, so they stay put in the collapsed strip too. -->
  <button type="button" class="new settings" aria-label="Settings" onclick={() => onopensettings?.()}>
    <span class="plus" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="3" />
        <path
          d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"
        />
      </svg>
    </span>
    <span>Settings</span>
  </button>
</aside>

{#if allDiscussionsFrom}
  <DiscussionsDialog
    {workspace}
    topicId={allDiscussionsFrom}
    onpick={(topicId, chatId) => {
      allDiscussionsFrom = undefined
      openChat(topicId, chatId)
    }}
    onclose={() => (allDiscussionsFrom = undefined)}
  />
{/if}

<SourceCard {workspace} hover={card} placement="right" onhover={(inside) => onhover?.(inside)} />

<style>
  .topics-sidebar {
    /* The plus and the icons below it sit in a cell this wide, under the sidebar button in the corner. */
    --icon-cell: 2.25rem;
    --row-height: 2.125rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    /* Peeking, it floats over the page. Pinned, the page makes room for it (see App). */
    position: absolute;
    inset: 0 auto 0 0;
    z-index: 30;
    width: 18rem;
    box-sizing: border-box;
    padding: 0 0.375rem 0.5rem;
    border-right: 1px solid var(--border);
    /* Peeking: slightly see-through and blurred, so it reads as lying on top of the PDF. */
    background: color-mix(in srgb, var(--sidebar-bg) 82%, transparent);
    backdrop-filter: blur(14px);
    box-shadow: var(--sidebar-shadow);
    overflow: hidden;
    white-space: nowrap;
    /* Slides in from the left edge as it fades in. */
    transition:
      transform 0.2s ease,
      opacity 0.2s ease,
      visibility 0.2s,
      background-color 0.2s ease,
      box-shadow 0.2s ease;
  }
  /* Pinned: solid, flat, part of the layout like the chat. (Not named .sidebar: PDF.js's stylesheet styles that globally.) */
  .topics-sidebar.pinned {
    background: var(--sidebar-bg);
    backdrop-filter: none;
    box-shadow: none;
  }
  /* Starts nearly in place, so it only slides the last bit as it fades in. */
  .topics-sidebar.closed {
    transform: translateX(-10%);
    opacity: 0;
    visibility: hidden;
    box-shadow: none;
  }
  @media (prefers-reduced-motion: reduce) {
    .topics-sidebar {
      transition: none;
    }
  }

  /* The list keeps its full width while the sidebar opens, so it is revealed rather than reflowed. */
  .list {
    width: calc(18rem - 0.75rem);
    /* Takes what room is left between the buttons, and scrolls when the topics need more. */
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: thin;
  }

  /* As tall as the tab row, with room on the left for the sidebar button that sits over it. */
  .top {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    height: var(--bar-height);
    margin-inline: -0.375rem;
    padding-left: calc(0.375rem + var(--icon-cell));
    border-bottom: 1px solid var(--border);
  }

  h1 {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    margin: 0;
    padding-left: 0.25rem;
    font-size: 1rem;
  }

  .new {
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    border-radius: var(--radius);
  }
  .new {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    width: 100%;
    /* The same height and text size as a topic row (see li > .topic). */
    height: var(--row-height);
    padding: 0;
    overflow: hidden;
    font-size: 0.85rem;
    text-align: left;
  }
  /* A little below the top bar. */
  .new-topic {
    margin-top: 0.375rem;
    /* Set a little apart from the topics below it. */
    margin-bottom: 0.625rem;
  }
  .plus {
    flex-shrink: 0;
    width: var(--icon-cell);
    text-align: center;
  }
  /* Pushed to the bottom; with a long list it comes after it. */
  .settings {
    flex-shrink: 0;
    margin-top: auto;
  }
  .settings .plus {
    display: grid;
    place-items: center;
  }
  .settings svg {
    width: 1.05rem;
    height: 1.05rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .new:hover {
    background: var(--hover);
  }

  h2 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    margin: 0.25rem 0.5rem 0.25rem;
  }

  .hint {
    white-space: normal;
    margin: 0 0.5rem;
    font-size: 0.85rem;
    color: var(--muted);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  /* Rounded rows with a 2px gap between them, so neighbouring highlights never touch. */
  li {
    display: flex;
    align-items: center;
    margin-block: 1px;
    border-radius: var(--radius);
  }
  li:hover {
    background: var(--row-hover);
  }
  li.active {
    background: var(--selected);
  }

  li form {
    flex: 1;
    padding: 0.25rem;
  }
  /* A discussion or source being renamed: the box sits where its row was. */
  li form.rename {
    padding: 1px 0;
  }
  li input {
    width: 100%;
    box-sizing: border-box;
  }

  .topic {
    flex: 1;
    min-width: 0;
    display: flex;
    gap: 0.5rem;
    padding: 0.375rem 0.5rem;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    text-align: left;
    cursor: pointer;
  }

  /* A topic's row is as tall as New topic and Settings. */
  li > .topic {
    align-items: center;
    min-height: var(--row-height);
    padding-block: 0;
    /* The name starts level with the + of New topic and the arrows of Discussions and Sources. */
    padding-left: 0.7rem;
  }

  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* A long name scrolls on hover (see marquee.ts): its text moves as a block, without the ellipsis. */
  .name:global(.scrolling) {
    text-overflow: clip;
  }
  .name:global(.scrolling) > span {
    display: inline-block;
  }

  .count {
    color: var(--muted);
    font-weight: normal;
    font-size: 0.75rem;
  }

  .dots {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 1.5rem;
    height: 1.5rem;
    margin-right: 0.25rem;
    padding: 0;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: var(--muted);
    cursor: pointer;
    visibility: hidden;
  }
  .dots svg {
    width: 1rem;
    height: 1rem;
    fill: currentColor;
  }
  .dots:hover,
  .dots[aria-expanded='true'] {
    background: color-mix(in srgb, var(--muted) 18%, transparent);
    color: inherit;
  }
  li:hover > .dots,
  li.active > .dots,
  .dots:focus-visible,
  .dots[aria-expanded='true'] {
    visibility: visible;
  }
  .dots:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  /* Opens under the dots, like the chat's model menu. */
  li {
    position: relative;
  }
  .topic-menu {
    position: absolute;
    top: calc(100% + 0.125rem);
    right: 0.25rem;
    z-index: 5;
    display: flex;
    flex-direction: column;
    min-width: 8rem;
    padding: 0.25rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 6px 20px rgb(0 0 0 / 0.18);
    font-size: 0.85rem;
    font-weight: normal;
  }
  .topic-menu button {
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
    cursor: pointer;
  }
  .topic-menu button:hover,
  .topic-menu button:focus-visible {
    background: var(--hover);
    outline: none;
  }
  /* The open topic's discussions: indented, under a small header, on a soft line down the left. */
  li.discussions {
    display: block;
    margin-block: 0;
    padding: 0 0 0.375rem 0.875rem;
    font-weight: normal;
  }
  /* Sources follows Discussions closely: the two read as one block under the topic. */
  li.discussions:has(+ li.sources) {
    padding-bottom: 0;
  }
  li.sources h3 {
    margin-top: 0.125rem;
  }
  li.discussions:hover {
    background: none;
  }
  /* Plain words, starting where the topic's name does (the list is indented 0.875rem, the name 0.5rem). */
  h3 {
    margin: 0.5rem 0 0.375rem -0.375rem;
    font-size: 0.8rem;
    font-weight: normal;
    color: var(--muted);
  }
  /* The label first, level with the topic's name, then its arrow. */
  .list-toggle {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0 0 0 0.2rem;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    text-transform: inherit;
    letter-spacing: inherit;
    cursor: pointer;
  }
  .list-toggle svg {
    width: 0.8rem;
    height: 0.8rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: transform 0.18s ease;
  }
  .list-toggle[aria-expanded='true'] svg {
    transform: rotate(90deg);
  }
  @media (prefers-reduced-motion: reduce) {
    .list-toggle svg {
      transition: none;
    }
  }
  li.discussions ul {
    --branch: color-mix(in srgb, var(--muted) 35%, transparent);
    /* Padding, not margin: the line sits in it, so the slide's clipping doesn't hide it until the end. */
    padding-left: 0.5rem;
  }
  li.discussion {
    margin-block: 0;
    padding-left: 0.75rem;
  }
  li.discussion:hover {
    background: none;
  }
  .row {
    position: relative;
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    /* The 2px gap lives on the row, so the branch line beside the rows stays unbroken. */
    margin-block: 1px;
    border-radius: var(--radius);
  }
  .row:hover {
    background: var(--row-hover);
  }
  .row.active {
    background: var(--selected);
    font-weight: 600;
  }
  .row .topic {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
  }
  /* An action rather than a discussion, so a shade lighter than the titles above it. */
  .view-all {
    color: var(--muted);
  }
  .new-discussion {
    gap: 0.375rem;
    color: var(--muted);
  }
  .row:hover .dots,
  .row.active .dots {
    visibility: visible;
  }
  /* The line down the left, and a short branch out to each title; the last one turns the corner.
     The line sits 0.475rem left of these rows, under the start of the section's label (0.875rem list
     indent - 0.375rem header pull + 0.4rem, measured from the ul's 0.5rem margin). A branch starts
     just right of the line, so the two never overlap. */
  li.discussion {
    --trunk: calc(-0.475rem - 0.5px);
  }
  li.discussion::before,
  li.discussion::after {
    content: '';
    position: absolute;
    pointer-events: none;
  }
  li.discussion::before {
    left: var(--trunk);
    top: 0;
    bottom: 0;
    border-left: 1px solid var(--branch);
  }
  li.discussion::after {
    left: calc(var(--trunk) + 1px);
    right: calc(100% - 0.625rem);
    top: 50%;
    border-top: 1px solid var(--branch);
  }
  li.discussion:last-child::before {
    bottom: 50%;
    right: calc(100% - 0.625rem);
    border-bottom: 1px solid var(--branch);
    border-bottom-left-radius: 0.375rem;
  }
  li.discussion:last-child::after {
    display: none;
  }

  .topic-menu .danger {
    color: var(--danger);
  }
  .topic-menu svg {
    width: 0.95rem;
    height: 0.95rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>
