"""
Quizzes: questions the reader works through in the chat, multiple choice or typed short
answers. The answering model writes them; how the reader did goes back into the chat
history, so later answers and quizzes can build on it. At the end Haiku grades the typed
answers and suggests what to review, in one call.
"""

import math
import random
import time
from typing import Any, Literal

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from .usage import UsageLog, call_from_response

# Writes the short recommendation after a quiz: a cheap, quick model is enough.
RECOMMEND_MODEL = "claude-haiku-5-5"

LETTERS = "ABCDEFGH"

# By default at most this share of a quiz's questions are typed answers, so they don't take
# over; the reader can change it in Settings.
MAX_TYPED_SHARE = 0.4

# The card typesets $...$ with KaTeX; Unicode stand-ins like "d²x/dτ²" show as plain text.
MATHS = "Markdown; all maths in LaTeX like $x^\\mu$, never Unicode like x² or x_μ"


class Distractor(BaseModel):
    misconception_rationale: str = Field(
        description="Written first: the specific mistake or misconception that leads to this "
        "answer, in one sentence the reader is shown after answering, e.g. 'Uses the diameter "
        "where the formula needs the radius.' or 'Confuses negative reinforcement with "
        "punishment.' " + MATHS
    )
    text: str = Field(
        description="The wrong answer that mistake produces, parallel in form, length and "
        "vocabulary to the right answer. " + MATHS
    )


class WrittenQuestion(BaseModel):
    """A question as the model writes it: the right answer, then the mistakes that tempt."""

    kind: Literal["choice", "typed"] = Field(
        default="choice",
        description="choice: multiple choice; typed: they type a short answer (a word, a "
        "number, an expression or a sentence or two), only where an answer can be checked "
        "against a clear model answer. At most 2 in 5 questions are typed.",
    )
    level: Literal["application", "analysis"] = Field(
        description="application: a short scenario or problem where they must recognise and "
        "apply the right idea; analysis: a flawed application or argument where they must find "
        "exactly what goes wrong"
    )
    question: str = Field(
        description="The stem: a complete, self-contained question that can be answered before "
        "reading the options. " + MATHS
    )
    answer: str = Field(
        description="The right answer, written like the wrong ones; for a typed question, "
        "the model answer, as short as a full answer can be. " + MATHS
    )
    distractors: list[Distractor] = Field(
        default=[], description="Exactly 3 wrong answers; none for a typed question"
    )
    key_points: list[str] = Field(
        default=[],
        description="Typed questions only: the 1 to 3 things an answer must get right to "
        "count, for grading, e.g. 'the sign of the result' or 'names friction as the "
        "force'. " + MATHS,
    )
    explanation: str = Field(
        description="Why the right answer is right, in a sentence or two. Cite a page only to "
        "point at something to look at, not as a source. " + MATHS
    )


class WrittenQuiz(BaseModel):
    title: str = Field(
        description="A few words naming what the quiz is about, in plain text without maths"
    )
    questions: list[WrittenQuestion]


class QuizQuestion(BaseModel):
    """
    A question as the reader sees it: multiple choice with the right answer somewhere among
    the choices, or typed, with a model answer to compare with.
    """

    kind: Literal["choice", "typed"] = "choice"
    question: str
    choices: list[str] = []
    answer: int = Field(
        default=-1, description="Index of the right choice in `choices`, from 0; -1 for typed"
    )
    explanation: str
    misconceptions: list[str | None] = Field(
        default=[], description="For each choice, the mistake behind it; None for the right one"
    )
    model_answer: str | None = Field(default=None, description="Typed questions: the answer")
    key_points: list[str] = Field(default=[], description="Typed questions: what must be right")


class Grade(BaseModel):
    """How a typed answer was judged."""

    verdict: Literal["right", "partly", "wrong"]
    feedback: str = Field(
        description="One short sentence to them: what was missing or wrong, or empty when right"
    )


class Quiz(BaseModel):
    title: str
    questions: list[QuizQuestion]


class QuizRecord(Quiz):
    """A quiz as the chat keeps it: with the reader's answers and the recommendation."""

    picked: list[int | None] = Field(
        default=[], description="The choice the reader picked for each question, if any"
    )
    typed: list[str | None] = Field(
        default=[],
        description="For each question, what the reader typed: their answer to a typed "
        "question, or a guess before seeing a multiple-choice question's options",
    )
    grades: list[Grade | None] = Field(
        default=[],
        description="For each question, how what they typed was graded. Only typed questions "
        "are graded for now; guesses could be, later, for bonus points.",
    )
    recommendation: str | None = None

    def typed_answer(self, n: int) -> str | None:
        text = self.typed[n] if n < len(self.typed) else None
        return text.strip() if text and text.strip() else None

    def grade(self, n: int) -> Grade | None:
        return self.grades[n] if n < len(self.grades) else None

    def answered(self, n: int) -> bool:
        q = self.questions[n]
        if q.kind == "typed":
            return self.typed_answer(n) is not None
        return n < len(self.picked) and self.picked[n] is not None

    def right(self, n: int) -> bool:
        q = self.questions[n]
        if q.kind == "typed":
            grade = self.grade(n)
            return grade is not None and grade.verdict == "right"
        return n < len(self.picked) and self.picked[n] == q.answer


