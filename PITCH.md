# Voicox: Solution Pitch

**Ask. Hear. Know.** A voice assistant for kirana shops.
Harshita Rathor | Gnani AI Great Indian AI Internship Challenge

## Problem

Millions of kirana shops run on memory, notebooks and spreadsheets. When the stock count comes up short, the owner can't tell why: a missed sale, damaged goods, or something else. The records exist, but reading reports takes time that someone serving customers in Hindi or Hinglish doesn't have, so the insights often go unused.

## Solution

Voicox turns the shop's records into a conversation.

- **Ask.** Owners ask questions out loud in Hindi, Hinglish or English, transcribed with Gnani Prisma.
- **Hear.** Answers are spoken back in the same language with Gnani Timbre, with a chart or table on screen.
- **Know.** Every number is calculated from the shop's own sales, purchase and inventory data.

## Demo moment

> **Owner:** "Chawal mein gap kyun hai?"
> **Voicox:** Rice is 17 units short: 194 expected, 177 counted. One possible cause is that no sales were recorded on 11 October. These are possible explanations, not accusations.

It also answers "Pichle mahine sabse zyada kya bika?", "Is hafte ki bikri kitni hui?" and "Kaun sa saman kam bach gaya hai?"

**Demo video:** [Watch on YouTube](https://youtu.be/YOUR_VIDEO_ID)

## Built to be trusted

- **No LLM at runtime.** A rule-based extractor maps each question to a fixed, validated question type, and DuckDB computes the numbers. A language model never generates a figure.
  `Speech → Transcription → Extraction → Validation → DuckDB → Response → Speech`
- **Honest refusals.** For advice, predictions, customer information, prices, profit, unknown products or unsupported periods, Voicox says it can't answer instead of guessing.
- **Explains without blaming.** It compares expected stock with counted stock and offers possible causes to investigate, not accusations.
  `Expected = Opening + Purchased − Sold − Damaged`
  `Shortfall = Expected − Counted`

## Results

Tested on synthetic shop data, with each answer checked against figures calculated independently from the raw CSV files.

- **28 of 30 questions correct (93%).** 20 were spoken (Hinglish, Hindi, English, noisy audio) and 10 were typed.
- **Hinglish, Hindi and noisy audio: 100%. English: 60% (3 of 5).** Both misses were English phrases misheard by the speech recogniser, and they are documented in `benchmark/results.md`.
- **309 automated tests pass.** Data cleaning reduced 905 raw sales rows to 892 clean rows.

## Why it is different

Many billing and ledger apps are screen-based: the owner still has to find and read the report. Voicox starts from the owner's own language and question, and goes beyond showing numbers by helping investigate stock gaps using the shop's records.

## Status and roadmap

Voicox is a working prototype running locally on synthetic data, with a mobile-first layout for phone screens. It isn't hosted publicly because an open demo could expose the Gnani API key; login and usage limits come first.

Next steps:

1. Validate with real shop records.
2. Make records easy to capture digitally (for example voice entry or photo import), so shops that start on paper can use it.
3. Integrate real billing, purchase and credit records.
4. Add more Indian languages through language-specific phrase sets.
5. Deploy a hosted version with login and usage limits.

**Tech stack:** Python, FastAPI, DuckDB, Gnani Prisma, Gnani Timbre.
**Acknowledgement:** Built with assistance from Claude (Anthropic).
