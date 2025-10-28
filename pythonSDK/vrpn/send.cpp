#include <iostream>
#include <string>
#include <vector>
#include <chrono>
#include <thread>
#include <csignal>
#include <cstring>
#include "vrpn_Tracker.h"
#include "zmq.hpp"

volatile sig_atomic_t g_should_run = 1;

void signal_handler(int) {
    g_should_run = 0;
}

// Message type identifiers
enum class MessageType : uint8_t {
    POSE = 0x01,
    VELOCITY = 0x02,
    ACCELERATION = 0x03
};

void VRPN_CALLBACK handle_pose(void* userdata, const vrpn_TRACKERCB t) {
    zmq::socket_t* socket = static_cast<zmq::socket_t*>(userdata);

    // Create message: [type_byte][data]
    size_t msg_size = sizeof(MessageType) + sizeof(vrpn_TRACKERCB);
    zmq::message_t msg(msg_size);

    uint8_t* ptr = static_cast<uint8_t*>(msg.data());
    *ptr = static_cast<uint8_t>(MessageType::POSE);
    memcpy(ptr + sizeof(MessageType), &t, sizeof(vrpn_TRACKERCB));

    socket->send(msg, zmq::send_flags::none);
}

void VRPN_CALLBACK handle_velocity(void* userdata, const vrpn_TRACKERVELCB t) {
    zmq::socket_t* socket = static_cast<zmq::socket_t*>(userdata);

    // Create message: [type_byte][data]
    size_t msg_size = sizeof(MessageType) + sizeof(vrpn_TRACKERVELCB);
    zmq::message_t msg(msg_size);

    uint8_t* ptr = static_cast<uint8_t*>(msg.data());
    *ptr = static_cast<uint8_t>(MessageType::VELOCITY);
    memcpy(ptr + sizeof(MessageType), &t, sizeof(vrpn_TRACKERVELCB));

    socket->send(msg, zmq::send_flags::none);
}

void VRPN_CALLBACK handle_acceleration(void* userdata, const vrpn_TRACKERACCCB t) {
    zmq::socket_t* socket = static_cast<zmq::socket_t*>(userdata);

    // Create message: [type_byte][data]
    size_t msg_size = sizeof(MessageType) + sizeof(vrpn_TRACKERACCCB);
    zmq::message_t msg(msg_size);

    uint8_t* ptr = static_cast<uint8_t*>(msg.data());
    *ptr = static_cast<uint8_t>(MessageType::ACCELERATION);
    memcpy(ptr + sizeof(MessageType), &t, sizeof(vrpn_TRACKERACCCB));

    socket->send(msg, zmq::send_flags::none);
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: " << argv[0] << " TrackerName@VRPNServerIP" << std::endl;
        return 1;
    }

    // Set up ZeroMQ publisher
    zmq::context_t context(1);
    zmq::socket_t publisher(context, zmq::socket_type::pub);
    publisher.bind("tcp://*:5555");

    // Set up VRPN tracker
    vrpn_Tracker_Remote tracker(argv[1]);
    tracker.register_change_handler(&publisher, handle_pose);
    tracker.register_change_handler(&publisher, handle_velocity);
    tracker.register_change_handler(&publisher, handle_acceleration);

    // Set up signal handler for graceful shutdown
    signal(SIGINT, signal_handler);

    std::cout << "Starting VRPN to ZeroMQ bridge..." << std::endl;
    std::cout << "Publishing on tcp://*:5555" << std::endl;
    std::cout << "  - Pose data (position + quaternion)" << std::endl;
    std::cout << "  - Velocity data (linear + angular)" << std::endl;
    std::cout << "  - Acceleration data (linear + angular)" << std::endl;
    std::cout << "Press Ctrl+C to exit." << std::endl;

    while (g_should_run) {
        tracker.mainloop();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }

    std::cout << "Shutting down..." << std::endl;
    return 0;
}