def arrange(
    written: WrittenQuiz,
    rng: random.Random | None = None,
    typed_share: float = MAX_TYPED_SHARE,
) -> Quiz:
    """
    The quiz as the reader sees it: each right answer put at a random place among its wrong
    ones, so where it is gives nothing away. Questions without a right answer and at least one
    wrong one are dropped.
    """
    rng = rng or random.Random()
    questions = []
    for q in capped(written.questions, typed_share):
        if q.kind == "typed":
            if not q.answer.strip():
                continue
            questions.append(
                QuizQuestion(
                    kind="typed",
                    question=q.question,
                    explanation=q.explanation,
                    model_answer=q.answer,
                    key_points=[p for p in q.key_points if p.strip()],
                )
            )
            continue
        wrong = [d for d in q.distractors if d.text.strip()][: len(LETTERS) - 1]
        if not q.answer.strip() or not wrong:
            continue
        # (text, the mistake behind it, whether it is the right one)
        options: list[tuple[str, str | None, bool]] = [(q.answer, None, True)]
        options += [(d.text, d.misconception_rationale.strip() or None, False) for d in wrong]
        rng.shuffle(options)
        questions.append(
            QuizQuestion(
                question=q.question,
                choices=[text for text, _, _ in options],
                answer=next(i for i, (_, _, right) in enumerate(options) if right),
                explanation=q.explanation,
                misconceptions=[why for _, why, _ in options],
            )
        )
    return Quiz(title=written.title, questions=questions)


def capped(written: list[WrittenQuestion], share: float = MAX_TYPED_SHARE) -> list[WrittenQuestion]:
    """
    The questions with at most `share` of them typed. A typed question past the cap
    becomes multiple choice if the model gave it wrong answers too, else it is dropped; the
    last ones go first.
    """
    questions = [q.model_copy() for q in written]

    def too_many() -> bool:
        typed = sum(q.kind == "typed" for q in questions)
        return typed > 0 and typed > math.floor(share * len(questions) + 1e-9)

    while too_many():
        n = max(i for i, q in enumerate(questions) if q.kind == "typed")
        if any(d.text.strip() for d in questions[n].distractors):
            questions[n].kind = "choice"
        else:
            del questions[n]
    return questions


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """A JSON schema with its $defs put in place, for a tool's input."""
    defs = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


QUIZ_TOOL: dict[str, Any] = {
    "name": "make_quiz",
    "description": (
        "Show them a quiz to work through (multiple choice, some typed answers), written by "
        "the quiz rules in your "
        "instructions. Use it when they ask to be quizzed or tested."
    ),
    "input_schema": inline_refs(WrittenQuiz.model_json_schema()),
}


def misconception(q: QuizQuestion, choice: int) -> str | None:
    """The mistake behind a wrong choice, if the quiz says."""
    return q.misconceptions[choice] if 0 <= choice < len(q.misconceptions) else None


def quiz_text(quiz: Quiz) -> str:
    """A quiz as the model wrote it, for the chat history."""
    lines = [f"[Quiz] {quiz.title} (shown to them as questions to work through)"]
    for n, q in enumerate(quiz.questions, 1):
        if q.kind == "typed":
            lines.append(f"{n}. (typed answer) {q.question}")
            lines.append(f"   Model answer: {q.model_answer}. {q.explanation}")
            if q.key_points:
                lines.append(f"   Must get right: {'; '.join(q.key_points)}")
            continue
        lines.append(f"{n}. {q.question}")
        for i, choice in enumerate(q.choices):
            why = misconception(q, i) if i != q.answer else None
            lines.append(f"   {LETTERS[i]}) {choice}" + (f" (the mistake: {why})" if why else ""))
        lines.append(f"   Right answer: {LETTERS[q.answer]}. {q.explanation}")
    return "\n".join(lines)


def score(quiz: QuizRecord) -> tuple[int, int]:
    """How many questions the reader got right, and how many they answered."""
    answered = [n for n in range(len(quiz.questions)) if quiz.answered(n)]
    return sum(quiz.right(n) for n in answered), len(answered)


def typed_line(quiz: QuizRecord, n: int) -> str:
    """How a typed answer went, for the results."""
    wrote = quiz.typed_answer(n)
    grade = quiz.grade(n)
    if grade is None:
        return f"They wrote: {wrote} (not graded)."
    verdict = {"right": "Right", "partly": "Partly right", "wrong": "Wrong"}[grade.verdict]
    feedback = f" {grade.feedback.strip()}" if grade.feedback.strip() else ""
    return f"{verdict}: they wrote {wrote}.{feedback}"


