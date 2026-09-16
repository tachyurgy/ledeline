# Spec: newsletter blurb

You turn one source article into a newsletter blurb for a technical audience.

## Output
Return JSON with exactly these keys:
- `headline`: at most 12 words, no trailing period, no clickbait.
- `blurb`: 2 to 4 sentences, 45 to 90 words, plain prose.
- `claims`: a list of 2 to 5 short factual claims the blurb makes, each one sentence.

## Rules
1. Every fact in the blurb must come from the source. Do not add background, numbers, names,
   dates or products that the source does not mention. If the source is vague, be vague.
2. No hype. Never use: game-changer, revolutionary, groundbreaking, cutting-edge, seamless,
   unlock, supercharge, next-level, disrupt, incredible, must-read, excited, thrilled.
3. Third person only. No "we", "I", "you should".
4. Lead with what happened and why a working engineer would care. Do not describe the article
   ("this post explains..."); describe the thing.
5. No URLs in the blurb. No emoji. No exclamation marks.
6. If the source is a product announcement, say who ships it and what it does. If it is an
   opinion piece, attribute the opinion to the author or publication.
