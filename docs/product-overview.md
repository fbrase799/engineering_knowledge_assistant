# Product overview

**Engineering Knowledge Assistant** helps engineers answer hybrid questions that need both:

1. What our curated technical documents say
2. What current public sources say
3. Where those evidence sets agree, disagree, or leave gaps

It is a decision-support tool, not a design authority. Recommendations are labeled as proposals.

## Modes

| Mode | Evidence |
|---|---|
| **Hybrid (default)** | Shared FAISS corpus + one Tavily search |
| Local | Corpus only |
| Web | Tavily only |

## Primary demo question

> How does the sensor timeout handling described in our reference architecture compare with current watchdog recommendations for embedded systems?

## Non-goals (v1)

No document uploads, no multi-agent deep research, no conversation memory, no managed vector DB.