def results_text(quiz: QuizRecord) -> str | None:
    """How the reader did, question by question, or None before they answered any."""
    right, answered = score(quiz)
    if not answered:
        return None
    total = len(quiz.questions)
    if answered < total:
        lines = [f"[Quiz results] They answered {answered} of {total} questions, {right} right."]
    else:
        lines = [f"[Quiz results] They got {right} of {total} right."]
    for n, q in enumerate(quiz.questions):
        picked = quiz.picked[n] if n < len(quiz.picked) else None
        guess = quiz.typed_answer(n) if q.kind == "choice" else None
        guessed = f" Before seeing the options they guessed: {guess}." if guess else ""
        if not quiz.answered(n):
            line = "Not answered."
        elif q.kind == "typed":
            line = typed_line(quiz, n)
        elif picked == q.answer:
            line = "Right." + guessed
        else:
            assert picked is not None
            chose = q.choices[picked] if 0 <= picked < len(q.choices) else "?"
            why = misconception(q, picked)
            line = (
                f"Wrong: they chose {LETTERS[picked]}) {chose}"
                + (f" (the mistake: {why})" if why else "")
                + f"; the answer is {LETTERS[q.answer]}) {q.choices[q.answer]}."
                + guessed
            )
        lines.append(f"{n + 1}. {line}")
    if quiz.recommendation:
        lines.append(f"They were advised: {quiz.recommendation}")
    return "\n".join(lines)


RECOMMEND_PROMPT = """\
Someone studying "{topic}" just took a quiz. {about}

The quiz, with the right answers and why:
{quiz}

{results}
{grading}
Write them a short recommendation, at most two sentences, on what to review: name the idea \
behind what they got wrong and where to read about it again, e.g. "Try reading the definition \
of the derivative again (book.pdf, p. 41)." Cite pages only as the explanations above give \
them, in the form (file name, p. N). Write any maths in LaTeX between dollar signs, as the quiz \
does, e.g. $f'(x) = 2x$, never as bare LaTeX commands or plain-text formulas: the app renders \
it. Speak to them directly, without a preamble. Leave it empty if they got everything right."""

GRADING_PROMPT = """
First grade their typed answers, in this order: {numbers}. Judge each against the model answer \
and what it must get right, not its wording: right if it gets all of that right (an equivalent \
form, notation or phrasing counts), partly if it gets some, wrong otherwise. For each, one \
short sentence to them on what was missing or wrong, empty when right. Be fair but not \
generous: a vague answer that would fit many questions is not right. Then write the \
recommendation with the grades in mind.
"""


class Review(BaseModel):
    grades: list[Grade] = Field(default=[], description="One per typed answer, in order")
    recommendation: str = ""


class ReviewResult(BaseModel):
    """Grades for the typed answers (by question, None for the rest) and what to review."""

    grades: list[Grade | None] = []
    recommendation: str | None = None


async def review(
    client: AsyncAnthropic,
    topic: str,
    about: str,
    quiz: QuizRecord,
    usage: UsageLog | None = None,
) -> ReviewResult:
    """
    After a quiz: grades for its typed answers and what to review, in one Haiku call; nothing
    when there is nothing to grade and every choice was right.
    """
    to_grade = [
        n
        for n, q in enumerate(quiz.questions)
        if q.kind == "typed" and quiz.typed_answer(n) and quiz.grade(n) is None
    ]
    right, answered = score(quiz)
    if not answered or (not to_grade and right == len(quiz.questions)):
        return ReviewResult(grades=list(quiz.grades))
    grading = (
        GRADING_PROMPT.format(numbers=", ".join(str(n + 1) for n in to_grade)) if to_grade else ""
    )
    prompt = RECOMMEND_PROMPT.format(
        topic=topic, about=about, quiz=quiz_text(quiz), results=results_text(quiz), grading=grading
    )
    began = time.monotonic()
    response: Any = await client.messages.parse(
        model=RECOMMEND_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
        output_format=Review,
        output_config={"effort": "low"},
    )
    if usage:
        usage.record(
            call_from_response(
                "quiz_recommendation", RECOMMEND_MODEL, response, time.monotonic() - began
            )
        )
    parsed: Review | None = response.parsed_output
    grades: list[Grade | None] = [quiz.grade(n) for n in range(len(quiz.questions))]
    for n, grade in zip(to_grade, parsed.grades if parsed else [], strict=False):
        grades[n] = grade
    text = parsed.recommendation.strip() if parsed else ""
    graded = quiz.model_copy(update={"grades": grades})
    everything_right = score(graded)[0] == len(quiz.questions)
    return ReviewResult(
        grades=grades, recommendation=text if text and not everything_right else None
    )
