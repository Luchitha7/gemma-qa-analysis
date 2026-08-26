package us.adepttech.signalqa.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import us.adepttech.signalqa.config.KafkaTopicConfig;
import us.adepttech.signalqa.model.CallMessage;
import us.adepttech.signalqa.model.ScoreResult;
import us.adepttech.signalqa.scoring.ResultStore;
import us.adepttech.signalqa.scoring.ScoringClient;

/**
 * The worker pool: this is the Java replacement for job_queue.py's workers.
 *
 * The @KafkaListener below IS a worker. Spring runs it for us: whenever a call
 * lands on the topic, this method is called with that call. Setting
 * concurrency = "2" means Spring runs two of these in parallel, exactly like
 * MAX_CONCURRENT = 2 in the Python queue.
 *
 * Note what is GONE compared to the Python version: there is no capacity check
 * and no 503. Kafka holds the backlog on disk, so we never turn a call away.
 * A flood just waits in the topic and is worked through 2 at a time.
 */
@Component
public class CallScoringWorker {

    private static final Logger log = LoggerFactory.getLogger(CallScoringWorker.class);

    private final ScoringClient scoring;
    private final ResultStore results;

    public CallScoringWorker(ScoringClient scoring, ResultStore results) {
        this.scoring = scoring;
        this.results = results;
    }

    /**
     * One worker turn: take a call off the topic, score it via Python, save it.
     *
     * We use MANUAL acknowledgment (ack.acknowledge()) and only call it AFTER
     * scoring succeeds. That is the important bit: if this worker crashes
     * mid-call, the call was never acknowledged, so Kafka hands it to another
     * worker instead of losing it.
     */
    @KafkaListener(
            topics = KafkaTopicConfig.CALLS_TOPIC,
            groupId = "qa-workers",
            concurrency = "2"   // our two workers; raise alongside the partition count
    )
    public void onCall(CallMessage call, Acknowledgment ack) {
        log.info("Worker picked up call {}", call.callId());
        try {
            ScoreResult result = scoring.analyze(call.callId(), call.transcript());

            if (result.isError()) {
                // A bad transcript is a real answer, not a crash. Record it and
                // move on so it does not get retried forever.
                log.warn("Call {} could not be scored: {}", call.callId(), result.fields());
            } else {
                log.info("Call {} scored: final={} band={}",
                        call.callId(), result.finalScore(), result.band());
            }

            results.save(result);
            ack.acknowledge();   // commit only after the work is safely done
        } catch (Exception e) {
            // Do NOT acknowledge: Kafka will redeliver this call so it is retried.
            log.error("Scoring call {} failed, will be retried: {}",
                    call.callId(), e.getMessage());
            throw e;
        }
    }
}
