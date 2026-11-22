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

const TYPED_KEY = 'leqtern.typedQuizShare'

/** By default at most this share of a quiz's questions are typed answers, as the backend has it. */
export const DEFAULT_TYPED_SHARE = 0.4

function savedShare(): number {
  try {
    const share = Number(localStorage.getItem(TYPED_KEY) ?? DEFAULT_TYPED_SHARE)
    return Number.isFinite(share) && share >= 0 && share <= 1 ? share : DEFAULT_TYPED_SHARE
  } catch {
    return DEFAULT_TYPED_SHARE
  }
}

/** The most of a quiz's questions that may be typed answers, from 0 to 1. A setting. */
export const quizTyped = $state({ share: savedShare() })

export function setTypedQuizShare(share: number) {
  quizTyped.share = Math.min(1, Math.max(0, Math.round(share * 10) / 10))
  try {
    localStorage.setItem(TYPED_KEY, String(quizTyped.share))
  } catch {
    // Not remembered when storage is unavailable.
  }
}
