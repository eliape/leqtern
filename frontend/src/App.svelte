<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { BackendError, fetchIndexSections, fetchSavedWorkspace, saveWorkspace } from './lib/api'
  import { chatReserve } from './lib/chatWidth'
  import ChatPanel from './lib/ChatPanel.svelte'
  import ContextMenu, { type MenuItem } from './lib/ContextMenu.svelte'
  import DocPane from './lib/DocPane.svelte'
  import FlashcardDialog from './lib/FlashcardDialog.svelte'
  import FlashcardManager from './lib/FlashcardManager.svelte'
  import { FLASHCARD_ICON } from './lib/flashcards'
  import type { Heading, PageContext, Pick } from './lib/context'
  import { ASK_ICON, QUIZ_ICON, SOCRATIC_ICON } from './lib/modes'
  import { currentEntry, fromIndex, type ReadingSpot } from './lib/outline'
  import OutlinePanel from './lib/OutlinePanel.svelte'
  import { isPdfFile } from './lib/pages'
  import { savedTool, saveTool, type Tool } from './lib/tools'
  import SettingsDialog from './lib/SettingsDialog.svelte'
  import { savedZoomFollowsChat } from './lib/chatZoom'
  import TopicProfileDialog from './lib/TopicProfileDialog.svelte'
  import TopicsSidebar from './lib/TopicsSidebar.svelte'
  import AddSourceMenu from './lib/AddSourceMenu.svelte'
  import SourceCard from './lib/SourceCard.svelte'
  import { CardHover } from './lib/cardHover.svelte'
  import { chatTitle, type FlashcardSource, type Mode, Workspace } from './lib/workspace.svelte'

  const workspace = new Workspace()
  let error = $state('')
  let dragging = $state(false)

  // The topics, tabs and chats are saved on disk through the backend and come back on load.
  // Saving only starts once the saved ones are back, so a failed load can't overwrite them.
  let restored = $state(false)
  // Each save says which revision it builds on and which tab sent it, so a tab working from an
  // older copy than another tab saved since can't save over it (the backend refuses: 409).
  let revision = 0
  const writer = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  // Set once another tab has saved since: this tab stops saving until it is reloaded.
  let staleTab = $state(false)

  onMount(async () => {
    try {
      const saved = await fetchSavedWorkspace()
      revision = typeof saved.revision === 'number' ? saved.revision : 0
      const docIds = workspace.restore(saved)
      for (const id of docIds) workspace.index(id)
      restored = true
    } catch {
      error = 'Could not load your saved topics. Is the backend running? Reload to try again.'
    }
  })

  let unsaved: string | undefined
  // What the last save sent, to send again when there is nothing new but PDFs to delete.
  let lastSaved: string | undefined
  let saveTimer: ReturnType<typeof setTimeout> | undefined
  let laterTimer: ReturnType<typeof setTimeout> | undefined
  let saving = false
  // Browsers drop a request sent as the page closes (keepalive) if its body is over 64 KB.
  const KEEPALIVE_LIMIT = 60_000
  // The backend keeps a PDF uploaded in the last 30 s; ask again after that.
  const DELETE_LATER_MS = 31_000

  /**
   * Send the latest changes, with the PDFs taken out of every topic since, for the backend to
   * delete. One save is sent at a time, so each builds on the revision the last one returned;
   * when the page is closing, it goes at once.
   */
  function saveNow(closing = false) {
    clearTimeout(saveTimer)
    if (staleTab || (saving && !closing)) return
    const json = unsaved ?? (workspace.hasReleased() ? lastSaved : undefined)
    if (json === undefined) return
    unsaved = undefined
    saving = true
    const release = workspace.takeReleased()
    const keepalive = closing && json.length < KEEPALIVE_LIMIT
    saveWorkspace(json, { base: revision, writer }, { keepalive, release })
      .then((saved) => {
        revision = Math.max(revision, saved.revision)
        lastSaved = json
        if (saved.later.length) {
          workspace.rerelease(saved.later)
          clearTimeout(laterTimer)
          laterTimer = setTimeout(saveNow, DELETE_LATER_MS)
        }
        if (error.startsWith('Could not save')) error = ''
      })
      .catch((failure) => {
        // A tab that has gone stale deletes nothing: the other tab's topics may still have them.
        if (failure instanceof BackendError && failure.status === 409) {
          staleTab = true
          return
        }
        workspace.rerelease(release)
        unsaved ??= json
        error = 'Could not save your topics. Is the backend running?'
      })
      .finally(() => {
        saving = false
        if (unsaved !== undefined && !staleTab) saveTimer = setTimeout(saveNow, 500)
      })
  }

  // A PDF taken out of every topic is deleted with a save, even one with nothing else new to save.
  workspace.onReleased = () => {
    if (!restored) return
    clearTimeout(saveTimer)
    saveTimer = setTimeout(saveNow, 500)
  }

  // Save shortly after each change, and right away when the page is hidden or closed.
  $effect(() => {
    const json = JSON.stringify(workspace.snapshot())
    if (!restored) return
    unsaved = json
    clearTimeout(saveTimer)
    saveTimer = setTimeout(saveNow, 500)
  })

  // The topics sidebar peeks out while its button or the sidebar itself is hovered, and stays
  // once pinned by clicking the button. Pinned is remembered in this browser.
  const PINNED_KEY = 'leqtern.sidebarPinned'
  function savedSidebarPinned() {
    try {
      return localStorage.getItem(PINNED_KEY) === '1'
    } catch {
      return false
    }
  }
  let sidebarPinned = $state(savedSidebarPinned())
  let sidebarPeek = $state(false)
  const sidebarOpen = $derived(sidebarPinned || sidebarPeek)
  let peekTimer: ReturnType<typeof setTimeout> | undefined
  const PEEK_GRACE_MS = 200
  function hoverSidebar(inside: boolean) {
    clearTimeout(peekTimer)
    if (inside) {
      sidebarPeek = true
      return
    }
    peekTimer = setTimeout(() => {
      // Not while a name is being typed in it: the box would lose what was typed.
      if (document.querySelector('#topics-sidebar input:focus')) return
      sidebarPeek = false
    }, PEEK_GRACE_MS)
  }
  function hideSidebarPeek() {
    clearTimeout(peekTimer)
    sidebarPeek = false
  }
  function togglePin() {
    sidebarPinned = !sidebarPinned
    // Unpinned with the pointer still on the button: it goes on peeking until the pointer leaves.
    sidebarPeek = !sidebarPinned
    try {
      localStorage.setItem(PINNED_KEY, sidebarPinned ? '1' : '0')
    } catch {
      // Not remembered, then.
    }
  }
  $effect(() => () => clearTimeout(peekTimer))
  let settingsOpen = $state(false)
  // Whether the PDF's zoom follows the chat opening and closing. Set in Settings.
  let zoomFollowsChat = $state(savedZoomFollowsChat())
  // The topic whose Scope and conventions are being edited, if any.
  let profileTopicId = $state<string>()
  const profileTopic = $derived(workspace.topics.find((t) => t.id === profileTopicId))
  // The Make flashcards menu, while open: the topic, what the cards are made from, and that in words.
  let making = $state.raw<{ topicId: string; source: FlashcardSource; about: string }>()
  // The topic whose deck the flashcard manager shows, if it is open.
  let deckTopicId = $state<string>()
  const deckTopic = $derived(workspace.topics.find((t) => t.id === deckTopicId))
  // Whether each topic's chat is showing, so a topic opens the way it was left. Not saved:
  // the chat starts hidden on every load.
  let chatOpenBy = $state<Record<string, boolean>>({})
  const chatOpen = $derived(!!workspace.activeTopicId && !!chatOpenBy[workspace.activeTopicId])
  function setChatOpen(open: boolean, topicId = workspace.activeTopicId) {
    if (topicId) chatOpenBy[topicId] = open
  }

  // The same card as the sidebar's sources, below a hovered tab.
  const tabCard = new CardHover()
  function showTabCard(id: string, tab: HTMLElement) {
    tabCard.show(id, () => {
      const box = tab.getBoundingClientRect()
      const width = 16 * parseFloat(getComputedStyle(document.documentElement).fontSize)
      return { x: Math.max(8, Math.min(box.left, window.innerWidth - width - 8)), y: box.bottom + 6 }
    })
  }
  $effect(() => () => tabCard.clear())

  /** A discussion picked (or started) in the sidebar: show it, ready to type. */
  function openChatFromSidebar() {
    setChatOpen(true)
    tick().then(() => chatPanel?.focus())
  }

  // What a left click on the PDF does. Each topic keeps its own, the same in all its tabs,
  // remembered in this browser; `picked` holds the picks made since the page loaded.
  let picked = $state<Record<string, Tool>>({})
  let tool = $derived.by<Tool>(() => {
    const id = workspace.activeTopic?.id
    return id ? (picked[id] ?? savedTool(id)) : 'select'
  })

  function setTool(value: Tool) {
    const id = workspace.activeTopic?.id
    if (!id) return
    picked[id] = value
    saveTool(
      id,
      value,
      workspace.topics.map((t) => t.id),
    )
  }

  let chatToggle = $state<HTMLButtonElement>()
  let chatPanel = $state<ChatPanel>()

  /** Whether a key press is typing into a text field, or meant for an open dialog or menu. */
  function keyIsForTarget(target: EventTarget | null) {
    if (document.querySelector('[aria-modal=true], [role=menu]')) return true
    if (!(target instanceof HTMLElement)) return false
    return target.isContentEditable || !!target.closest('input, textarea, select, [contenteditable]')
  }

  // Tabs stay mounted once opened, so switching back to one keeps its page,
  // zoom and scroll position without re-rendering.
  let mounted = $state<string[]>([])
  const panes: Record<string, DocPane> = $state({})

  let doc = $derived(workspace.activeDoc)

  // The browser tab names the open topic.
  $effect(() => {
    const name = workspace.activeTopic?.name.trim()
    document.title = name ? `${name} · Leqtern` : 'Leqtern'
  })

  $effect(() => {
    if (doc && !mounted.includes(doc.id)) mounted.push(doc.id)
  })

  // A tab brought back from the saved workspace fetches its PDF once it is shown.
  $effect(() => {
    for (const id of mounted) if (!workspace.docs[id]?.data) void workspace.loadPdf(id)
  })

  // Unmount the panes of closed tabs and deleted topics. A reopened tab starts fresh at its last page.
  $effect(() => {
    const open = mounted.filter((id) => workspace.isTabOpen(id))
    if (open.length !== mounted.length) mounted = open
  })

  // The row the open tab's controls are shown in, and the tabs that scroll next to it.
  let controlsEl = $state<HTMLElement>()
  let tabsEl = $state<HTMLElement>()

  // Keep the open tab in view when there are more tabs than fit, also when the row
  // narrows (the chat opening, the window shrinking).
  $effect(() => {
    if (!doc || !tabsEl) return
    const el = tabsEl
    const reveal = () =>
      el.querySelector('[aria-selected="true"]')?.scrollIntoView?.({ inline: 'nearest', block: 'nearest' })
    reveal()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(reveal)
    observer.observe(el)
    return () => observer.disconnect()
  })

  // A mouse wheel only scrolls up and down, so let it scroll the tabs sideways.
  // Reordering tabs by dragging them. The tab itself follows the pointer, and the tabs it passes
  // slide aside to show where it will land. Dropping slides it into that place, then the order is
  // saved; with the slides removed at the same moment, nothing on screen jumps.
  const DRAG_START_PX = 4
  const SETTLE_MS = 150
  let dragTab = $state<string>()
  let dragDx = $state(0)
  // Where the tab would land, counted among the other tabs.
  let dragTo = $state(0)
  let dragSettling = $state(false)
  // While a tab is dragged, the PDF, the chat and the sidebar ignore the pointer.
  let tabDragging = $state(false)
  // The row's layout when the drag started; transforms don't change offsetLeft.
  let dragGeometry: { lefts: number[]; widths: number[]; from: number; step: number } | undefined
  let suppressClick = false

  function tabPointerDown(event: PointerEvent, id: string) {
    if (event.button !== 0 || dragTab !== undefined || !tabsEl) return
    if ((event.target as Element).closest('.close, button.index-status')) return
    const startX = event.clientX
    const row = tabsEl
    let started = false
    const move = (e: PointerEvent) => {
      const dx = e.clientX - startX
      if (!started) {
        if (Math.abs(dx) < DRAG_START_PX) return
        started = true
        beginTabDrag(id, row)
      }
      if (!dragGeometry) return
      const { lefts, widths, from } = dragGeometry
      // Keep the tab inside the row.
      const min = -lefts[from]
      const max = lefts[lefts.length - 1] + widths[widths.length - 1] - (lefts[from] + widths[from])
      dragDx = Math.max(min, Math.min(max, dx))
      const centre = lefts[from] + widths[from] / 2 + dragDx
      dragTo = lefts.filter((l, i) => i !== from && l + widths[i] / 2 <= centre).length
    }
    const stop = (drop: boolean) => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', cancel)
      window.removeEventListener('keydown', escape, true)
      if (started) finishTabDrag(drop)
    }
    const up = () => stop(true)
    const cancel = () => stop(false)
    const escape = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      e.stopPropagation()
      stop(false)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', cancel)
    window.addEventListener('keydown', escape, true)
  }

  function beginTabDrag(id: string, row: HTMLElement) {
    tabCard.close()
    const tabs = [...row.querySelectorAll<HTMLElement>('.tab')]
    const from = (workspace.activeTopic?.openDocIds ?? []).indexOf(id)
    if (from === -1 || tabs.length === 0) return
    const lefts = tabs.map((t) => t.offsetLeft)
    const widths = tabs.map((t) => t.offsetWidth)
    const gap = parseFloat(getComputedStyle(row).columnGap) || 0
    dragGeometry = { lefts, widths, from, step: widths[from] + gap }
    dragTab = id
    dragDx = 0
    dragTo = from
    tabDragging = true
    // The release would otherwise click the tab under the pointer.
    suppressClick = true
  }

  function finishTabDrag(drop: boolean) {
    const id = dragTab
    const geometry = dragGeometry
    if (id === undefined || !geometry) return endTabDrag()
    const { lefts, widths, from } = geometry
    const to = drop ? dragTo : from
    // Slide into the place it lands in, then save the order.
    const landing = to >= from ? lefts[to] + widths[to] - widths[from] : lefts[to]
    dragTo = to
    dragSettling = true
    dragDx = landing - lefts[from]
    setTimeout(() => {
      if (to !== from) workspace.moveTab(id, to)
      endTabDrag()
    }, SETTLE_MS)
    // A click, if any, comes straight after the release.
    setTimeout(() => (suppressClick = false))
  }

  function endTabDrag() {
    dragTab = undefined
    dragGeometry = undefined
    dragDx = 0
    dragSettling = false
    tabDragging = false
  }

  /** How far a tab is moved: the dragged one with the pointer, the others aside to make room. */
  function tabShift(index: number): string | undefined {
    if (dragTab === undefined || !dragGeometry) return undefined
    const { from, step } = dragGeometry
    if (index === from) return `translateX(${dragDx}px)`
    if (index > from && index <= dragTo) return `translateX(${-step}px)`
    if (index < from && index >= dragTo) return `translateX(${step}px)`
    return undefined
  }

  function scrollTabs(event: WheelEvent) {
    if (event.deltaX !== 0 || event.ctrlKey || !tabsEl) return
    tabsEl.scrollLeft += event.deltaY
  }

  // Read at call time: bind:this fills `panes` after the tab mounts.
  const pane = (): DocPane | undefined => (doc ? panes[doc.id] : undefined)

  // Asking about a spot (or selected text), by a click with the Click to ask tool or
  // from the right-click menu, attaches it to the topic's chat in the mode it is for
  // and opens the chat. Its images render in the background; a question sent
  // meanwhile waits for them.
  // Per topic, so a pick in another topic can't drop this one's images.
  const latestPick: Record<string, number> = {}
  const capturing: Record<string, Promise<unknown>> = {}

  function onPick(docId: string, pick: Pick, mode: Mode | 'quiz' = 'normal') {
    const picked = workspace.docs[docId]
    const topic = workspace.topicOf(docId)
    if (!picked || !topic) return
    const n = (latestPick[topic.id] = (latestPick[topic.id] ?? 0) + 1)
    const context = { ...pick, docId, docName: picked.name, pageTexts: [] }
    if (mode === 'quiz') workspace.quizOn(topic.id, context)
    else workspace.attachContext(topic.id, context, mode)
    setChatOpen(true, topic.id)
    tick().then(() => chatPanel?.focus())
    capturing[topic.id] = (panes[docId]?.capture(pick) ?? Promise.resolve(undefined))
      .then((captured) => {
        // Unless another pick replaced it or it was removed meanwhile.
        if (captured && n === latestPick[topic.id] && topic.context?.docId === docId) {
          workspace.fillContext(topic.id, { ...captured, docId, docName: picked.name })
        }
      })
      .catch(() => {})
  }

  // Right-clicking a spot (or the selection) opens a menu of ways to study it, with either tool.
  type MenuTarget = { docId: string; pick: Pick; x: number; y: number }
  let menu = $state.raw<MenuTarget>()

  /** Put text on the clipboard, as the browser's own Copy would. */
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // No clipboard API (a page served over plain http): copy the selection the old way.
      document.execCommand('copy')
    }
  }

  /**
   * What the menu offers for a right-clicked spot or selection. Each of Ask, Socratic and
   * Quiz me attaches it to the chat, as a click with the Click to ask tool does: Ask waits for
   * a question, Socratic for what to focus on, if anything, and Quiz me puts "Quiz me on this"
   * in the box, to send or to add what to focus on.
   */
  function menuItems({ docId, pick }: MenuTarget): MenuItem[] {
    const items: MenuItem[] = [
      {
        label: 'Ask',
        icon: ASK_ICON,
        hint: 'Attach it to the chat to ask about it',
        onselect: () => onPick(docId, pick),
      },
      {
        label: 'Socratic',
        icon: SOCRATIC_ICON,
        hint: 'Work it out by answering questions',
        onselect: () => onPick(docId, pick, 'socratic'),
      },
      {
        label: 'Quiz me',
        icon: QUIZ_ICON,
        hint: 'Test yourself with a few questions',
        onselect: () => onPick(docId, pick, 'quiz'),
      },
      {
        label: 'Make flashcards',
        icon: FLASHCARD_ICON,
        hint: 'Write Anki cards on it for the topic’s deck',
        onselect: () => flashcardsFromPick(docId, pick),
      },
    ]
    const text = pick.selection
    if (text) {
      items.push({
        label: 'Copy',
        divider: true,
        // Two sheets, one on top of the other.
        icon: 'M10 9h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1zM15 9V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h4',
        onselect: () => copy(text),
      })
    }
    return items
  }

  /** Open the Make flashcards menu for a spot or selection; its images render meanwhile. */
  function flashcardsFromPick(docId: string, pick: Pick) {
    const picked = workspace.docs[docId]
    const topic = workspace.topicOf(docId)
    if (!picked || !topic) return
    const context: PageContext = { ...pick, docId, docName: picked.name, pageTexts: [] }
    const ready = (panes[docId]?.capture(pick) ?? Promise.resolve(undefined)).then(
      (captured) => captured && { ...captured, docId, docName: picked.name },
    )
    const where = `p. ${pick.page} of ${picked.name}`
    const about = pick.selection ? `Your selection on ${where}` : `The spot you right-clicked on ${where}`
    making = { topicId: topic.id, source: { kind: 'pick', context, ready }, about }
  }

  /** Open the Make flashcards menu for a discussion, up to one of its answers. */
  function flashcardsFromChat(chatId: string, messageId: string) {
    const topic = workspace.topics.find((t) => t.chats.some((c) => c.id === chatId))
    const chat = topic?.chats.find((c) => c.id === chatId)
    if (!topic || !chat) return
    const last = chat.messages.at(-1)?.id === messageId
    const about = `The discussion “${chatTitle(chat)}”${last ? '' : ', up to the answer you picked'}`
    making = { topicId: topic.id, source: { kind: 'chat', chatId, messageId }, about }
  }

  /** The topic's open page as context, for a question asked without clicking anything. */
  async function openPageContext(topicId: string): Promise<PageContext | undefined> {
    const docId = workspace.topics.find((t) => t.id === topicId)?.activeDocId
    const open = docId ? workspace.docs[docId] : undefined
    const captured = docId ? await panes[docId]?.capture() : undefined
    return open && captured ? { ...captured, docId: open.id, docName: open.name } : undefined
  }

  async function send(topicId: string) {
    await capturing[topicId]
    workspace.ask(topicId, () => openPageContext(topicId))
  }

  /** Show where a chat chip or citation points: its tab, page and spot. */
  async function reveal(target: Pick & { docId: string }) {
    if (!workspace.docs[target.docId]) return
    workspace.selectDoc(target.docId)
    await tick()
    panes[target.docId]?.reveal(target)
  }

  /** The spot attached to a tab's topic, when it is in that tab's PDF. */
  function markerFor(docId: string): Pick | undefined {
    const context = workspace.topicOf(docId)?.context
    return context?.docId === docId ? context : undefined
  }

  /** A tab's indexing progress in a few words, or nothing once it is ready. */
  function indexLabel(docId: string): string | undefined {
    const state = workspace.indexing[docId]
    if (!state || state.status === 'ready') return undefined
    if (state.status === 'error') return 'Not indexed'
    if (state.status === 'indexing' && state.pageCount) {
      return `Indexing ${Math.round((100 * state.pagesDone) / state.pageCount)}%`
    }
    return 'Indexing…'
  }

  function indexTitle(docId: string): string {
    const state = workspace.indexing[docId]
    if (state?.status === 'error') {
      return `Could not index this PDF (${state.error ?? 'unknown error'}). You can still ask about the open page.`
    }
    return 'Indexing so the whole topic can be searched. You can already ask about the open page.'
  }

  let fileInput: HTMLInputElement

  /** Open each PDF as a tab in the active topic. Several at once all go into the same topic. */
  async function open(files: FileList | File[] | null | undefined) {
    const list = Array.from(files ?? [])
    if (!list.length) return
    const pdfs = list.filter(isPdfFile)
    const skipped = list.filter((f) => !isPdfFile(f)).map((f) => f.name)
    error = skipped.length ? `${skipped.join(', ')} ${skipped.length === 1 ? 'is' : 'are'} not a PDF.` : ''
    if (!pdfs.length) return
    // Get a peeking sidebar out of the way of the new PDFs.
    hideSidebarPeek()
    // Read them all first, so a slow file can't reorder the tabs.
    const loaded = await Promise.all(pdfs.map(async (f) => [f.name, new Uint8Array(await f.arrayBuffer())] as const))
    const added = loaded.map(([name, data]) => workspace.addDoc(name, data))
    // Land on the first one, as the reader picked them.
    workspace.selectDoc(added[0].id)
    // Index them in the background, so the whole topic can be searched, opened or not.
    for (const doc of added) if (!workspace.indexing[doc.id]) workspace.index(doc.id)
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    dragging = false
    open(event.dataTransfer?.files)
  }

  // The open tab's chapters and sections, shown over the PDF by the button left of the tabs.
  // The PDF's own bookmarks when it has them, else the sections the index has found so far.
  let outlineOpen = $state(false)
  let outline = $state<{ docId: string; entries: Heading[] }>()

  $effect(() => {
    if (!outlineOpen || !doc) return
    const id = doc.id
    const serverId = workspace.indexing[id]?.serverId
    // Look again as indexing gets further, so a new PDF's outline fills in.
    void workspace.indexing[id]?.pagesDone
    let stale = false
    ;(async () => {
      const bookmarks = (await panes[id]?.outline()) ?? []
      const entries = bookmarks.length
        ? bookmarks.map((b) => ({ ...b, level: Math.min(b.level, 3) }))
        : serverId
          ? fromIndex(await fetchIndexSections(serverId).catch(() => []))
          : []
      if (!stale) outline = { docId: id, entries }
    })()
    return () => {
      stale = true
    }
  })

  // Where each tab is being read, and where the headings on that page are, so the outline
  // can mark the section being read, switching as a heading scrolls past.
  let reading = $state<Record<string, ReadingSpot>>({})
  let pageSpots = $state.raw<{ entries: Heading[]; page: number; spots: (number | undefined)[] }>()

  $effect(() => {
    if (!outlineOpen || !doc || outline?.docId !== doc.id) return
    const id = doc.id
    const entries = outline.entries
    const page = reading[id]?.page ?? workspace.pages[id] ?? 1
    if (pageSpots?.entries === entries && pageSpots.page === page) return
    let stale = false
    Promise.all(entries.map((e) => (e.page === page ? (panes[id]?.spotOf(e) ?? undefined) : undefined))).then((spots) => {
      if (!stale) pageSpots = { entries, page, spots }
    })
    return () => {
      stale = true
    }
  })

  let currentSection = $derived.by(() => {
    if (!doc || outline?.docId !== doc.id) return -1
    const at = reading[doc.id] ?? { page: workspace.pages[doc.id] ?? 1, y: 0 }
    const spots = pageSpots?.entries === outline.entries && pageSpots.page === at.page ? pageSpots.spots : []
    return currentEntry(outline.entries, at, spots)
  })

  function outlineEmpty(docId: string): string {
    const state = workspace.indexing[docId]
    if (state?.status === 'error') return 'This PDF has no outline of its own, and it could not be indexed to make one.'
    if (state && state.status !== 'ready') return 'This PDF has no outline of its own. One will appear here as it is indexed.'
    return 'No chapters or sections were found in this PDF.'
  }

  function goToSection(heading: Heading) {
    pane()?.goToHeading(heading)
    outlineOpen = false
  }

  function onKeydown(event: KeyboardEvent) {
    const mod = event.ctrlKey || event.metaKey
    if (event.key === 'Escape' && outlineOpen && !(event.target as Element | null)?.closest?.('#chat-panel')) {
      outlineOpen = false
      return
    }
    if (mod && event.key === 'o') {
      event.preventDefault()
      fileInput.click()
    }
    // C opens the chat, ready to type, or closes it, unless the key is typing or meant for a menu.
    // (Enter and Escape stay with focused buttons and the browser's full screen.)
    if (event.key.toLowerCase() === 'c' && !mod && !event.shiftKey && !event.altKey && !event.isComposing && !event.repeat) {
      if (workspace.activeTopic && !keyIsForTarget(event.target)) {
        event.preventDefault()
        // Closing by key leaves focus where it was, or on the page if it was in the chat:
        // focusing the toggle from a key press would show its outline and tooltip.
        if (chatOpen) chatPanel?.close(false)
        else {
          setChatOpen(true)
          tick().then(() => chatPanel?.focus())
        }
      }
      return
    }
    if (!doc) return
    // Zoom the PDF rather than the whole page, like browser PDF viewers do.
    if (mod && (event.key === '+' || event.key === '=')) {
      event.preventDefault()
      pane()?.zoomIn()
    } else if (mod && event.key === '-') {
      event.preventDefault()
      pane()?.zoomOut()
    } else if (mod && event.key === '0') {
      event.preventDefault()
      pane()?.fitWidth()
    }
  }

