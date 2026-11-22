<script lang="ts">
  import { type CitableDocs, renderMarkdown } from './markdown'
  import type { QuizQuestion } from './api'
  import type { Quiz } from './workspace.svelte'
  import { masksChoices, quizMask } from './quizMask.svelte'
  import { firstOpen, isAnswered, isRight, isTyped, rightCount, typedText } from './quiz'

  type Props = {
    quiz: Quiz
    /** The reader picked a choice for a question. Each question is answered once. */
    onpick: (question: number, choice: number) => void
    /** The reader typed an answer to a typed question, or a guess before uncovering the choices. */
    ontype?: (question: number, text: string) => void
    /** The reader asked for the next hint on a question. */
    onhint?: (question: number) => void
    /** The question on show changed (the number of questions for the results). */
    onopen?: (question: number) => void
    /** What the quiz's citations can point at, as in answers. */
    docs?: CitableDocs
  }

  let { quiz, onpick, ontype, onhint, onopen, docs }: Props = $props()

  const LETTERS = 'ABCDEFGH'
  const total = $derived(quiz.questions.length)

  // Which question is showing; `total` shows the results. Starts at the first one not yet
  // answered, so a quiz left halfway (or reloaded) carries on where it was.
  const start = () => firstOpen(quiz)
  let step = $state(start())
  $effect(() => onopen?.(step))

  let right = $derived(rightCount(quiz))
  let question = $derived(quiz.questions[step])
  let picked = $derived(quiz.picked[step] ?? null)
  let typed = $derived(isTyped(quiz, step))
  let answered = $derived(!!question && isAnswered(quiz, step))
  // What the reader is typing: a typed answer, or a guess on the mask. Cleared for each question.
  let draft = $state('')
  let draftStep = $state(-1)
  $effect(() => {
    if (draftStep !== step) ((draft = ''), (draftStep = step))
  })

  /** Uncover the choices, keeping a guess if one was typed. */
  function reveal() {
    if (draft.trim()) ontype?.(step, draft)
    revealedStep = step
  }

  function submitTyped() {
    if (draft.trim()) ontype?.(step, draft)
  }

  /** Enter sends, Shift+Enter starts a new line. */
  function onTypedKey(event: KeyboardEvent, send: () => void) {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault()
      send()
    }
  }

  let hints = $derived(question?.hints ?? [])
  let hintsSeen = $derived(Math.min(quiz.hints_used?.[step] ?? 0, hints.length))
  // Which revealed hint is on top of the deck: the newest, until the reader clicks to cycle.
  // Reset per question and whenever another hint is revealed.
  let hintAt = $state<{ step: number; seen: number; at: number } | null>(null)
  let shownHint = $derived(hintAt?.step === step && hintAt.seen === hintsSeen ? hintAt.at : hintsSeen - 1)

  /** Put the next revealed hint on top. */
  function cycleHint() {
    if (hintsSeen > 1) hintAt = { step, seen: hintsSeen, at: (shownHint + 1) % hintsSeen }
  }

  const VERDICTS = { right: 'Right', partly: 'Partly right', wrong: 'Not right' } as const

  // The question whose choices the reader uncovered; moving on hides the next one's again.
  let revealedStep = $state<number | null>(null)
  let masked = $derived(
    quizMask.hideChoices && !!question && masksChoices(question) && picked === null && revealedStep !== step,
  )

  /** Markdown on one line: choices have no paragraphs of their own. */
  const inline = (text: string) => renderMarkdown(text, docs).replace(/^<p>|<\/p>\s*$/g, '')

  // The results ring: a circle whose coloured part is the share of right answers.
  const RADIUS = 15.5
  // Whether the ring fills up from empty: when the reader goes on to the results, not when a
  // finished quiz is shown again (after a reload or a topic switch).
  let filling = $state(false)
  // Whether the results show each question again with its choices and explanation.
  let details = $state(false)
</script>

