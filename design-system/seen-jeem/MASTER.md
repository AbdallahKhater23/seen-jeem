# Seen Jeem visual system

Direction: a warm, playful Arabic trivia experience inspired by the public
`https://seenjeemkw.com/` reference, inspected through rendered screenshots and its
public CSS. UI/UX Pro Max's Vibrant & Block-based recommendation fits this product;
its generic blue palette and testimonial-page layout were replaced by the actual
reference's orange/red language and this app's game workflow.

## Tokens

- Canvas: warm cream `#FFFAF5`; cards: white; lines: `#EDDFD5`.
- Primary orange: `#F57928`; action red: `#A72D2A`.
- Main text: `#382720`; secondary text: warm stone.
- Arabic typography: Cairo, with system fallbacks and native RTL layout.
- Corners: 12–14 px controls, 18–28 px cards; restrained warm shadows.
- Team identities use darker teal/pink/green/gold/violet/orange for readable scores.
- Category illustrations use individual pastel backgrounds and vector symbols.

## Components and screen rules

- BrandMark: original letter symbol and Arabic wordmark, used in account navigation.
- Account: two-column story/form on desktop; concise story and stacked form on mobile.
- Setup: welcome panel → category search/selection → team setup and coin → powers.
- Category cards: explicit selected border/checkmark; six selections maximum.
- Board: six category panels, each with six large 200/400/600 point buttons.
- Arena: large centered question, persistent desktop controls, scrollable powers rail.
- Results: warm winner treatment, readable team statistics, explicit replay confirmation.
- Admin: the same fonts, light surfaces, borders, and semantic accent colors.

## Interaction and access

Maintain visible keyboard focus, associated form labels, at least 44 px button targets,
native password manager/paste support, text alongside status colors, and no horizontal
scroll at mobile/tablet/desktop widths. Honor reduced-motion preferences. Game changes
mount immediately; no exit animation may delay or hide a returning board. Keep points,
history, and authentication on the existing server contracts.

`src/brand.css` contains the shared theme; screen structures use named classes for
account, setup, board, and question layouts. Gameplay/state logic remains in the
existing store and backend. No remote image assets are required for the new category art.
