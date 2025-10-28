#include <algorithm>
#include <chrono>
#include <csignal>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <cstddef>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <string>

#include "vrpn_Connection.h"
#include "vrpn_Shared.h"
#include "vrpn_Tracker.h"

namespace {

struct TrackerState {
    std::string label;
    std::chrono::steady_clock::time_point last_pose{};
    std::chrono::steady_clock::time_point last_twist{};
    std::chrono::steady_clock::time_point last_accel{};
    double pose_frequency{0.0};
    double twist_frequency{0.0};
    double accel_frequency{0.0};
    bool pose_valid{false};
    bool twist_valid{false};
    bool accel_valid{false};
    vrpn_TRACKERCB latest_pose{};
    vrpn_TRACKERVELCB latest_twist{};
    vrpn_TRACKERACCCB latest_accel{};
    std::string connection_status{"Initializing"};
    std::string last_rendered{};
};

std::sig_atomic_t g_should_run = 1;

void signal_handler(int) { g_should_run = 0; }

std::string now_string()
{
    using clock = std::chrono::system_clock;
    const auto now = clock::now();
    const auto time = clock::to_time_t(now);
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;

    std::ostringstream oss;
    oss << std::put_time(std::localtime(&time), "%F %T") << '.'
        << std::setw(3) << std::setfill('0') << ms.count();
    return oss.str();
}

void print_usage(const char* prog, const std::string& default_device, const std::string& default_host)
{
    std::cerr << "Usage: " << prog << " [--tracker <Device@Host>] [--device <name>] [--host <addr>]\n"
              << "              [--timeout <seconds>]\n"
              << "       " << prog << " <Device@Host>\n\n"
              << "Examples:\n"
              << "  " << prog << " --tracker Drone001@192.168.31.100\n"
              << "  " << prog << " --device Drone001 --host 192.168.31.100\n"
              << "  " << prog << " Drone001@localhost\n\n"
              << "Defaults: device='" << default_device << "', host='" << default_host << "'\n";
}

std::string time_string(const timeval& tv)
{
    if (tv.tv_sec == 0 && tv.tv_usec == 0) {
        return now_string();
    }

    const auto secs = static_cast<std::time_t>(tv.tv_sec);
    const auto ms = tv.tv_usec / 1000;
    std::ostringstream oss;
    oss << std::put_time(std::localtime(&secs), "%F %T") << '.'
        << std::setw(3) << std::setfill('0') << ms;
    return oss.str();
}

std::string format_frequency(double freq)
{
    if (!std::isfinite(freq) || freq <= 0.0) {
        return "freq=-- Hz";
    }

    std::ostringstream oss;
    oss << "freq=" << std::fixed << std::setprecision(2) << freq << " Hz";
    return oss.str();
}

double update_frequency(const std::chrono::steady_clock::time_point& now,
                        std::chrono::steady_clock::time_point& last,
                        double& frequency)
{
    if (last.time_since_epoch().count() != 0) {
        const double dt = std::chrono::duration<double>(now - last).count();
        if (dt > 1e-6) {
            const double instantaneous = 1.0 / dt;
            if (frequency <= 0.0) {
                frequency = instantaneous;
            } else {
                constexpr double alpha = 0.2; // simple low-pass average
                frequency = (1.0 - alpha) * frequency + alpha * instantaneous;
            }
        }
    }

    last = now;
    return frequency;
}

std::string format_components(const double* values, std::size_t count, int width = 10, int precision = 4)
{
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(precision);
    for (std::size_t i = 0; i < count; ++i) {
        if (i != 0) {
            oss << ' ';
        }
        oss << std::setw(width) << values[i];
    }
    return oss.str();
}

struct AngularSummary {
    double axis[3]{0.0, 0.0, 0.0};
    double angle{0.0};
    double omega[3]{0.0, 0.0, 0.0};
    double dt{0.0};
    bool has_axis{false};
    bool has_rate{false};
};

AngularSummary summarize_quaternion(const double q[4], double dt)
{
    AngularSummary summary{};
    summary.dt = dt;

    const double qw = q[3];
    const double clamped = std::clamp(qw, -1.0, 1.0);
    const double angle = 2.0 * std::acos(clamped);
    summary.angle = angle;
    const double sin_half = std::sqrt(std::max(0.0, 1.0 - clamped * clamped));

    if (sin_half > 1e-6) {
        const double inv = 1.0 / sin_half;
        summary.axis[0] = q[0] * inv;
        summary.axis[1] = q[1] * inv;
        summary.axis[2] = q[2] * inv;
        summary.has_axis = true;
    }

    if (dt > 1e-6 && summary.has_axis) {
        const double rate = angle / dt;
        summary.omega[0] = summary.axis[0] * rate;
        summary.omega[1] = summary.axis[1] * rate;
        summary.omega[2] = summary.axis[2] * rate;
        summary.has_rate = true;
    }

    return summary;
}

std::string format_angular_summary(const AngularSummary& summary)
{
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(4);
    oss << "axis=(";
    if (summary.has_axis) {
        oss << format_components(summary.axis, 3);
    } else {
        double nan_vals[3] = {std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::quiet_NaN()};
        oss << format_components(nan_vals, 3);
    }
    oss << ") angle=" << summary.angle << " rad";
    if (summary.has_rate) {
        oss << " omega=(" << format_components(summary.omega, 3) << ") rad/s (dt=" << summary.dt << ')';
    } else {
        double nan_vals[3] = {std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::quiet_NaN(),
                              std::numeric_limits<double>::quiet_NaN()};
        oss << " omega=(" << format_components(nan_vals, 3) << ") rad/s (dt=" << summary.dt << ')';
    }
    return oss.str();
}

void enter_alternate_screen()
{
    std::cout << "\033[?1049h\033[?25l";
}

void leave_alternate_screen()
{
    std::cout << "\033[?25h\033[?1049l";
}

void render_status(TrackerState& state)
{
    std::ostringstream oss;
    oss << "Connection : " << state.connection_status << "\n"
        << "Tracker    : " << state.label << "\n";

    const auto now = std::chrono::steady_clock::now();
    oss << std::fixed;

    oss << "\nPose\n";
    if (state.pose_valid) {
        const auto age = std::chrono::duration<double>(now - state.last_pose).count();
        oss << "  sensor    : " << state.latest_pose.sensor << "\n"
            << "  stamp     : " << time_string(state.latest_pose.msg_time) << " (age "
            << std::setprecision(2) << age << " s)\n"
            << "  position  : " << format_components(state.latest_pose.pos, 3) << "\n"
            << "  quaternion: " << format_components(state.latest_pose.quat, 4) << "\n"
            << "  " << format_frequency(state.pose_frequency) << "\n";
    } else {
        oss << "  <waiting for data>\n";
    }

    oss << "\nTwist\n";
    if (state.twist_valid) {
        const auto age = std::chrono::duration<double>(now - state.last_twist).count();
        const auto angular = summarize_quaternion(state.latest_twist.vel_quat, state.latest_twist.vel_quat_dt);
        oss << "  sensor    : " << state.latest_twist.sensor << "\n"
            << "  stamp     : " << time_string(state.latest_twist.msg_time) << " (age "
            << std::setprecision(2) << age << " s)\n"
            << "  linear    : " << format_components(state.latest_twist.vel, 3) << "\n"
            << "  angular   : " << format_angular_summary(angular) << "\n"
            << "  " << format_frequency(state.twist_frequency) << "\n";
    } else {
        oss << "  <waiting for data>\n";
    }

    oss << "\nAcceleration\n";
    if (state.accel_valid) {
        const auto age = std::chrono::duration<double>(now - state.last_accel).count();
        const auto angular = summarize_quaternion(state.latest_accel.acc_quat, state.latest_accel.acc_quat_dt);
        oss << "  sensor    : " << state.latest_accel.sensor << "\n"
            << "  stamp     : " << time_string(state.latest_accel.msg_time) << " (age "
            << std::setprecision(2) << age << " s)\n"
            << "  linear    : " << format_components(state.latest_accel.acc, 3) << "\n"
            << "  angular   : " << format_angular_summary(angular) << "\n"
            << "  " << format_frequency(state.accel_frequency) << "\n";
    } else {
        oss << "  <waiting for data>\n";
    }

    oss << "\nCtrl+C to exit";

    state.last_rendered = oss.str();
    std::cout << "\033[2J\033[H" << state.last_rendered << std::flush;
}

void VRPN_CALLBACK handle_pose(void* userdata, const vrpn_TRACKERCB t)
{
    auto* state = static_cast<TrackerState*>(userdata);
    const auto now = std::chrono::steady_clock::now();
    update_frequency(now, state->last_pose, state->pose_frequency);
    state->latest_pose = t;
    state->pose_valid = true;
    render_status(*state);
}

void VRPN_CALLBACK handle_twist(void* userdata, const vrpn_TRACKERVELCB t)
{
    auto* state = static_cast<TrackerState*>(userdata);
    const auto now = std::chrono::steady_clock::now();
    update_frequency(now, state->last_twist, state->twist_frequency);
    state->latest_twist = t;
    state->twist_valid = true;
    render_status(*state);
}

void VRPN_CALLBACK handle_accel(void* userdata, const vrpn_TRACKERACCCB t)
{
    auto* state = static_cast<TrackerState*>(userdata);
    const auto now = std::chrono::steady_clock::now();
    update_frequency(now, state->last_accel, state->accel_frequency);
    state->latest_accel = t;
    state->accel_valid = true;
    render_status(*state);
}

} // namespace

