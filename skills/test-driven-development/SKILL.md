---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
---

# Test-Driven Development (TDD)

## Overview
Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

## The Iron Law
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over. No exceptions.

## Red-Green-Refactor

### RED — Write Failing Test
Write one minimal test showing what should happen. One behavior, clear name, real code (no mocks unless unavoidable).

### Verify RED — Watch It Fail
**MANDATORY. Never skip.** Run the test. Confirm it fails for the right reason (feature missing, not a typo).

### GREEN — Minimal Code
Write the simplest code to pass the test. Don't add features or refactor beyond the test.

### Verify GREEN — Watch It Pass
**MANDATORY.** Run it. Confirm it passes and no other tests broke.

### REFACTOR — Clean Up
After green only: remove duplication, improve names, extract helpers. Keep tests green.

### Repeat
Next failing test for next feature.

## Good Tests
- One behavior per test — "and" in the name? Split it
- Clear name describing the behavior
- Tests real code, not mocks (unless unavoidable)
- Watched it fail before implementing

## Red Flags — Delete Code and Start Over
- Code written before test
- Test passes immediately without implementation
- Can't explain why the test failed
- "I'll write tests after"
- "Already manually tested it"
- "Tests after achieve the same goals"

## Verification Checklist
Before marking work complete:
- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass, output pristine
- [ ] Edge cases covered

## Final Rule
```
Production code → test exists and failed first. Otherwise → not TDD.
```
