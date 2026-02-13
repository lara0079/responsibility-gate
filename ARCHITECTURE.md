# Responsibility Gate — Architecture Note

## Purpose
Responsibility Gate is a pre-execution control layer for AI-assisted systems. Its job is simple: it prevents high-impact actions from executing unless a named human authority explicitly assumes responsibility.

## Design principle
No high-impact automated decision executes without named human responsibility.

## Where it sits
The gate runs between a decision-producing system and whatever executes the action. It does not replace the AI. It constrains what can be executed.

## Operational flow
A system submits an action and a justification. The gate stores the proposal, assigns it a state, and enforces the execution rules.

High-risk proposals are held for authorization. Low-risk proposals can pass without blocking routine automation.

## States
- pending: proposed, not allowed to execute
- approved: cleared for execution (system-approved for low risk, human-approved for high risk)
- executed: executed and logged
- rejected: explicitly rejected and logged

## Accountability binding
For high-risk actions, approval requires a human identity (authorized_by), a timestamp, and an optional note. Without that binding, execution is blocked.

## Audit record
Each decision stores: action, justification, risk level, state transitions, timestamps, and execution outcome. This is meant to support traceability and later review.

## Intended institutional use
Designed for environments where automated decisions have real-world consequences: public sector workflows, regulatory decisions, licensing/approvals, and other high-impact automated operations.

