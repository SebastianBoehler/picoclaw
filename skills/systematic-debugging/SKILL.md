---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# Systematic Debugging

## Overview
Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

## The Iron Law
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use
Use for ANY technical issue: test failures, bugs, unexpected behavior, performance problems, build failures, integration issues.

**Use ESPECIALLY when:** under time pressure, "just one quick fix" seems obvious, you've already tried multiple fixes.

## The Four Phases

### Phase 1: Root Cause Investigation
1. **Read Error Messages Carefully** — stack traces, line numbers, error codes
2. **Reproduce Consistently** — if not reproducible, gather more data, don't guess
3. **Check Recent Changes** — git diff, new dependencies, config changes
4. **Gather Evidence** — in multi-component systems, add diagnostic logging at each boundary BEFORE proposing fixes
5. **Trace Data Flow** — where does bad value originate? Fix at source, not symptom

### Phase 2: Pattern Analysis
1. Find working examples of similar code in the codebase
2. Compare against references — read completely, don't skim
3. List every difference, however small
4. Understand dependencies and assumptions

### Phase 3: Hypothesis and Testing
1. State clearly: "I think X is the root cause because Y"
2. Make the SMALLEST possible change to test hypothesis
3. One variable at a time — don't fix multiple things at once
4. If wrong: form NEW hypothesis, don't add more fixes on top

### Phase 4: Implementation
1. Create failing test case first
2. Implement single fix addressing root cause
3. Verify fix — tests pass, no regressions
4. **If ≥ 3 fixes failed: STOP — question the architecture**

## Red Flags — STOP and Return to Phase 1
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably X, let me fix that"
- "One more fix attempt" (when already tried 2+)
- Each fix reveals a new problem in a different place

## Quick Reference
| Phase | Success Criteria |
|-------|-----------------|
| 1. Root Cause | Understand WHAT and WHY |
| 2. Pattern | Identify differences from working code |
| 3. Hypothesis | Confirmed or new hypothesis formed |
| 4. Implementation | Bug resolved, tests pass |

## Real-World Impact
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