</script>

<svelte:window onkeydown={onKeydown} onpagehide={() => saveNow(true)} />
<svelte:document
  onvisibilitychange={() => {
    // Hidden pages usually keep running, so this save is not limited like one sent on close.
    if (document.visibilityState === 'hidden') saveNow()
  }}
/>

<div
  class="app"
  class:tab-dragging={tabDragging}
  role="application"
  ondragover={(e) => {
    // Only files dropped from outside show the drop overlay, not a tab being reordered.
    if (!e.dataTransfer?.types.includes('Files')) return
    e.preventDefault()
    dragging = true
  }}
  ondragleave={(e) => {
    if (e.relatedTarget === null) dragging = false
  }}
  ondrop={onDrop}
  onpointerdown={(e) => {
    // Pressing anywhere but the sidebar (the PDF, the tabs, the chat) ends a peek. Pinned, it stays.
    const target = e.target as Element
    if (!target.closest('#topics-sidebar, .sidebar-toggle, .settings-dialog, .topic-profile-dialog, .flashcard-dialog, .flashcard-manager')) {
      hideSidebarPeek()
    }
    // The outline closes too, unless the press is in it or on its button.
    if (!target.closest('#topics-sidebar, #doc-outline, .outline-toggle')) outlineOpen = false
  }}
