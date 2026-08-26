package us.adepttech.signalqa.web;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import us.adepttech.signalqa.kafka.CallProducer;
import us.adepttech.signalqa.model.CallMessage;
import us.adepttech.signalqa.model.ScoreResult;
import us.adepttech.signalqa.scoring.ResultStore;

import java.util.Map;
import java.util.UUID;

/**
 * The front door of the Java service.
 *
 * IMPORTANT behaviour change from the Python /analyze: that endpoint scored the
 * call and returned the result on the same request (synchronous). Going through
 * Kafka makes this ASYNCHRONOUS. Here, POST /calls only drops the call on the
 * topic and hands back a callId straight away. The caller then fetches the
 * result later with GET /calls/{id}. This is the trade Kafka brings: nobody is
 * rejected under load, but the answer is picked up rather than waited on.
 */
@RestController
@RequestMapping("/calls")
public class IngestController {

    private final CallProducer producer;
    private final ResultStore results;

    public IngestController(CallProducer producer, ResultStore results) {
        this.producer = producer;
        this.results = results;
    }

    /**
     * Accept a transcript and queue it for scoring.
     * Body: { "transcript": "Agent: ...\nClient: ..." }
     * Returns: { "callId": "..." , "status": "queued" }
     */
    @PostMapping
    public ResponseEntity<Map<String, String>> submit(@RequestBody Map<String, String> body) {
        String transcript = body.get("transcript");
        if (transcript == null || transcript.isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "transcript is required"));
        }

        String callId = UUID.randomUUID().toString();
        producer.enqueue(new CallMessage(callId, transcript));

        return ResponseEntity.accepted()
                .body(Map.of("callId", callId, "status", "queued"));
    }

    /**
     * Fetch the result once a worker has scored it.
     * Returns 200 with the result, or 404 while it is still being processed.
     */
    @GetMapping("/{callId}")
    public ResponseEntity<?> result(@PathVariable String callId) {
        ScoreResult result = results.get(callId);
        if (result == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("callId", callId, "status", "not ready"));
        }
        return ResponseEntity.ok(result.fields());
    }
}
