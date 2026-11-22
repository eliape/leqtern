/**
 * Steps the backend names while they run ("Writing a quiz"), with the words to show once
 * they are done. Lookups arrive already done ("Searched for …") and are shown as they are.
 */
const PAST: Record<string, string> = {
  'Writing a quiz': 'Wrote a quiz',
  'Checking for duplicates': 'Checked for duplicates',
}

/** Whether a step is one that runs a while, so it reads "…ing…" until it ends. */
export function ongoing(text: string): boolean {
  return text in PAST
}

/** A step's label: "Writing a quiz…" while it runs, "Wrote a quiz" once it is done. */
export function stepLabel(text: string, running: boolean): string {
  const past = PAST[text]
  if (!past) return text
  return running ? `${text}…` : past
}
