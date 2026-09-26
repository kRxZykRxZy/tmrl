#pragma once

#include "bridge_state.h"
#include <atomic>
#include <windows.h>

namespace tmrl {

class BridgeServer {
public:
    BridgeServer();
    ~BridgeServer();

    void run();
    void stop();

private:
    std::atomic_bool stopping_{false};
    BridgeState state_{};

    void serve_client(HANDLE pipe);
    static bool read_frame(HANDLE pipe, std::uint16_t& message, std::uint64_t& sequence, std::string& body);
    static bool write_frame(HANDLE pipe, std::uint16_t message, std::uint64_t sequence, const std::string& body);

    static std::string json_ok(const std::string& extra);
    static std::string json_error(ResultCode code, const char* detail);
};

} // namespace tmrl
