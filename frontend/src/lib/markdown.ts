import DOMPurify from 'dompurify'
import katex from 'katex'
import { Marked, type TokenizerAndRendererExtension } from 'marked'

/** Typeset LaTeX with KaTeX. Bad or half-streamed LaTeX shows as red source rather than throwing. */
function tex(source: string, displayMode: boolean): string {
  return katex.renderToString(source, { displayMode, throwOnError: false, output: 'htmlAndMathml' })
}

// Display maths: $$...$$ or \[...\], which may span lines.
const blockMath: TokenizerAndRendererExtension = {
  name: 'blockMath',
  level: 'block',
  start: (src) => src.match(/\$\$|\\\[/)?.index,
  tokenizer(src) {
    const match = /^\$\$([\s\S]+?)\$\$[^\S\n]*(?:\n|$)/.exec(src) ?? /^\\\[([\s\S]+?)\\\][^\S\n]*(?:\n|$)/.exec(src)
    if (match) return { type: 'blockMath', raw: match[0], text: match[1].trim() }
  },
  renderer: (token) => `<div class="math-display">${tex(token.text, true)}</div>\n`,
}

// Inline maths: \(...\), $$...$$ inside a line, or $...$. For single dollars the opening $ must
// not be followed by a space and the closing $ must not be preceded by one or followed by a
// digit, so prices like "$5 and $10" stay as text.
const inlineMath: TokenizerAndRendererExtension = {
  name: 'inlineMath',
  level: 'inline',
  start: (src) => src.match(/\$|\\\(/)?.index,
  tokenizer(src) {
    const match =
      /^\\\(([\s\S]+?)\\\)/.exec(src) ??
      /^\$\$([^$]+?)\$\$/.exec(src) ??
      /^\$(?!\s)((?:\\\$|[^$\n])+?)(?<!\s)\$(?!\d)/.exec(src)
    if (match) return { type: 'inlineMath', raw: match[0], text: match[1].trim(), display: match[0].startsWith('$$') }
  },
  // Short maths like "n − 1" stays on one line; a long formula may break after a relation or
  // operator, so it can't push the answer wider than the chat.
  renderer: (token) =>
    token.display
      ? `<span class="math-display">${tex(token.text, true)}</span>`
      : token.text.length > LONG_INLINE
        ? `<span class="math-long">${tex(token.text, false)}</span>`
        : tex(token.text, false),
}

/** Inline maths longer than this many characters of LaTeX may wrap. */
const LONG_INLINE = 24

// Links open in a new tab: following one in place would leave the app and lose the open PDFs.
// Nothing in an answer may load from elsewhere: text in a PDF could get the model to write an
// image or style whose address carries what it was shown (the reader's notes, the question).
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.getAttribute('href')) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
  if (/url\s*\(/i.test(node.getAttribute('style') ?? '')) node.removeAttribute('style')
})

const marked = new Marked({ gfm: true, breaks: true, extensions: [blockMath, inlineMath] })

/** Which PDFs an answer's citations can point at (see linkCitations). */
export type CitableDocs = {
  /** The topic's PDF names. */
  names: string[]
  /** The backend's aliases for them, like D1, as the model sees them. */
  aliases?: Record<string, string>
  /** The PDF a citation with only a page, like "(p. 12)", is about: the one the question was asked in. */
  current?: string
}

/**
 * Turn an answer's Markdown, with LaTeX maths, into HTML that is safe to insert: the model's
 * text is untrusted, so anything like scripts or event handlers is stripped. Citations of the
 * PDFs in `docs` become links (see linkCitations).
 */
export function renderMarkdown(source: string, docs?: CitableDocs): string {
  const html = marked.parse(source, { async: false })
  // KaTeX's MathML copy (for screen readers and copying) keeps the LaTeX in <annotation>.
  const options = {
    ADD_TAGS: ['semantics', 'annotation'],
    ADD_ATTR: ['target', 'encoding'],
    FORBID_TAGS: ['img', 'image', 'video', 'audio', 'source', 'picture', 'link', 'style'],
    FORBID_ATTR: ['srcset', 'background', 'poster'],
  }
  if (!docs?.names.length) return DOMPurify.sanitize(html, options)
  const root = document.createElement('div')
  root.append(DOMPurify.sanitize(html, { ...options, RETURN_DOM_FRAGMENT: true }))
  linkCitations(root, docs)
  return root.innerHTML
}