>
  <!-- Stays in the top left corner whether the sidebar is shown or not; Leqtern slides in beside it. -->
  <button
    type="button"
    class="icon-button sidebar-toggle"
    class:pressed={sidebarPinned}
    aria-label={sidebarPinned ? 'Hide topics' : 'Show topics'}
    aria-expanded={sidebarPinned}
    aria-controls="topics-sidebar"
    title={sidebarPinned ? 'Hide sidebar' : 'Show sidebar'}
    onclick={togglePin}
    onpointerenter={() => hoverSidebar(true)}
    onpointerleave={() => hoverSidebar(false)}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5" /><path d="M9 4v16" /></svg>
  </button>
  <TopicsSidebar
    {workspace}
    open={sidebarOpen}
    pinned={sidebarPinned}
    onhover={hoverSidebar}
    {chatOpen}
    onopenchat={openChatFromSidebar}
    onopensettings={() => (settingsOpen = true)}
    onupload={() => fileInput.click()}
    onopenprofile={(id) => (profileTopicId = id)}
    onopenflashcards={(id) => (deckTopicId = id)}
  />
  {#if settingsOpen}<SettingsDialog {workspace} bind:zoomFollowsChat onclose={() => (settingsOpen = false)} />{/if}
  {#if profileTopic}<TopicProfileDialog topic={profileTopic} onclose={() => (profileTopicId = undefined)} />{/if}
  {#if making && workspace.topics.some((t) => t.id === making?.topicId)}
    {@const { topicId } = making}
    <FlashcardDialog
      {workspace}
      {topicId}
      source={making.source}
      about={making.about}
      onclose={() => (making = undefined)}
      onreveal={reveal}
      onopendeck={() => {
        making = undefined
        deckTopicId = topicId
      }}
    />
  {/if}
  {#if deckTopic}
    <FlashcardManager {workspace} topic={deckTopic} onclose={() => (deckTopicId = undefined)} onreveal={reveal} />
  {/if}

  <div class="main" class:beside-sidebar={sidebarPinned && zoomFollowsChat}>
    <input
      bind:this={fileInput}
      type="file"
      accept="application/pdf,.pdf"
      multiple
      hidden
      data-testid="file-input"
      onchange={(e) => {
        open(e.currentTarget.files)
        e.currentTarget.value = ''
      }}
    />

    {#if staleTab}
      <p class="error" role="alert">
        Your topics were changed in another tab, so this tab stopped saving. Reload it to continue; changes made here since
        are not saved.
        <button type="button" class="reload" onclick={() => location.reload()}>Reload</button>
      </p>
    {/if}
    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    {#if workspace.activeTopic}
      <!-- One row: the tabs scroll sideways when there are many, the controls never shrink. -->
      <div class="tabrow" class:chat-closed={!chatOpen} class:sidebar-pinned={sidebarPinned && !zoomFollowsChat}>
        <button
          type="button"
          class="icon-button outline-toggle"
          class:pressed={outlineOpen}
          disabled={!doc}
          aria-label="Outline"
          aria-expanded={outlineOpen}
          aria-controls="doc-outline"
          title="Outline"
          onclick={() => (outlineOpen = !outlineOpen)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M8 12h12M8 18h12" /></svg>
        </button>
        <!-- Not focusable itself: its tabs are, and the drag handlers only take drops. -->
        <!-- svelte-ignore a11y_interactive_supports_focus -->
        <div
          class="tabs"
          role="tablist"
          aria-label={`PDFs in ${workspace.activeTopic.name}`}
          bind:this={tabsEl}
          onwheel={(e) => {
            tabCard.close()
            scrollTabs(e)
          }}
          class:reordering={dragTab !== undefined}
          onclickcapture={(e) => {
            if (!suppressClick) return
            e.preventDefault()
            e.stopPropagation()
          }}
        >
          {#each workspace.activeTopic.openDocIds as id, index (id)}
            <div
              class="tab"
              class:active={id === doc?.id}
              class:dragged={id === dragTab}
              class:settling={id === dragTab && dragSettling}
              role="presentation"
              style:transform={tabShift(index)}
              onpointerdown={(e) => tabPointerDown(e, id)}
              onpointerenter={(e) => {
                if (dragTab === undefined) showTabCard(id, e.currentTarget)
              }}
              onpointerleave={() => tabCard.leave()}
            >
              <button
                type="button"
                role="tab"
                aria-selected={id === doc?.id}
                onclick={() => workspace.selectDoc(id)}>{workspace.docName(id)}</button
              >
              {#if workspace.indexing[id]?.status === 'error'}
                <button type="button" class="index-status failed" title={`${indexTitle(id)} Click to try again.`} onclick={() => workspace.retryIndex(id)}
                  >{indexLabel(id)}</button
                >
              {:else if indexLabel(id)}
                <span class="index-status" title={indexTitle(id)}>{indexLabel(id)}</span>
              {/if}
              <button type="button" class="close" aria-label={`Close ${workspace.docName(id)}`} onclick={() => workspace.closeDoc(id)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
              </button>
            </div>
          {/each}
        </div>
        <AddSourceMenu {workspace} onupload={() => fileInput.click()} />
        <div class="controls-slot" bind:this={controlsEl}></div>
        <!-- Fixed in the window's top right corner. The chat panel opens over that corner and
             shows its close button in the same spot, so this fades out while the chat is open. -->
        <button
          type="button"
          class="icon-button chat-toggle"
          class:hidden={chatOpen}
          inert={chatOpen}
          bind:this={chatToggle}
          aria-label="Show chat"
          aria-keyshortcuts="C"
          aria-expanded={chatOpen}
          aria-controls="chat-panel"
          onclick={() => setChatOpen(!chatOpen)}
        >
          <span class="tip" aria-hidden="true">Chat <kbd>C</kbd></span>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8z"
            />
          </svg>
        </button>
      </div>
    {/if}

    <main class="stage">
      {#each mounted as id (id)}
        {@const d = workspace.docs[id]}
        {@const failed = workspace.pdfErrors[id]}
        {#if d && (failed || !d.data)}
          <div class="tabpanel" class:active={id === doc?.id} inert={id !== doc?.id} role="tabpanel" aria-label={d.name}>
            <div class="empty">
              {#if failed}
                <p>{failed}</p>
                <button type="button" onclick={() => workspace.retryPdf(id)}>Try again</button>
                <p class="hint">The PDF stays in the topic. To take it out, delete it from the topic's sources.</p>
              {:else}
                <p class="hint">Opening {d.name}…</p>
              {/if}
            </div>
          </div>
        {:else if d?.data}
          <div class="tabpanel" class:active={id === doc?.id} inert={id !== doc?.id} role="tabpanel" aria-label={d.name}>
            <DocPane
              bind:this={panes[id]}
              data={d.data}
              startPage={workspace.pages[id]}
              onpagechange={(page) => {
                workspace.pages[id] = page
              }}
              onreadingspot={(spot) => {
                reading[id] = spot
              }}
              active={id === doc?.id}
              controlsTarget={controlsEl}
              marker={markerFor(id)}
              reserve={chatOpen || zoomFollowsChat ? 0 : chatReserve()}
              {chatOpen}
              followChat={zoomFollowsChat}
              sidebarPinned={sidebarPinned && zoomFollowsChat}
              {tool}
              ontoolchange={setTool}
              onpick={(p) => onPick(id, p)}
              oncontextpick={(pick, at) => (menu = { docId: id, pick, ...at })}
              onmarkerclick={() => {
                const topic = workspace.topicOf(id)
                if (topic) workspace.clearContext(topic.id)
              }}
              onerror={() => {
                // A PDF the backend has (and may have indexed) stays in its topic; one that never got
                // that far, like a file that isn't a PDF after all, is taken out again.
                if (workspace.indexing[id]?.serverId) {
                  workspace.pdfFailed(id, `Could not show ${d.name}. It may be damaged or password-protected.`)
                } else {
                  error = `Could not open ${d.name}. Is it a valid PDF?`
                  workspace.removeDoc(id)
                }
              }}
            />
          </div>
        {/if}
      {/each}

      {#if outlineOpen && doc}
        <OutlinePanel
          entries={outline?.docId === doc.id ? outline.entries : undefined}
          empty={outlineEmpty(doc.id)}
          current={currentSection}
          ongo={goToSection}
          onclose={() => (outlineOpen = false)}
        />
      {/if}

      {#if !workspace.activeTopic}
        <div class="empty">
          <p>Open a PDF to start reading.</p>
          <button type="button" onclick={() => fileInput.click()}>Choose a file</button>
          <p class="hint">or drop PDFs anywhere in this window</p>
        </div>
      {:else if !doc}
        <div class="empty">
          <p>Add a PDF to {workspace.activeTopic.name}.</p>
          <button type="button" onclick={() => fileInput.click()}>Choose a file</button>
          <p class="hint">Each PDF in a topic opens as a tab, so you can switch between them.</p>
        </div>
      {/if}
      {#if dragging}
        <div class="drop-overlay">Drop to open</div>
      {/if}
    </main>
  </div>

  <!-- The toggle is inert while the chat is open, so focus can only go back once it is not. -->
  <ChatPanel
    bind:this={chatPanel}
    {workspace}
    bind:open={() => chatOpen, setChatOpen}
    onclose={() => tick().then(() => chatToggle?.focus())}
    onsend={send}
    onreveal={reveal}
    onflashcards={flashcardsFromChat}
  />

  <SourceCard {workspace} hover={tabCard} placement="below" />

  {#if menu}
    <ContextMenu x={menu.x} y={menu.y} label="Study this" items={menuItems(menu)} onclose={() => (menu = undefined)} />
  {/if}
</div>

<style>
  .app {
    position: relative;
    display: flex;
    height: 100vh;
  }
  .app.tab-dragging :is(.stage, :global(#chat-panel), :global(#topics-sidebar)) {
    pointer-events: none;
  }

  .error {
    margin: 0;
    padding: 0.5rem 1rem;
    background: #ffebe9;
    color: #82071e;
  }

  .main {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    transition: margin-left 0.2s ease;
  }
  /* Pinned with "Fit to chat": the sidebar takes its room like the chat, and the PDF fits beside it.
     With "Fixed size" it lies over the PDF instead, and only the tab row makes way. */
  .main.beside-sidebar {
    margin-left: 15rem;
  }

  /* In the top left corner, over the sidebar, where the tab row leaves room for it. */
  .sidebar-toggle {
    position: absolute;
    top: 0.25rem;
    left: 0.625rem;
    z-index: 31;
  }
  .sidebar-toggle svg {
    width: 1.1rem;
    height: 1.1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
  }

  /* The chrome around the PDF shares the sidebar's and the chat's background, shapes and hover shade. */
  .tabrow {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--border);
    background: var(--sidebar-bg);
    /* Above the tabs' hover card, which slides out from under it. */
    position: relative;
    z-index: 26;
    /* Room on the left for the sidebar button in the corner. */
    padding-left: 2.75rem;
    transition:
      padding-right 0.2s ease,
      padding-left 0.2s ease;
  }
  /* The sidebar lies over the PDF but not over the tab row, which moves along beside it. */
  .tabrow.sidebar-pinned {
    padding-left: calc(15rem + 0.5rem);
  }
  /* Pinned beside the PDF, the sidebar holds the button, so the tab row needs no room for it. */
  .beside-sidebar .tabrow {
    padding-left: 0.5rem;
  }
  /* Room for the chat icon in the corner. With the chat open, the panel takes that corner. */
  .tabrow.chat-closed {
    padding-right: calc(0.5rem + 1.75rem + 0.25rem);
  }
  @media (prefers-reduced-motion: reduce) {
    .tabrow,
    .main {
      transition: none;
    }
  }

  .tabs {
    display: flex;
    align-items: center;
    gap: 0.125rem;
    /* Tabs shrink and scroll; the controls beside them keep their size. */
    flex: 0 1 auto;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
    position: relative;
  }

  .controls-slot {
    flex-shrink: 0;
    margin-left: auto;
  }

  /* A tab is a row like the sidebar's topics: no frame, a shade on hover and the open one. */
  .tab {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    max-width: 14rem;
    height: 1.75rem;
    border-radius: var(--radius);
    color: var(--muted);
    font-size: 0.9rem;
  }
  /* While a tab is dragged, the others slide aside; the dragged one follows the pointer, lifted. */
  .tabs.reordering {
    user-select: none;
    cursor: grabbing;
  }
  .tabs.reordering .tab {
    transition: transform 150ms ease;
  }
  .tabs.reordering .tab.dragged {
    position: relative;
    z-index: 1;
    background: var(--surface);
    color: inherit;
    box-shadow: 0 4px 12px rgb(0 0 0 / 0.18);
    transition: none;
  }
  .tabs.reordering .tab.dragged.settling {
    transition: transform 150ms ease;
  }
  .tabs.reordering .tab [role='tab'] {
    cursor: grabbing;
  }
  @media (prefers-reduced-motion: reduce) {
    .tabs.reordering .tab,
    .tabs.reordering .tab.dragged.settling {
      transition: none;
    }
  }
  .tab:hover,
  .tab.active {
    background: var(--hover);
  }
  .tab.active {
    color: inherit;
  }

  .tab [role='tab'] {
    overflow: hidden;
    height: 100%;
    padding: 0 0.25rem 0 0.625rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    font: inherit;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }
  .tab [role='tab']:focus-visible,
  .tab .close:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  .tab .close {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 1.25rem;
    height: 1.25rem;
    margin-right: 0.25rem;
    padding: 0;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    cursor: pointer;
    opacity: 0.6;
  }
  .tab .close:hover {
    background: color-mix(in srgb, currentColor 14%, transparent);
    opacity: 1;
  }
  .tab .close svg {
    width: 0.75rem;
    height: 0.75rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.2;
    stroke-linecap: round;
  }

  .index-status {
    flex-shrink: 0;
    margin-right: 0.125rem;
    font-size: 0.7rem;
    color: var(--muted);
    white-space: nowrap;
  }
  .index-status.failed {
    color: #b35900;
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    font-size: 0.7rem;
    cursor: pointer;
  }
  .index-status.failed:hover {
    text-decoration: underline;
  }

  .reload {
    margin-left: 0.5rem;
  }

  .outline-toggle,
  .sidebar-toggle {
    color: var(--muted);
  }
  .outline-toggle:hover,
  .outline-toggle.pressed,
  .sidebar-toggle:hover,
  .sidebar-toggle.pressed {
    color: inherit;
  }
  .outline-toggle.pressed {
    background: var(--hover);
  }
  .outline-toggle:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .chat-toggle {
    position: fixed;
    top: 0.25rem;
    right: 0.5rem;
    z-index: 5;
    transition: opacity 0.15s;
  }
  .chat-toggle.hidden {
    opacity: 0;
    pointer-events: none;
  }

  .stage {
    position: relative;
    flex: 1;
    min-height: 0;
  }

  /* Inactive tabs stay laid out (so they keep their scroll position) but hidden. */
  .tabpanel {
    position: absolute;
    inset: 0;
    visibility: hidden;
  }
  .tabpanel.active {
    visibility: visible;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 0.5rem;
  }

  .hint {
    color: var(--muted);
    font-size: 0.9rem;
    margin: 0;
  }

  .drop-overlay {
    position: absolute;
    inset: 0.5rem;
    display: grid;
    place-items: center;
    border: 3px dashed var(--accent);
    border-radius: 0.5rem;
    background: color-mix(in srgb, var(--surface) 85%, transparent);
    font-size: 1.25rem;
    pointer-events: none;
  }
</style>
