# Crescendo Red-Teaming

A personal research project implementing the Crescendo multi-turn jailbreak
tactic described by Microsoft Research in
[Russinovich, Salem & Eldan (2024)](#reference), to evaluate how a panel of
open-source LLMs resist an escalating, multi-turn attack.

> **Intended use:** authorized safety research and red-team evaluation of LLM
> safeguards. Do not point this at models or services you do not have
> permission to test.

Given a target objective, an attacker LLM (Gemini) plans a sequence of
escalating questions — starting from a benign, educational framing and
referencing the target's own prior replies each round — and runs that
sequence against a panel of HuggingFace-hosted open-source models in
parallel, so their resistance to the same escalation can be compared
side by side.

## Showcase

Read the case study: **[samguan2020.github.io/crescendo-red-teaming](https://samguan2020.github.io/crescendo-red-teaming/)**

The page source is [`docs/index.html`](docs/index.html), served by GitHub Pages.

## Architecture

Backend-only: a hexagonal (ports and adapters) FastAPI service. See
[`backend/README.md`](backend/README.md) for the full architecture, API
surface, local setup, and test instructions.

```
backend/src/crescendo/
  domain/        # AttackJob, Turn, Verdict, pure domain services — zero framework deps
  application/   # AttackEngine: parallel models, serial turns per model
  strategies/    # GeminiPlanStrategy -> ReactiveStrategy -> TemplateStrategy fallback cascade
  adapters/      # FastAPI routes, Gemini/HuggingFace clients, judge, Postgres + Redis, queue
  infra/         # Settings, composition root, logging
```

## Reference

This project implements the tactic from:

> Mark Russinovich, Ahmed Salem, and Ronen Eldan. **"Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack."** arXiv:2404.01833, 2024. Also presented at USENIX Security 2025.
>
> [Paper (arXiv)](https://arxiv.org/abs/2404.01833) · [Project page](https://crescendo-the-multiturn-jailbreak.github.io/)

This codebase is an independent implementation built to study and evaluate
that tactic — it is not released or endorsed by Microsoft or the paper's
authors.

## Safety

Outputs can include unsafe content by design — that's what's being
measured — so results should be treated as sensitive research data, not
published verbatim.
