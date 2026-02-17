# Technical Constraints for MVP Systems

## Latency budget
Real-time product surfaces should define a strict latency budget for each request stage: network overhead, retrieval, model inference, and post-processing. Without explicit budgets, feature scope drifts and user experience degrades.

## Cost and throughput
Inference-heavy workloads need queueing and graceful degradation. Startup teams should monitor average tokens per request, cache hit rates, and fallback paths for high-demand windows.

## Reliability guardrails
Production systems should include retry policies, request timeouts, and observability by endpoint. Background jobs need idempotency to avoid duplicate writes when retries occur.