/**
 * The text of a selection in a rendered answer, to quote it back: maths goes back to its LaTeX
 * (from KaTeX's annotation, as $...$ or $$...$$) and blocks keep their line breaks.
 */
export function selectedMarkdown(range: Range): string {
  const root = document.createElement('div')
  // A selection inside one formula holds only part of KaTeX's output, so it takes the whole formula.
  const formula = (range.commonAncestorContainer instanceof Element
    ? range.commonAncestorContainer
    : range.commonAncestorContainer.parentElement
  )?.closest('.katex')
  root.append(formula ? formula.cloneNode(true) : range.cloneContents())
  for (const katex of root.querySelectorAll('.katex')) {
    const source = katex.querySelector('annotation[encoding="application/x-tex"]')?.textContent?.trim()
    const display = !!katex.closest('.katex-display') || (!!formula && !!formula.closest('.katex-display'))
    katex.replaceWith(source ? (display ? `$$${source}$$` : `$${source}$`) : '')
  }
  for (const block of root.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, pre, blockquote, tr, .math-display')) {
    block.append('\n')
  }
  return (root.textContent ?? '').replace(/\u2060/g, '').replace(/[^\S\n]*\n\s*/g, '\n').trim()
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// "p. 41", "pp. 41–43", also spelled out or in Swedish ("page 41", "s. 41", "sid. 41").
const PAGES = String.raw`(?:pp?\.|pages?|ss?\.|sid\.|sidorna|sidan|sida)\s*(\d+)(?:\s*[–—-]\s*(\d+))?`

/**
 * Wrap page citations in links carrying the PDF's name and the first page, so the chat can show
 * that page. ask.py asks for "(book.pdf, p. 41)" or "(book.pdf, pp. 41–43)"; the model sometimes
 * leaves out ".pdf" or the comma, uses the alias it sees in tool results ("D1, p. 41", shown with
 * the PDF's name instead), or gives only the page ("(p. 41)"), which means `current`.
 * Code, maths and links are left alone.
 */
export function linkCitations(root: HTMLElement, docs: CitableDocs) {
  const byName = new Map<string, string>()
  for (const doc of docs.names) {
    byName.set(doc.toLowerCase(), doc)
    const bare = doc.replace(/\.pdf$/i, '')
    if (bare && bare !== doc) byName.set(bare.toLowerCase(), doc)
  }
  const byAlias = new Map<string, string>()
  for (const [alias, doc] of Object.entries(docs.aliases ?? {})) {
    if (docs.names.includes(doc)) byAlias.set(alias.toLowerCase(), doc)
  }
  const names = [...byName.keys(), ...byAlias.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp)
  if (!names.length) return
  const named = String.raw`(?<![\w.-])(${names.join('|')}),?\s*${PAGES}`
  // A page alone counts only right after an opening parenthesis, as in "(p. 41)".
  const alone = String.raw`(?<=\(\s*)${PAGES}`
  const pattern = new RegExp(docs.current ? `${named}|${alone}` : named, 'gi')

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest('code, pre, a, button, .katex') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  })
  const texts: Text[] = []
  while (walker.nextNode()) texts.push(walker.currentNode as Text)

  for (const node of texts) {
    const text = node.data
    const matches = [...text.matchAll(pattern)]
    if (!matches.length) continue
    const pieces: (string | HTMLElement)[] = []
    let at = 0
    for (const match of matches) {
      const [whole, name, namedPage, namedEnd, alonePage, aloneEnd] = match
      const key = name?.toLowerCase()
      const doc = key ? (byName.get(key) ?? byAlias.get(key)!) : docs.current!
      const page = namedPage ?? alonePage
      const end = namedEnd ?? aloneEnd
      // An alias means nothing to the reader, so the link shows the PDF's name instead.
      const shown = key && byAlias.has(key) && !byName.has(key) ? doc + whole.slice(name.length) : whole
      pieces.push(text.slice(at, match.index))
      // A link, so it wraps with the sentence like text; the chat handles its click.
      const link = document.createElement('a')
      link.href = '#'
      link.className = 'citation'
      link.dataset.doc = doc
      link.dataset.page = page
      if (end && Number(end) > Number(page)) link.dataset.end = end
      link.title = `Show ${doc}, p. ${page}`
      // Non-breaking spaces keep "p. 41" with its PDF's name when the line wraps.
      const lead = key ? shown.length - (whole.length - name.length) : 0
      link.textContent = shown.slice(0, lead) + shown.slice(lead).replace(/\s+/g, '\u00a0')
      pieces.push(link)
      at = match.index + whole.length
    }
    pieces.push(text.slice(at))
    node.replaceWith(...pieces)
  }
  iconCitations(root)
}

