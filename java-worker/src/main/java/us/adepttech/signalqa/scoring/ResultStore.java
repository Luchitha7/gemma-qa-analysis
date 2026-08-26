package us.adepttech.signalqa.scoring;

import org.springframework.stereotype.Component;
import us.adepttech.signalqa.model.ScoreResult;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Where finished results are kept so a caller can fetch them by callId.
 *
 * This is a deliberately simple in-memory store so the skeleton runs end to end
 * on one machine. In production this becomes a database or a second Kafka topic
 * ("scored-calls") that another service reads. It is the one piece a reviewer
 * will expect to see replaced before this goes live.
 */
@Component
public class ResultStore {

    private final Map<String, ScoreResult> results = new ConcurrentHashMap<>();

    public void save(ScoreResult result) {
        results.put(result.callId(), result);
    }

    public ScoreResult get(String callId) {
        return results.get(callId);
    }
}
