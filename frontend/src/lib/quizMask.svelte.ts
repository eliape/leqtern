// Hiding a quiz question's choices until the reader clicks them, so they think of an answer
// before seeing the options. A setting, on unless turned off.

import type { QuizQuestion } from './api'

const KEY = 'leqtern.hideQuizChoices'

function saved(): boolean {
  try {
    return localStorage.getItem(KEY) !== 'false'
  } catch {
    return true
  }
}

/** Shared by Settings and every quiz card, so a change shows at once. */
export const quizMask = $state({ hideChoices: saved() })

export function setHideQuizChoices(on: boolean) {
  quizMask.hideChoices = on
  try {
    localStorage.setItem(KEY, String(on))
  } catch {
    // Storage can be unavailable (private windows); the choice just isn't remembered.
  }
}

/**
 * Whether this kind of question gets the mask. Only multiple choice does: a true/false
 * question (not written yet) has nothing to give away in its two options.
 */
export function masksChoices(question: QuizQuestion): boolean {
  return (question.kind ?? 'choice') === 'choice'
}