/** One cited place: a PDF by name, its first page and, for a range, its last. */
export type Cite = { doc: string; page: number; end?: number }

const BOOK_ICON =
  '<svg class="cite-book" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3.5C6.6 2.6 4.6 2.3 2.5 2.5v9.5c2.1-.2 4.1.1 5.5 1 1.4-.9 3.4-1.2 5.5-1V2.5c-2.1-.2-4.1.1-5.5 1zM8 3.5v9.5"/></svg>'

/**
 * Citations in parentheses, like "is linear (book.pdf, p. 41)." or "(a.pdf, p. 3; b.pdf, p. 9)",
 * become one small book icon right after the claim, in place of the parentheses. The icon carries
 * every place it cites; the original text stays inside it, hidden, so copying the answer keeps it.
 * A citation written into the sentence itself ("see book.pdf, p. 41") stays a text link.
 */
function iconCitations(root: HTMLElement) {
  const done = new Set<Element>()
  for (const first of root.querySelectorAll<HTMLAnchorElement>('a.citation')) {
    if (done.has(first)) continue
    // The citations that follow it with only commas, semicolons or spaces between.
    const group = [first]
    for (let next = first.nextSibling; next; ) {
      if (next instanceof Text && /^[\s,;]*$/.test(next.data) && next.nextSibling instanceof HTMLAnchorElement) {
        next = next.nextSibling
      } else if (next instanceof HTMLAnchorElement && next.classList.contains('citation')) {
        group.push(next)
        next = next.nextSibling
      } else break
    }
    group.forEach((link) => done.add(link))
    const before = first.previousSibling
    const after = group[group.length - 1].nextSibling
    const open = before instanceof Text ? /\s*\(\s*$/.exec(before.data) : null
    const close = after instanceof Text ? /^\s*\)/.exec(after.data) : null
    if (!open || !close || !(before instanceof Text) || !(after instanceof Text)) continue

    const range = document.createRange()
    range.setStart(before, open.index)
    range.setEnd(after, close[0].length)
    const original = range.toString().replace(/\u00a0/g, ' ')
    const cites: Cite[] = group.map((link) => ({
      doc: link.dataset.doc!,
      page: Number(link.dataset.page),
      ...(link.dataset.end ? { end: Number(link.dataset.end) } : {}),
    }))
    const icon = document.createElement('a')
    icon.href = '#'
    icon.className = 'citation cite-icon'
    icon.dataset.doc = cites[0].doc
    icon.dataset.page = String(cites[0].page)
    icon.dataset.cites = JSON.stringify(cites)
    icon.setAttribute('aria-label', cites.map((c) => citeLabel(c)).join('; '))
    // Hidden text for copying; word joiners keep the icon on one line with the word before it and the full stop after.
    const copy = document.createElement('span')
    copy.className = 'cite-copy'
    copy.textContent = original
    icon.append(copy, '\u2060')
    icon.insertAdjacentHTML('beforeend', BOOK_ICON)
    icon.append('\u2060')
    range.deleteContents()
    range.insertNode(icon)
  }
}

/** "book.pdf, p. 41" or "book.pdf, pp. 41–43". */
export function citeLabel(cite: Cite, name = cite.doc): string {
  return `${name}, ${pagesLabel(cite)}`
}

export function pagesLabel(cite: Cite): string {
  return cite.end ? `pp. ${cite.page}–${cite.end}` : `p. ${cite.page}`
}
