#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <signal.h>
#include <MQTTClient.h>

#define ADDRESS     "tcp://100.106.113.72:1883"
#define CLIENTID    "C_Publisher"
#define TOPIC       "experiment/data"
#define CONTROL     "experiment/control"
#define CHECKSUM_TOPIC "experiment/checksum"
#define QOS         1
#define TIMEOUT     10000L
#define BATCH_SIZE  512
#define MAX_BUFFER  8192

volatile bool running = false;
uint32_t seq_num = 1;
uint64_t checksum = 0;
int count = 0;

pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
uint8_t* buffer[MAX_BUFFER];
int buffer_len = 0;

MQTTClient client;

void rebuffer(uint8_t* payload) {
    pthread_mutex_lock(&lock);
    if (buffer_len < MAX_BUFFER) {
        buffer[buffer_len++] = payload;
    } else {
        free(payload);  // drop oldest if buffer full
    }
    pthread_mutex_unlock(&lock);
}

void* data_gen_thread(void* arg) {
    while (1) {
        if (!running) {
            usleep(1000);
            continue;
        }
        uint8_t* payload = malloc(BATCH_SIZE * 12);
        for (int i = 0; i < BATCH_SIZE; i++) {
            double adc_value = 123.456;
            memcpy(&payload[i * 12], &adc_value, sizeof(double));
            memcpy(&payload[i * 12 + 8], &seq_num, sizeof(uint32_t));
            for (int j = 0; j < 12; j++) checksum += payload[i * 12 + j];
            seq_num++;
        }

        pthread_mutex_lock(&lock);
        if (buffer_len < MAX_BUFFER) {
            buffer[buffer_len++] = payload;
        } else {
            free(payload);  // drop oldest if buffer full
        }
        pthread_mutex_unlock(&lock);

        count += BATCH_SIZE;
    }
    return NULL;
}

void* publisher_thread(void* arg) {
    while (1) {
        if (!running) {
            usleep(1000);
            continue;
        }

        pthread_mutex_lock(&lock);
        if (buffer_len == 0) {
            pthread_mutex_unlock(&lock);
            usleep(100);
            continue;
        }

        uint8_t* payload = buffer[0];
        memmove(&buffer[0], &buffer[1], (buffer_len - 1) * sizeof(uint8_t*));
        buffer_len--;
        pthread_mutex_unlock(&lock);

        MQTTClient_message pubmsg = MQTTClient_message_initializer;
        pubmsg.payload = payload;
        pubmsg.payloadlen = BATCH_SIZE * 12;
        pubmsg.qos = QOS;
        pubmsg.retained = 0;

        MQTTClient_deliveryToken token;
        int rc = MQTTClient_publishMessage(client, TOPIC, &pubmsg, &token);
        if (rc != MQTTCLIENT_SUCCESS) {
            printf("Publish failed (rc=%d), rebuffering\n", rc);
            rebuffer(payload);
        } else {
            free(payload);
        }
    }
    return NULL;
}

int on_message(void *context, char *topicName, int topicLen, MQTTClient_message *message) {
    char *payload = (char *)message->payload;
    payload[message->payloadlen] = '\0';

    if (strcmp(topicName, CONTROL) == 0) {
        if (strcmp(payload, "1") == 0) {
            running = true;
            printf("Signal started.\n");
        } else if (strcmp(payload, "0") == 0) {
            running = false;
            printf("Signal stopped.\n");

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

            printf("Sent %d samples. Checksum = %llu\n", count, (unsigned long long)checksum);
        }
    }

    MQTTClient_freeMessage(&message);
    MQTTClient_free(topicName);
    return 1;
}

int main() {
    MQTTClient_connectOptions conn_opts = MQTTClient_connectOptions_initializer;
    MQTTClient_create(&client, ADDRESS, CLIENTID, MQTTCLIENT_PERSISTENCE_NONE, NULL);
    MQTTClient_setCallbacks(client, NULL, NULL, on_message, NULL);

    if (MQTTClient_connect(client, &conn_opts) != MQTTCLIENT_SUCCESS) {
        fprintf(stderr, "Failed to connect\n");
        return 1;
    }

    MQTTClient_subscribe(client, CONTROL, QOS);
    printf("Connected to broker. Waiting for control command.\n");

    pthread_t gen_thread, pub_thread;
    pthread_create(&gen_thread, NULL, data_gen_thread, NULL);
    pthread_create(&pub_thread, NULL, publisher_thread, NULL);

    while (1) sleep(1);

    return 0;
}
