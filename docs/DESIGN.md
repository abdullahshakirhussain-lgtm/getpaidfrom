# Get Paid From: design rules

Written 2026-10-26 after the owner said the first two designs "look like AI slop". Every new page is checked against this file before it ships.

## What reads as "AI slop" (researched, 2026-10-26)

Sources: [Fountain Institute: 7 signs a UI has been vibe coded](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui),
[925 Studios: AI slop web design guide](https://www.925studios.co/blog/ai-slop-web-design-guide),
[Noqta: overused AI UI patterns](https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026),
[superdesign: why AI design looks generic](https://www.superdesign.dev/blog/why-ai-design-looks-generic),
[Banani: vibe designing](https://www.banani.co/blog/vibe-designing). These are design blogs, not studies, but they agree on the list.

| Tell | Where our previous design had it |
|---|---|
| Indigo / purple accent (Tailwind's indigo-500 default) | accent `#4338ca`, purple logo square |
| Inter or plain system sans, nothing chosen | `system-ui` only |
| Everything in a rounded card, same radius (16px) everywhere, cards in cards | verdicts, tiles, lines, platform cards |
| Thick coloured border on one side of a rounded card ("the most recognisable signature") | verdict cards |
| Uppercase, letter-spaced eyebrow labels | "CLIENTS PAYING YOU" |
| Pill badges everywhere | status chips, example buttons, country chips |
| Emoji used as icons | flag emoji, ✓ logo |
| Centred hero with one highlighted word in the accent colour | "Get paid from *your country*" |
| Neon-on-dark / glow dark mode as the default look | dark theme |
| Letter monograms instead of real marks | "P", "W", "G" squares |
| Same-sized identical grid cells, no hierarchy | 3-across tile grid |
| Vague or robotic copy ("You can. Easiest: X") | verdict headlines |

## The system

**Idea.** A well-set reference page, like a timetable or a good dictionary entry: black ink on white paper, rules instead of boxes, a margin column for headings. The one flourish is the *blank*: the brand is a sentence, "Get paid from ___", and the country you pick fills the blank, marked like a highlighter on paper.

**Colour.** White `#ffffff` page, ink `#15171c`, grey ink `#5d6370`, hairline `#e2e4e8`. One accent: highlighter yellow `#ffe45c`, used only behind the filled-in blank and the focused search. Links are ink, underlined. Status colours are semantic and only appear on status marks:
works `#17784a`, likely `#17784a` (hollow mark), limited `#a85400`, not confirmed `#6b7180`, not available `#c0352b`.

**Status marks.** A small shape *and* a word, never colour alone: ● Works, ○ Likely, ◐ Limited, ◌ Not confirmed, ✕ Not available. Every mark has a defined meaning (see /about/).

**Type.** Headings and the short answer: Newsreader 600 (serif, editorial). Everything else: Atkinson Hyperlegible Next 400/700, designed for legibility, which suits readers on cheap phones in a second language. Self-hosted (no Google requests). Sentence case everywhere; no letter-spaced capitals.

**Shape.** No cards, no shadows, no gradients. Content is grouped by whitespace and 1px rules. Radius only on the search input (6px). Logos are the companies' real marks in their official colours (owner request, 2026-10-27). Marks whose colour is under 3:1 contrast on white sit on a small ink square; the colour itself is never changed.

**Layout.** Left-aligned. On wide screens each section has its heading in a 168px margin column and content on the right. On phones the heading sits above. Max content width 920px.

**Copy.** Plain sentences a person would say. Short answers 15 words or fewer. No internal labels (fact codes, TRAP, "single source").

**Motion.** None, except the row that a link jumps to gets a brief highlighter fade, so you can see where you landed.

## Page structure

Country page: the sentence "Get paid from **Sri Lanka**" → *The short answer* (clients abroad / selling online, one serif line each) → *Watch out for* (numbered, 3 at most) → *Every option* (services table: logo, status, one-line reason; the row opens to sources) → *Paperwork* (tax ID, registering, VAT, income tax) → *Also good to know* → sources and date.

Home: the sentence with the blank *is* the search box. Below it: example questions as plain links, countries A–Z, services with how many countries each works in.

Service page: "Where PayPal works", countries grouped by status.
