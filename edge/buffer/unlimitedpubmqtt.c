#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include "MQTTClient.h"

#define ADDRESS         "tcp://100.106.113.72:1883"
#define CLIENTID        "C_Publisher"
#define TOPIC           "experiment/data"
#define CONTROL         "experiment/control"
#define CHECKSUM_TOPIC  "experiment/checksum"
#define QOS             1
#define TIMEOUT         10000L

#define BATCH_SIZE      512

volatile bool running = false;
uint32_t seq_num = 1;
uint64_t checksum = 0;
int count = 0;

MQTTClient client;

void* signal_loop(void* arg) {
    while (running) {
        size_t total_bytes = BATCH_SIZE * 12;
        uint8_t* batch = malloc(total_bytes);
        if (!batch) {
            fprintf(stderr, "Memory allocation failed\n");
            break;
        }

        for (int i = 0; i < BATCH_SIZE; i++) {
            double adc_value = 123.456;
            memcpy(&batch[i * 12], &adc_value, sizeof(double));
            memcpy(&batch[i * 12 + 8], &seq_num, sizeof(uint32_t));
            for (int j = 0; j < 12; j++) checksum += batch[i * 12 + j];
            seq_num++;
            count++;
        }

        MQTTClient_message pubmsg = MQTTClient_message_initializer;
        pubmsg.payload = batch;
        pubmsg.payloadlen = total_bytes;
        pubmsg.qos = QOS;
        pubmsg.retained = 0;

        MQTTClient_deliveryToken token;
        int rc = MQTTClient_publishMessage(client, TOPIC, &pubmsg, &token);
        if (rc == MQTTCLIENT_SUCCESS) {
            MQTTClient_waitForCompletion(client, token, TIMEOUT);
        } else {
            fprintf(stderr, "Failed to publish message, rc=%d\n", rc);
        }

        free(batch);  // clean up
    }

    // Send final checksum
    char msg[64];
    snprintf(msg, sizeof(msg), "%llu", (unsigned long long)checksum);
    MQTTClient_message cmsg = MQTTClient_message_initializer;
    cmsg.payload = msg;
    cmsg.payloadlen = strlen(msg);
    cmsg.qos = 1;
    cmsg.retained = 0;
    MQTTClient_deliveryToken token;
    MQTTClient_publishMessage(client, CHECKSUM_TOPIC, &cmsg, &token);
    MQTTClient_waitForCompletion(client, token, TIMEOUT);

    printf("Signal stopped. Sent %d samples. Checksum = %llu\n", count, (unsigned long long)checksum);
    return NULL;
}

int on_message(void *context, char *topicName, int topicLen, MQTTClient_message *message) {
    char *payload = (char *)message->payload;
    payload[message->payloadlen] = '\0';

    printf("Received on %s: %s\n", topicName, payload);

    if (strcmp(topicName, CONTROL) == 0) {
        if (strcmp(payload, "1") == 0 && !running) {
            running = true;
            pthread_t thread;
            pthread_create(&thread, NULL, signal_loop, NULL);
        } else if (strcmp(payload, "0") == 0 && running) {
            running = false;
        }
    }

    MQTTClient_freeMessage(&message);
    MQTTClient_free(topicName);
    return 1;
}

int main(int argc, char* argv[]) {
    MQTTClient_connectOptions conn_opts = MQTTClient_connectOptions_initializer;

    MQTTClient_create(&client, ADDRESS, CLIENTID, MQTTCLIENT_PERSISTENCE_NONE, NULL);
    MQTTClient_setCallbacks(client, NULL, NULL, on_message, NULL);
    MQTTClient_connect(client, &conn_opts);

    MQTTClient_subscribe(client, CONTROL, QOS);

    printf("Connected to broker\n");

    while (1) sleep(1);
}
