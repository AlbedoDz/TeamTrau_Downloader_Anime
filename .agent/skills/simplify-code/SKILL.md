---
name: simplify-code
description: "Review a diff for clarity and safe simplifications, then optionally apply low-risk fixes."
risk: safe
source: "Dimillian/Skills (MIT)"
date_added: "2026-03-25"
---

# Simplify Code

Review changed code for reuse, quality, efficiency, and clarity issues. Use Codex sub-agents to review in parallel, then optionally apply only high-confidence, behavior-preserving fixes.

## When to Use
- When the user asks to simplify, clean up, refactor, or review changed code.
- When you want high-confidence, behavior-preserving improvements on a scoped diff.

## Modes

Choose the mode from the user's request:
- `review-only`: user asks to review, audit, or check the changes
- `safe-fixes`: user asks to simplify, clean up, or refactor the changes
- `fix-and-validate`: same as `safe-fixes`, but also run the smallest relevant validation after edits

If the user does not specify, default to:
- `review-only` for "review", "audit", or "check"
- `safe-fixes` for "simplify", "clean up", or "refactor"

## Step 1: Determine the Scope and Diff Command
Prefer this scope order:
1. Files or paths explicitly named by the user
2. Current git changes
3. Files edited earlier in the current Codex turn
4. Most recently modified tracked files, only if the user asked for a review but there is no diff

## Step 2: Launch Four Review Sub-Agents in Parallel
Use Codex sub-agents when the scope is large enough for parallel review to help. For a tiny diff or one very small file, it is acceptable to review locally instead.

### Sub-Agent 1: Code Reuse Review
Review the changes for reuse opportunities:
1. Search for existing helpers, utilities, or shared abstractions that already solve the same problem.
2. Flag duplicated functions or near-duplicate logic introduced in the change.
3. Flag inline logic that should call an existing helper instead of re-implementing it.

### Sub-Agent 2: Code Quality Review
Review the same changes for code quality issues:
1. Redundant state, cached values, or derived values stored unnecessarily.
2. Parameter sprawl caused by threading new arguments through existing call chains.
3. Copy-paste with slight variation that should become a shared abstraction.
4. Leaky abstractions or ownership violations across module boundaries.
5. Stringly-typed values where existing typed contracts, enums, or constants already exist.

### Sub-Agent 3: Efficiency Review
Review the same changes for efficiency issues:
1. Repeated work, duplicate reads, duplicate API calls, or unnecessary recomputation.
2. Sequential work that could safely run concurrently.
3. New work added to startup, render, request, or other hot paths without clear need.
4. Pre-checks for existence when the operation itself can be attempted directly and errors handled.
5. Memory growth, missing cleanup, or listener/subscription leaks.
6. Overly broad reads or scans when the code only needs a subset.

### Sub-Agent 4: Clarity and Standards Review
Review the same changes for clarity, local standards, and balance:
1. Violations of local project conventions or module patterns.
2. Unnecessary complexity, deep nesting, weak names, or redundant comments.
3. Overly compact or clever code that reduces readability.
4. Over-simplification that collapses separate concerns into one unclear unit.
5. Dead code, dead abstractions, or indirection without value.

## Step 3: Aggregate Findings
Wait for all review sub-agents to complete, then merge their findings. Discard weak, duplicative, or instruction-conflicting findings before editing.

## Step 4: Fix Issues Carefully
In `safe-fixes` or `fix-and-validate` mode:
- Apply only high-confidence, behavior-preserving fixes.
- Skip subjective refactors that need product or architectural judgment.
- Preserve local patterns when they are intentional or instruction-backed.

## Step 5: Validate When Required
In `fix-and-validate` mode, run the smallest relevant validation for the touched scope after edits (e.g. targeted pytest runs or Ruff formatting).
