package us.adepttech.signalqa.scoring;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import us.adepttech.signalqa.model.ScoreResult;

import java.util.Map;

/**
 * Talks to the Python scoring service.
 *
 * This is the bridge between the two worlds. The Java worker never runs a model;
 * it hands the transcript to Python's existing /analyze endpoint over HTTP and
 * gets back the full result object. Python stays exactly as it is.
 */
@Component
public class ScoringClient {

    private final RestClient http;

    /**
     * The base URL of the Python app, read from application.yml
     * (python.analyze-url). Defaults to the local dev address.
     */
    public ScoringClient(@Value("${python.base-url:http://localhost:8000}") String baseUrl) {
        this.http = RestClient.builder()
                .baseUrl(baseUrl)
                .build();
    }

    /**
     * Send one transcript to Python /analyze and return the parsed result.
     *
     * Mirrors what job_queue.py's worker used to do in-process, except the
     * scoring now happens over an HTTP call to Python instead of a direct call.
     */
    @SuppressWarnings("unchecked")
    public ScoreResult analyze(String callId, String transcript) {
        Map<String, Object> body = http.post()
                .uri("/analyze")
                .body(Map.of("transcript", transcript))
                .retrieve()
                .body(Map.class);

        return new ScoreResult(callId, body);
    }
}
