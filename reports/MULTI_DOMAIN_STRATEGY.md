# Multi-Domain LLM Strategy

This project should start with a general-purpose LLM, then add domain-specific context and evaluation before considering fine-tuning.

## Recommendation

- Keep the base LLM generic.
- Add RAG knowledge packs per business domain.
- Add supervised models for column typing, anomaly detection, and action suggestion.
- Fine-tune only if the domain has enough labeled examples and stable requirements.

## Domain Packs

Create one compact pack per domain:

- Logistics: shipment dates, order ids, warehouse codes, delivery statuses.
- Sales: lead stages, revenue fields, CRM identifiers, customer segments.

Each pack should contain:

- a glossary,
- example schemas,
- validation rules,
- common dirty patterns,
- approved transformations.

## 7-Day Evaluation Plan

### Day 1: Baseline

- Measure the current ETL pipeline on 3 domain datasets.
- Record quality score, runtime, and error rate.

### Day 2: Domain Classification

- Add automatic domain detection from column names and data patterns.
- Validate accuracy on labeled samples.

### Day 3: Domain RAG

- Load the right domain pack before rule generation.
- Compare LLM output with and without domain context.

### Day 4: Supervised Models

- Evaluate the current column-role and action models per domain.
- Track precision, recall, and F1.

### Day 5: Fine-Tuning Decision

- Check if the LLM still makes repeated domain-specific mistakes.
- Only fine-tune if a clear gap remains after RAG and supervised models.

### Day 6: Performance Test

- Measure latency, token usage, and throughput.
- Compare against the generic baseline.

### Day 7: Go/No-Go

- Keep the approach only if it improves quality and remains stable across domains.
- Otherwise, stay with RAG + rules + supervised models.

## Success Criteria

- Quality score improvement of at least 10 points over the baseline.
- F1 score above 0.85 for column classification in stable domains.
- No increase in critical errors.
- Lower or equal total runtime per file.

## Fine-Tuning Rule

Fine-tune the LLM only when all of these are true:

- At least a few hundred labeled examples per domain.
- The domain vocabulary is stable.
- The same mistakes repeat after RAG and rules.
- The gain is measurable in production-like tests.
