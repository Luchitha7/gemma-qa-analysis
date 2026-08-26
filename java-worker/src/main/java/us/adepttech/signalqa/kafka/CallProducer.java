package us.adepttech.signalqa.kafka;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import us.adepttech.signalqa.config.KafkaTopicConfig;
import us.adepttech.signalqa.model.CallMessage;

/**
 * The producer side: puts a call onto the Kafka topic.
 *
 * This is where the "everything goes through Kafka" idea lives. When a call
 * comes in, we do NOT score it on the spot. We drop it on the topic and return
 * immediately. The workers pick it up whenever they are free. That is what lets
 * 200-500 calls arrive at once without anything being rejected: they simply
 * wait in the topic.
 */
@Component
public class CallProducer {

    private final KafkaTemplate<String, CallMessage> kafka;

    public CallProducer(KafkaTemplate<String, CallMessage> kafka) {
        this.kafka = kafka;
    }

    /**
     * Send one call to the topic.
     *
     * We use the callId as the message key. Kafka sends all messages with the
     * same key to the same partition, which keeps ordering predictable and
     * spreads different calls across the partitions (and therefore the workers).
     */
    public void enqueue(CallMessage call) {
        kafka.send(KafkaTopicConfig.CALLS_TOPIC, call.callId(), call);
    }
}
