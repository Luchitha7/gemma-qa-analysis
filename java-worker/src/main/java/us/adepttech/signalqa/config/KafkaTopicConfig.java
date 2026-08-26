package us.adepttech.signalqa.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

/**
 * Defines the topic the calls flow through.
 *
 * The key number here is PARTITIONS. Partitions are the parallel lanes inside a
 * topic, and they cap how many workers can genuinely run at once. We currently
 * run 2 workers (see CallScoringWorker's concurrency), so the topic needs at
 * least 2 partitions. If we later want 5 workers, this has to grow to 5 too.
 *
 * Growing partitions after the fact is awkward, so size this for the most
 * workers you ever expect, not just today's 2.
 */
@Configuration
public class KafkaTopicConfig {

    public static final String CALLS_TOPIC = "calls-to-score";

    @Bean
    public NewTopic callsToScoreTopic() {
        return TopicBuilder.name(CALLS_TOPIC)
                .partitions(2)   // matches our 2 workers; raise this to scale out
                .replicas(1)     // 1 is fine for local dev; production uses 3
                .build();
    }
}
