# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Roadmap & Backlog

**Split index from detail.** Most roadmap questions ("what's left?", "what's the status of X?") should cost reading one small table, not a full document. A single file with full detail in every row forces everyone to pay that cost on every glance. Splitting it means the cheap, common case (a quick status check) stays cheap, and the expensive case (reading an item's full rationale) is only paid when someone is about to actually work on that specific item.

**Two files, not one:**
- `roadmap.md` (repo root) — the **index**. A markdown table only: `#` | `Feature` | `Status` | one-line `Description`, no exceptions. IDs use a short, consistent prefix (`RM-01`, `RM-02`, ...) — reuse that same ID in branch names and commit messages for that item. Statuses stay simple: `done` / `todo`; add `in-progress` / `blocked` only if the project actually needs them. This file must never grow beyond a table.
- `docs/roadmap.md` — the **detail**. One section per item, with at most a **Why** (1-3 sentences) and a **Scope** (short bullets: what's included, what's deliberately left out). This is not a changelog — history lives in commits/PRs, not here.

**Maintenance rules (permanent — apply in every future session, not just when this was first set up):**
- Never duplicate text between the two files — the index links to the detail section, it doesn't repeat it.
- Once an item is `done` and has been stable for a while, trim its detail section down to 2-3 lines plus a link to the commit/PR — don't preserve the full original reasoning forever.
- Before adding anything to either file, ask: "is this needed to decide or act, or is it just history?" If it's just history, leave it out.
- Large architectural decisions don't live in the roadmap. If the project has (or gets) a dedicated place for those, the roadmap only links to it.

