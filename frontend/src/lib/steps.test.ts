import { describe, expect, it } from 'vitest'
import { ongoing, stepLabel } from './steps'

describe('stepLabel', () => {
  it('reads -ing with an ellipsis while running and past tense once done', () => {
    expect(stepLabel('Writing a quiz', true)).toBe('Writing a quiz…')
    expect(stepLabel('Writing a quiz', false)).toBe('Wrote a quiz')
    expect(stepLabel('Checking for duplicates', false)).toBe('Checked for duplicates')
  })

  it('leaves lookups, already in past tense, as they are', () => {
    expect(stepLabel('Searched for “newton”', true)).toBe('Searched for “newton”')
    expect(ongoing('Searched for “newton”')).toBe(false)
    expect(ongoing('Writing a quiz')).toBe(true)
  })
})
