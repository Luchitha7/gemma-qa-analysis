package us.adepttech.signalqa;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point for the Java side of SignalQA.
 *
 * This service does NOT score calls itself. The AI models (RoBERTa, Gemma)
 * stay in the Python app. This service is only the plumbing that used to live
 * in job_queue.py:
 *
 *   - it accepts a transcript and drops it onto a Kafka topic (the producer),
 *   - a pool of workers pulls transcripts off that topic and asks the Python
 *     /analyze endpoint to score each one (the consumers).
 *
 * Kafka is the waiting line. Python is still the brain.
 */
@SpringBootApplication
public class SignalQaWorkerApplication {

    public static void main(String[] args) {
        SpringApplication.run(SignalQaWorkerApplication.class, args);
    }
}