int main(int argc, char* argv[])
{
    std::string default_device = "Drone001";
    std::string default_host = "192.168.31.100";

    std::ios::sync_with_stdio(false);
    std::cout << std::unitbuf;
    std::cerr << std::unitbuf;

    std::string tracker_name = default_device + '@' + default_host;
    std::string device_name = default_device;
    std::string host_name = default_host;
    bool tracker_explicit = false;
    auto connect_timeout = std::chrono::seconds{5};

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            print_usage(argv[0], default_device, default_host);
            return 0;
        } else if (arg == "-t" || arg == "--tracker") {
            if (++i >= argc) {
                std::cerr << "Missing value for " << arg << ".\n";
                print_usage(argv[0], default_device, default_host);
                return 1;
            }
            tracker_name = argv[i];
            tracker_explicit = true;
        } else if (arg == "--timeout") {
            if (++i >= argc) {
                std::cerr << "Missing value for --timeout.\n";
                print_usage(argv[0], default_device, default_host);
                return 1;
            }
            char* end = nullptr;
            const long value = std::strtol(argv[i], &end, 10);
            if (end == argv[i] || value <= 0) {
                std::cerr << "Invalid timeout value: " << argv[i] << '\n';
                return 1;
            }
            connect_timeout = std::chrono::seconds{value};
        } else if (arg == "--device") {
            if (++i >= argc) {
                std::cerr << "Missing value for --device.\n";
                print_usage(argv[0], default_device, default_host);
                return 1;
            }
            device_name = argv[i];
        } else if (arg == "--host") {
            if (++i >= argc) {
                std::cerr << "Missing value for --host.\n";
                print_usage(argv[0], default_device, default_host);
                return 1;
            }
            host_name = argv[i];
        } else if (!arg.empty() && arg.front() != '-') {
            tracker_name = arg;
            tracker_explicit = true;
        } else {
            std::cerr << "Unknown option: " << arg << '\n';
            print_usage(argv[0], default_device, default_host);
            return 1;
        }
    }

    if (!tracker_explicit) {
        tracker_name = device_name + '@' + host_name;
    }

    std::unique_ptr<vrpn_Tracker_Remote> tracker;
    try {
        tracker = std::make_unique<vrpn_Tracker_Remote>(tracker_name.c_str());
    } catch (...) {
        std::cerr << "Failed to create VRPN tracker client. Check tracker name and build configuration.\n";
        return 1;
    }

    auto* connection = tracker->connectionPtr();
    if (connection == nullptr) {
        std::cerr << "Tracker connection pointer is null. Aborting.\n";
        return 1;
    }

    bool alt_screen_active = false;
    enter_alternate_screen();
    alt_screen_active = true;
    auto leave_alt_screen = [&](const std::string& snapshot) {
        if (alt_screen_active) {
            leave_alternate_screen();
            alt_screen_active = false;
        }
        if (!snapshot.empty()) {
            std::cout << snapshot << std::endl;
        }
    };

    TrackerState state{};
    state.label = device_name;
    {
        std::ostringstream status;
        status << "Connecting to " << tracker_name << " (timeout " << connect_timeout.count() << "s)";
        state.connection_status = status.str();
        render_status(state);
    }
    tracker->register_change_handler(&state, handle_pose);
    tracker->register_change_handler(&state, handle_twist);
    tracker->register_change_handler(&state, handle_accel);

    std::signal(SIGINT, signal_handler);

    const auto deadline = std::chrono::steady_clock::now() + connect_timeout;
    while (g_should_run && std::chrono::steady_clock::now() < deadline && !connection->connected()) {
        tracker->mainloop();
        connection->mainloop();
        vrpn_SleepMsecs(50);
    }

    if (!connection->connected()) {
        std::ostringstream status;
        status << "Connection failed: timeout after " << connect_timeout.count() << "s";
        state.connection_status = status.str();
        render_status(state);
        std::cerr << "Unable to connect to tracker within " << connect_timeout.count()
                  << " seconds. Please verify the server is reachable.\n";
        leave_alt_screen(state.last_rendered);
        return 2;
    }

    state.connection_status = "Connected to " + tracker_name + " (listening)";
    render_status(state);

    auto last_pose_warning = std::chrono::steady_clock::now();
    bool pose_warning_printed = false;

    while (g_should_run) {
        tracker->mainloop();
        connection->mainloop();

        const auto now = std::chrono::steady_clock::now();
        if (state.last_pose.time_since_epoch().count() != 0) {
            const auto elapsed_pose = now - state.last_pose;

            if (elapsed_pose > std::chrono::seconds{3}) {
                if (!pose_warning_printed || (now - last_pose_warning) > std::chrono::seconds{3}) {
                    std::cerr << '[' << now_string() << "] No pose updates for "
                              << std::chrono::duration_cast<std::chrono::seconds>(elapsed_pose).count()
                              << "s. Check server status.\n";
                    last_pose_warning = now;
                    pose_warning_printed = true;
                }
            } else {
                pose_warning_printed = false;
            }
        }

        if (!connection->connected()) {
            state.connection_status = "Connection lost, attempting reconnect...";
            render_status(state);
            std::cerr << '[' << now_string() << "] Connection lost. Attempting to reconnect...\n";
            while (g_should_run && !connection->connected()) {
                tracker->mainloop();
                connection->mainloop();
                vrpn_SleepMsecs(250);
            }
            if (!g_should_run) {
                break;
            }
            state.connection_status = "Reconnected to " + tracker_name;
            render_status(state);
            std::cerr << '[' << now_string() << "] Reconnected to tracker.\n";
        }

        vrpn_SleepMsecs(5);
    }

    state.connection_status = "Shutting down";
    render_status(state);
    tracker->unregister_change_handler(&state, handle_pose);
    tracker->unregister_change_handler(&state, handle_twist);
    tracker->unregister_change_handler(&state, handle_accel);
    leave_alt_screen(state.last_rendered);
    return 0;
}