{#snippet choices(q: QuizQuestion, chosen: number | null, live: boolean)}
  <div class="choices" role="group" aria-label="Choices">
    {#each q.choices as choice, i (i)}
      <button
        type="button"
        class="choice"
        class:right={chosen !== null && i === q.answer}
        class:wrong={chosen === i && i !== q.answer}
        aria-pressed={chosen === i}
        disabled={!live || chosen !== null}
        onclick={() => onpick(step, i)}
      >
        <span class="letter" aria-hidden="true">{LETTERS[i]}</span>
        <span class="body">
          <span class="markdown">{@html inline(choice)}</span>
          <!-- Once answered, each wrong choice says what mistake leads to it. -->
          {#if chosen !== null && i !== q.answer && q.misconceptions?.[i]}
            <span class="why markdown">{@html inline(q.misconceptions[i]!)}</span>
          {/if}
        </span>
      </button>
    {/each}
  </div>
{/snippet}

<div class="quiz" role="group" aria-label={`Quiz: ${quiz.title}`}>
  <div class="head">
    <span class="title">{quiz.title}</span>
    <span class="head-end">
      {#if question && hints.length && onhint}
        <button
          type="button"
          class="hint-button"
          title={hintsSeen >= hints.length ? 'No more hints' : hintsSeen ? 'Show another hint' : 'Show a hint'}
          aria-label={hintsSeen >= hints.length ? 'No more hints' : hintsSeen ? 'Show another hint' : 'Show a hint'}
          disabled={answered || hintsSeen >= hints.length}
          onclick={() => onhint(step)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"
            ><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z" /></svg
          >
        </button>
      {/if}
      <span class="progress">{step < total ? `Question ${step + 1} of ${total}` : 'Results'}</span>
    </span>
  </div>

  {#if question}
    <div class="question markdown">{@html renderMarkdown(question.question, docs)}</div>
    {#if hintsSeen}
      <!-- The revealed hints as a deck: the top card shows, the others peek out below it. -->
      <div class="hints" style={`--behind: ${hintsSeen - 1}`} aria-live="polite">
        {#if hintsSeen > 1}
          <button
            type="button"
            class="hint card"
            aria-label={`Hint ${shownHint + 1} of ${hintsSeen}, click for the next`}
            onclick={cycleHint}
          >
            <span class="hint-number">Hint {shownHint + 1} of {hintsSeen}</span>
            <span class="markdown">{@html inline(hints[shownHint])}</span>
          </button>
        {:else}
          <div class="hint card" role="note" aria-label="Hint">
            <span class="markdown">{@html inline(hints[0])}</span>
          </div>
        {/if}
      </div>
    {/if}
    {#if typed}
      {#if !answered}
        <div class="typed">
          <textarea
            class="answer-box"
            rows="2"
            placeholder="Type your answer"
            aria-label="Your answer"
            bind:value={draft}
            onkeydown={(e) => onTypedKey(e, submitTyped)}
          ></textarea>
          <button type="button" class="next" disabled={!draft.trim()} onclick={submitTyped}>Submit</button>
        </div>
      {:else}
        <div class="feedback" role="status">
          <p class="wrote"><span class="label">You wrote</span> {typedText(quiz, step)}</p>
          <div class="model-answer">
            <span class="label">Model answer</span>
            <div class="markdown">{@html renderMarkdown(question.model_answer ?? '', docs)}</div>
          </div>
          <div class="markdown">{@html renderMarkdown(question.explanation, docs)}</div>
          <p class="muted-note">Compare with the model answer; it is graded with the rest at the end.</p>
          <button type="button" class="next" onclick={() => ((step += 1), (filling = step === total))}>
            {step + 1 < total ? 'Next question' : 'See results'}
          </button>
        </div>
      {/if}
    {:else}
      <div class="choices-wrap">
        <div class:covered={masked} inert={masked}>{@render choices(question, picked, true)}</div>
        {#if masked}
          <!-- Clicking anywhere on the mask but the guess box uncovers the choices. -->
          <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
          <div class="mask" onclick={(e) => (e.target as HTMLElement).closest('input') || reveal()}>
            <button type="button" class="reveal" onclick={(e) => (e.stopPropagation(), reveal())}>Click to reveal</button>
            {#if ontype}
              <input
                class="guess"
                type="text"
                placeholder="Or type a guess first"
                aria-label="Your guess"
                bind:value={draft}
                onkeydown={(e) => onTypedKey(e, reveal)}
              />
            {/if}
          </div>
        {/if}
      </div>
      {#if picked !== null}
        <div class="feedback" role="status">
          <p class="verdict" class:right={picked === question.answer}>
            {picked === question.answer ? 'Right.' : `Not quite: the answer is ${LETTERS[question.answer]}.`}
          </p>
          {#if typedText(quiz, step)}
            <p class="wrote"><span class="label">Your guess</span> {typedText(quiz, step)}</p>
          {/if}
          <div class="markdown">{@html renderMarkdown(question.explanation, docs)}</div>
          <button type="button" class="next" onclick={() => ((step += 1), (filling = step === total))}>
            {step + 1 < total ? 'Next question' : 'See results'}
          </button>
        </div>
      {/if}
    {/if}
  {:else}
    <div class="score" role="img" aria-label={`You got ${right} of ${total} right`}>
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle class="track" cx="18" cy="18" r={RADIUS} />
        {#if right > 0}
          <circle
            class="done"
            class:filling
            cx="18"
            cy="18"
            r={RADIUS}
            pathLength="100"
            stroke-dasharray={`${(100 * right) / total} 100`}
          />
        {/if}
      </svg>
      <span class="fraction" aria-hidden="true">{right}/{total}</span>
    </div>
    {#if right === total}
      <p class="advice">Every answer right.</p>
    {:else if quiz.recommendation}
      <div class="advice">
        <span class="label">What to review</span>
        <div class="markdown">{@html renderMarkdown(quiz.recommendation, docs)}</div>
      </div>
    {:else if quiz.reviewing === 'writing'}
      <p class="advice muted">
        {quiz.questions.some((_, i) => isTyped(quiz, i)) ? 'Grading your answers…' : 'Writing a note on what to review…'}
      </p>
    {:else if quiz.reviewing === 'failed'}
      <p class="advice muted">
        {quiz.questions.some((_, i) => isTyped(quiz, i) && !quiz.grades?.[i])
          ? 'Could not grade your answers.'
          : 'Could not write a note on what to review.'}
      </p>
    {/if}
    <button type="button" class="details-toggle" aria-expanded={details} onclick={() => (details = !details)}>
      {details ? 'Hide details' : 'Details'}
    </button>
    {#if details}
      <ol class="details">
        {#each quiz.questions as q, i (i)}
          {@const choice = quiz.picked[i] ?? null}
          {@const ok = isRight(quiz, i)}
          {@const grade = quiz.grades?.[i] ?? null}
          <li>
            <div class="question markdown">
              <span class="mark" class:right={ok} class:partly={grade?.verdict === 'partly'} aria-label={ok ? 'Right' : grade?.verdict === 'partly' ? 'Partly right' : 'Wrong'}
                >{ok ? '✓' : grade?.verdict === 'partly' ? '½' : '✗'}</span
              >
              {@html renderMarkdown(q.question, docs)}
            </div>
            {#if quiz.hints_used?.[i]}
              <p class="muted-note">Used {quiz.hints_used[i] === 1 ? 'a hint' : `${quiz.hints_used[i]} hints`}</p>
            {/if}
            {#if isTyped(quiz, i)}
              <p class="wrote"><span class="label">You wrote</span> {typedText(quiz, i) ?? '–'}</p>
              {#if grade}
                <p class="grade" class:right={ok} class:partly={grade.verdict === 'partly'}>
                  {VERDICTS[grade.verdict]}.{grade.feedback ? ` ${grade.feedback}` : ''}
                </p>
              {:else if quiz.reviewing === 'writing'}
                <p class="muted-note">Grading…</p>
              {/if}
              <div class="model-answer">
                <span class="label">Model answer</span>
                <div class="markdown">{@html renderMarkdown(q.model_answer ?? '', docs)}</div>
              </div>
            {:else}
              {@render choices(q, choice, false)}
              {#if typedText(quiz, i)}
                <p class="wrote"><span class="label">Your guess</span> {typedText(quiz, i)}</p>
              {/if}
            {/if}
            <div class="markdown explanation">{@html renderMarkdown(q.explanation, docs)}</div>
          </li>
        {/each}
      </ol>
    {/if}
  {/if}
</div>

<style>
  .quiz {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
  }
  .title {
    font-weight: 600;
  }
  .head-end {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-shrink: 0;
  }
  .hint-button {
    display: inline-flex;
    align-items: center;
    gap: 0.15rem;
    padding: 0.1rem 0.3rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: var(--muted);
    font: inherit;
    font-size: 0.75rem;
    cursor: pointer;
  }
  .hint-button:hover:not(:disabled) {
    background: var(--hover);
    color: inherit;
  }
  .hint-button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .hint-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .hint-button svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .hints {
    /* Room for the cards behind the top one. */
    margin-bottom: calc(var(--behind) * 0.35rem);
  }
  .hint {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    width: 100%;
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    font-size: 0.9em;
    text-align: left;
    /* The cards behind, as edges peeking out below. */
    box-shadow:
      0 calc(min(var(--behind), 1) * 0.4rem) 0 calc(min(var(--behind), 1) * -0.3rem)
        color-mix(in srgb, var(--muted) 10%, var(--surface)),
      0 calc(min(var(--behind), 1) * 0.4rem) 0 calc(min(var(--behind), 1) * -0.24rem)
        var(--border);
  }
  button.hint {
    cursor: pointer;
  }
  button.hint:hover {
    background: var(--hover);
  }
  button.hint:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .hint-number {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--muted);
  }
  .progress {
    flex-shrink: 0;
    color: var(--muted);
    font-size: 0.75rem;
  }

  .markdown :global(p) {
    margin: 0 0 0.4rem;
  }
  .markdown :global(p:last-child) {
    margin-bottom: 0;
  }

  .choices {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  /* Rows like the chat's menus: a frame, a shade on hover, green or red once answered. */
  .choice {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.4rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .choice:hover:not(:disabled) {
    background: var(--hover);
  }
  .choice:focus-visible,
  .next:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .choice:disabled {
    cursor: default;
  }
  .choice:disabled:not(.right):not(.wrong) {
    color: var(--muted);
  }
  .choice.right {
    border-color: var(--right);
    background: color-mix(in srgb, var(--right) 10%, var(--surface));
  }
  .choice.wrong {
    border-color: var(--danger);
    background: color-mix(in srgb, var(--danger) 10%, var(--surface));
  }
  /* A frosted box over exactly the choices, until the reader clicks it. */
  .choices-wrap {
    position: relative;
  }
  .mask {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: color-mix(in srgb, var(--surface) 55%, transparent);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    color: var(--muted);
    font: inherit;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
  }
  .mask:hover {
    color: inherit;
    background: color-mix(in srgb, var(--surface) 45%, transparent);
  }
  .reveal {
    padding: 0.2rem 0.6rem;
    border: none;
    border-radius: var(--radius);
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .reveal:focus-visible,
  .guess:focus-visible,
  .answer-box:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .guess,
  .answer-box {
    box-sizing: border-box;
    padding: 0.35rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    font-weight: 400;
    font-size: 0.9rem;
  }
  .guess {
    width: min(18rem, 90%);
    cursor: text;
  }
  .typed {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .answer-box {
    width: 100%;
    resize: vertical;
  }
  .next:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .wrote,
  .grade {
    margin: 0;
  }
  .label {
    margin-right: 0.35rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--muted);
  }
  .model-answer {
    padding: 0.4rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }
  .model-answer .label {
    display: block;
    margin-bottom: 0.1rem;
  }
  .grade {
    font-weight: 600;
    color: var(--danger);
  }
  .grade.right {
    color: var(--right);
  }
  .grade.partly,
  .mark.partly {
    color: var(--partly);
  }
  .muted-note {
    margin: 0;
    font-size: 0.85em;
    color: var(--muted);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .why {
    font-size: 0.85em;
    color: var(--muted);
  }
  .choice.wrong .why {
    color: inherit;
  }
  .letter {
    flex-shrink: 0;
    font-weight: 600;
    color: var(--muted);
  }

  .feedback {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .verdict {
    margin: 0;
    font-weight: 600;
    color: var(--danger);
  }
  .verdict.right {
    color: var(--right);
  }
  .next {
    align-self: flex-start;
    padding: 0.3rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }
  .next:hover:not(:disabled) {
    background: var(--hover);
  }

  .score {
    position: relative;
    align-self: center;
    width: 5.5rem;
    height: 5.5rem;
    margin: 0.25rem 0;
  }
  .score svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  .score circle {
    fill: none;
    stroke-width: 3.5;
  }
  .score .track {
    stroke: var(--border);
  }
  .score .done {
    stroke: var(--right);
    stroke-linecap: round;
  }
  .score .done.filling {
    animation: fill 0.9s 0.15s cubic-bezier(0.33, 1, 0.68, 1) backwards;
  }
  @keyframes fill {
    from {
      stroke-dasharray: 0 100;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .score .done.filling {
      animation: none;
    }
  }
  .fraction {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font-size: 1.25rem;
    font-weight: 600;
  }

  .details-toggle {
    align-self: flex-start;
    padding: 0.2rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: inherit;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .details-toggle:hover {
    background: var(--hover);
  }
  .details-toggle:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .details {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .details li {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .mark {
    float: left;
    width: 1.1rem;
    font-weight: 700;
    color: var(--danger);
  }
  .mark.right {
    color: var(--right);
  }
  .explanation {
    color: var(--muted);
    font-size: 0.9em;
  }

  .advice {
    margin: 0;
    padding: 0.5rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
  }
  .advice.muted {
    color: var(--muted);
  }
  .advice .label {
    display: block;
    margin-bottom: 0.15rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--muted);
  }
</style>
