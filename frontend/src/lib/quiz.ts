// Reading a quiz's state: which questions are answered and which are right, for multiple-choice
// and typed questions alike. Older quizzes have no `typed` or `grades`.

import type { QuizRecord } from './api'

export const isTyped = (quiz: QuizRecord, n: number) => quiz.questions[n]?.kind === 'typed'

/** What the reader typed for a question (a typed answer, or a guess), if anything. */
export function typedText(quiz: QuizRecord, n: number): string | null {
  const text = quiz.typed?.[n]
  return text && text.trim() ? text.trim() : null
}

export function isAnswered(quiz: QuizRecord, n: number): boolean {
  return isTyped(quiz, n) ? typedText(quiz, n) !== null : (quiz.picked[n] ?? null) !== null
}

/** Right: the right choice, or a typed answer graded right. A typed answer not graded yet is not. */
export function isRight(quiz: QuizRecord, n: number): boolean {
  if (isTyped(quiz, n)) return quiz.grades?.[n]?.verdict === 'right'
  return quiz.picked[n] === quiz.questions[n]?.answer
}

/** The first question not answered yet; the number of questions when all are. */
export function firstOpen(quiz: QuizRecord): number {
  const i = quiz.questions.findIndex((_, n) => !isAnswered(quiz, n))
  return i === -1 ? quiz.questions.length : i
}

export const rightCount = (quiz: QuizRecord) => quiz.questions.filter((_, n) => isRight(quiz, n)).length

/** Typed answers that still need a grade. */
export const ungraded = (quiz: QuizRecord) =>
  quiz.questions.some((_, n) => isTyped(quiz, n) && typedText(quiz, n) !== null && !quiz.grades?.[n])
