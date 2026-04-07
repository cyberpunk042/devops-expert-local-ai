---
name: Stop minimizing, compressing, and conflating
description: Model keeps merging separate requirements into one, rushing to present designs before understanding, and asking questions the user already answered
type: feedback
---

When the user describes multiple separate things, keep them separate. Do not merge them. Do not compress. Do not conflate.

When the user says "explore and analyze", do the exploration FIRST, report findings, THEN design. Do not skip to design.

When the user has already explained what they want, do not ask them to repeat. Go re-read the conversation.

When the user says "take your time" and "plan big", do thorough investigation with subagents, read all the code, understand the full picture, and THEN present.

**Why:** User has been burned repeatedly by the model compressing 5 distinct requirements into 1 sloppy design, rushing to present before understanding, and asking questions that were already answered. Each time causes frustration and wasted iterations.

**How to apply:** Before presenting any design, verify: (1) have I actually read the relevant code? (2) am I treating each requirement as separate? (3) has the user already answered this question? (4) have I done enough exploration or am I guessing?
