# gStack-Antigravity: The AI Founder's Toolkit

gStack follows the **"Boil the Lake"** principle — with AI, the marginal cost of completeness is near-zero. Instead of "good enough," we aim for "complete" (full test coverage, all edge cases, robust error handling).

Commands are grouped by the natural lifecycle of a sprint:
**Think → Plan → Build → Review → Test → Ship → Reflect**

## 1. Think (Phase 1)
| Command | Role | Description |
|---|---|---|
| `/office-hours` | **Founder Advisor** | YC-style brainstorming session. Forces specificity on demand, status quo, and your "narrowest wedge" before any code is written. |

## 2. Plan (Phase 2)
| Command | Role | Description |
|---|---|---|
| `/plan-ceo-review` | **CEO** | Strategy & ambition audit. Challenges whether the feature actually moves the needle for users. |
| `/plan-eng-review` | **Lead Engineer** | Architecture & execution review. Focuses on data flow, state machines, and failure modes. |
| `/plan-design-review`| **Designer** | Reviews the plan through a UX lens — information hierarchy, interaction states, and Rams' principles. |
| `/design-consultation`| **Design Lead** | Helps implement or refine your design system (colors, typography, components). |
| `/autoplan` | **Review Suite** | Runs the CEO, Eng, and Design reviews automatically on the current plan. |
| `/cso` | **Security Officer**| Security audit for the proposed plan — identifies data leaks, auth bypasses, and infra risks. |

## 3. Build & Execution (Phase 3)
| Command | Role | Description |
|---|---|---|
| `/investigate` | **Debugger** | Systematic root cause investigation for complex bugs. Checks logs, state, and traces. |
| `/codex` | **Second Opinion** | Requests an adversarial code review or a "second opinion" from another LLM perspective. |
| `/freeze` | **Scope Guard** | Restricts all AI edits to a specific directory or module to prevent regressions elsewhere. |
| `/guard` | **Safety Mode** | Maximum safety: enables destructive command warnings and stricter edit restrictions. |
| `/unfreeze` | **Reset** | Removes all edit/directory restrictions. |
| `/careful` | **Live Ops** | Guardrails for working with production or live systems. |

## 4. Review & Test (Phase 4)
| Command | Role | Description |
|---|---|---|
| `/review` | **PR Reviewer** | Pre-merge code review. Catches bugs, style issues, and missing tests before you land code. |
| `/qa` | **QA Engineer** | Full browser-based E2E testing. Opens a real browser, clicks through flows, and finds/fixes bugs. |
| `/qa-only` | **QA Reporter** | Runs the browser tests and reports results without automatically fixing them. |
| `/design-review` | **Visual QA** | Visual design audit — checks layouts, responsive states, and UI polish against the design doc. |
| `/browse` | **Live Browser** | Direct access to the headless browser for manual inspection or automation scripts. |

## 5. Ship & Post-Release (Phase 5)
| Command | Role | Description |
|---|---|---|
| `/ship` | **Release Manager**| Orchestrates the final merge. Runs tests, verifies the build, and prepares the release. |
| `/land-and-deploy` | **DevOps** | Automation for merging, deploying to staging/prod, and verifying the deployment. |
| `/canary` | **Monitor** | Post-deploy monitoring for health checks and errors in production. |
| `/benchmark` | **Perf Eng** | Performance regression detection using the browse daemon. |
| `/document-release`| **Doc Engineer** | Automatically updates documentation (README, CHANGELOG) after a successful ship. |
| `/retro` | **Team Lead** | Engineering retrospective. Reflects on the sprint, what was hard, and how to improve. |

## 6. Maintenance & Config
| Command | Role | Description |
|---|---|---|
| `/gstack-upgrade` | **Updater** | Upgrades gstack to the latest version from GitHub. |
| `/setup-cookies` | **Auth Helper** | Imports cookies from your real browser (Chrome/Arc/Brave) into the gstack headless browser. |
| `/setup-deploy` | **Configurator**| One-time setup for your deployment pipeline (staging vs. prod URLs). |

## Core Philosophies
1. **Specificity is the only currency.** No vague goals. We name individuals, roles, and concrete pain points.
2. **Interest is not demand.** Waitlists don't count. Behavior (usage, payment, anger when it breaks) counts.
3. **See something, say something.** If the AI notices a bug outside the current task, it's encouraged to flag or fix it proactively (especially in `solo` mode).
