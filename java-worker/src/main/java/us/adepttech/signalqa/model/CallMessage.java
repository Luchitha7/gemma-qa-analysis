package us.adepttech.signalqa.model;

/**
 * One unit of work travelling through Kafka: a single call to be scored.
 *
 * This is the equivalent of one job that used to sit in job_queue.py's in-memory
 * queue. Now it is a message on the "calls-to-score" topic instead.
 *
 * A Java record is just a small immutable data holder (like a Python dataclass).
 *
 * @param callId     our own id for this call, so we can match the result back
 * @param transcript the raw transcript text, exactly what Python /analyze expects
 */
public record CallMessage(String callId, String transcript) {
}
