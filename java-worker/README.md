# SignalQA Java Worker

This is the Java + Kafka version of the queue and worker layer that currently
lives in `job_queue.py`. It is a work in progress and is **not wired into the
live system**. It sits beside the Python app and does not change it.

## The idea in one line

Kafka is the waiting line, Java moves the traffic, Python still does the scoring.

## How the pieces map to the Python system

| Python today | Here (Java + Kafka) |
|---|---|
| `queue.Queue` holding jobs in memory | the Kafka topic `calls-to-score` (backlog on disk) |
| `MAX_CONCURRENT = 2` worker threads | `@KafkaListener(concurrency = "2")` in `CallScoringWorker` |
| `CAPACITY = 5` + 503 rejection | gone; Kafka absorbs the backlog, nothing is rejected |
| the worker calling the scoring code | `ScoringClient` calling Python `POST /analyze` over HTTP |
| RoBERTa + Gemma + scoring | unchanged, still in Python |

## The flow

```
POST /calls  ──►  CallProducer  ──►  Kafka topic "calls-to-score"
 (returns a                                  │
  callId now)                                │  2 partitions
                                   ┌─────────┴─────────┐
                                   ▼                   ▼
                              Worker 1            Worker 2      (CallScoringWorker, concurrency 2)
                                   │                   │
                                   └───────┬───────────┘
                                           ▼
                                 ScoringClient  ──►  Python POST /analyze
                                           │
                                           ▼
                                     ResultStore   ──►  GET /calls/{callId}
```

## The one behaviour change to know

The Python `/analyze` scores the call and returns the result on the same
request. Going through Kafka makes this **asynchronous**:

- `POST /calls` returns a `callId` immediately (the call is only queued).
- `GET /calls/{callId}` returns the result once a worker has scored it.

Nobody is rejected under load, but the caller fetches the answer instead of
waiting on one response.

## Files

- `web/IngestController.java` — the front door: accept a transcript, queue it, fetch results.
- `kafka/CallProducer.java` — drops a call on the topic.
- `kafka/CallScoringWorker.java` — the 2 workers; pull a call, score it, save it.
- `scoring/ScoringClient.java` — calls the Python `/analyze` endpoint.
- `scoring/ResultStore.java` — in-memory result store (a DB or results topic later).
- `config/KafkaTopicConfig.java` — the topic and its partition count.
- `model/CallMessage.java`, `model/ScoreResult.java` — the data that moves around.

## Running it locally (once Docker is available)

You need three things up at once: Kafka, the Python app, and this service.

```bash
# 1. Start Kafka (needs Docker Desktop installed)
cd java-worker
docker compose up -d

# 2. Start the Python scoring app (from the repo root, as usual)
#    so it is listening on http://localhost:8000

# 3. Start this Java service
mvn spring-boot:run
```

Then submit a call and fetch its result:

```bash
# queue a call, note the callId it returns
curl -s -X POST http://localhost:8080/calls \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Agent: How can I help?\nClient: I was charged twice."}'

# fetch the result (once a worker has scored it)
curl -s http://localhost:8080/calls/<callId>
```

Docker is not installed on this machine yet, so step 1 waits until it is. The
code compiles and the structure is complete without it.

## Open questions for the team

These change the design and are worth settling before this goes further:

1. Does Python `/analyze` stay behind an HTTP call (recommended), or do they
   want scoring rewritten? Rewriting RoBERTa/Gemma in Java is not realistic.
2. Where do results go long term: a database, or a second `scored-calls` topic?
3. How does a caller learn a result is ready: polling `GET /calls/{id}` (as now),
   or a notification?
4. What is the most workers we ever expect? That sets the topic partition count.
