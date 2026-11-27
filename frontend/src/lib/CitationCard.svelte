<script lang="ts">
  import type { IndexSection } from './api'
  import type { CardHover } from './cardHover.svelte'
  import { type Cite, pagesLabel } from './markdown'
  import type { Workspace } from './workspace.svelte'

  type Props = {
    workspace: Workspace
    hover: CardHover
    /** What the hovered book icon cites. */
    cites: Cite[]
    /** The topic's PDFs; a citation names one by its file name. */
    docIds: string[]
    /** Each PDF's indexed sections, by its id, once fetched. */
    sections: Record<string, IndexSection[]>
    onopen: (cite: Cite) => void
  }

  let { workspace, hover, cites, docIds, sections, onopen }: Props = $props()

  const docOf = (cite: Cite) => docIds.find((id) => workspace.docs[id]?.name === cite.doc)

  /** The heading the cited page falls under: the last one starting on or before it. */
  function sectionOf(cite: Cite): string | undefined {
    const id = docOf(cite)
    return id ? sections[id]?.findLast((s) => s.start_page <= cite.page)?.title : undefined
  }
</script>

{#if hover.spot}
  <div
    class="citation-card"
    class:below={hover.spot.below}
    role="tooltip"
    style:top="{hover.spot.y}px"
    style:left="{hover.spot.x}px"
    onpointerenter={() => hover.keep()}
    onpointerleave={() => hover.leave()}
  >
    {#each cites as cite, i (i)}
      {@const id = docOf(cite)}
      {@const section = sectionOf(cite)}
      <button type="button" class="cite" onclick={() => onopen(cite)}>
        <span class="cite-name">{id ? workspace.docName(id) : cite.doc}</span>
        <span class="cite-where">{pagesLabel(cite)}{section ? ` · ${section}` : ''}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .citation-card {
    position: fixed;
    z-index: 40;
    box-sizing: border-box;
    width: 13rem;
    padding: 0.25rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: 0 4px 14px rgb(0 0 0 / 0.12);
    /* Centred above the icon; below it when there is no room above. */
    transform: translate(-50%, -100%);
    animation: cite-in 0.12s ease-out;
  }
  .citation-card.below {
    transform: translateX(-50%);
  }
  /* An invisible strip bridges the gap to the icon, so the pointer can cross onto the card. */
  .citation-card::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: 100%;
    height: 0.5rem;
  }
  .citation-card.below::after {
    top: auto;
    bottom: 100%;
  }
  @keyframes cite-in {
    from {
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .citation-card {
      animation: none;
    }
  }
  .cite {
    display: block;
    width: 100%;
    padding: 0.3rem 0.5rem;
    border: none;
    border-radius: calc(var(--radius) - 2px);
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .cite:hover,
  .cite:focus-visible {
    background: var(--hover);
  }
  .cite-name {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    line-height: 1.3;
    overflow-wrap: anywhere;
  }
  .cite-where {
    display: block;
    margin-top: 0.1rem;
    font-size: 0.72rem;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
