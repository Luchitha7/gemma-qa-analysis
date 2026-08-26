package us.adepttech.signalqa.model;

import java.util.Map;

/**
 * The scoring result that comes back from the Python /analyze endpoint.
 *
 * Python returns a large JSON object (final, band, agent, ratings, compliance,
 * and so on, all documented in FRONTEND_API_GUIDE.md). We do not need to model
 * every field in Java, so we keep the whole thing as a map and pull out the two
 * fields the worker cares about (the overall score and the band).
 *
 * @param callId the id of the call this result belongs to
 * @param fields the full result object from Python, as a map
 */
public record ScoreResult(String callId, Map<String, Object> fields) {

    /** The overall 0-100 score, or null if Python returned an error instead. */
    public Object finalScore() {
        return fields == null ? null : fields.get("final");
    }

    /** GOOD / OKAY / NEEDS IMPROVEMENT, or null on error. */
    public Object band() {
        return fields == null ? null : fields.get("band");
    }

    /** Python returns an "error" key instead of a score for a bad transcript. */
    public boolean isError() {
        return fields != null && fields.containsKey("error");
    }
}
