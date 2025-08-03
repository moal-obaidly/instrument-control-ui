#include <zmq.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <time.h>

#define BATCH_SIZE 100

volatile int running = 1;
uint32_t seq_num = 1;

void* signal_thread_func(void* arg) {
    void* socket = (void*)arg;

    while (running) {
        uint8_t batch[BATCH_SIZE * 12];  // 12 bytes per sample

        for (int i = 0; i < BATCH_SIZE; i++) {
            double adc_val = 123.456;  // simulate ADC value
            uint32_t seq = seq_num++;

            memcpy(&batch[i * 12], &adc_val, sizeof(double));
            memcpy(&batch[i * 12 + 8], &seq, sizeof(uint32_t));
        }

        // Send topic first
        zmq_send(socket, "experiment/data", 15, ZMQ_SNDMORE);
        zmq_send(socket, batch, sizeof(batch), 0);

        usleep(100);  // throttle CPU
    }

    return NULL;
}

void handle_sigint(int sig) {
    running = 0;
    printf("\nSignal stopped. Exiting...\n");
}

int main() {
    signal(SIGINT, handle_sigint);

    // Setup ZeroMQ PUB socket
    void* context = zmq_ctx_new();
    void* pub_socket = zmq_socket(context, ZMQ_PUB);
    int rc = zmq_bind(pub_socket, "tcp://*:5556");
    if (rc != 0) {
        perror("Failed to bind PUB socket");
        return 1;
    }

    printf("ZeroMQ publisher started. Press Ctrl+C to stop.\n");

    // Start signal thread
    pthread_t signal_thread;
    pthread_create(&signal_thread, NULL, signal_thread_func, pub_socket);

    // Wait for thread to finish
    pthread_join(signal_thread, NULL);

    // Clean up
    zmq_close(pub_socket);
    zmq_ctx_destroy(context);

    return 0;
}
