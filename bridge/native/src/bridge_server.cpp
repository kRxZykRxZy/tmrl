#include "bridge_server.h"

#include <cstring>
#include <cstdlib>
#include <sstream>
#include <vector>

namespace {
#pragma pack(push, 1)
struct Header {
    char magic[4];
    std::uint16_t version;
    std::uint16_t message;
    std::uint32_t flags;
    std::uint64_t sequence;
    std::uint32_t length;
};
#pragma pack(pop)

constexpr std::uint16_t kHello = 0x0001;
constexpr std::uint16_t kCapabilities = 0x0002;
constexpr std::uint16_t kPing = 0x0003;
constexpr std::uint16_t kStartSession = 0x0010;
constexpr std::uint16_t kStopSession = 0x0011;
constexpr std::uint16_t kCreateAgent = 0x0100;
constexpr std::uint16_t kDestroyAgent = 0x0102;
constexpr std::uint16_t kDestroyAll = 0x0103;
constexpr std::uint16_t kCameraTarget = 0x0500;
constexpr std::uint16_t kCameraRelease = 0x0501;
constexpr std::uint16_t kCameraState = 0x0502;
constexpr std::uint16_t kMaxFrame = 1024 * 1024;

std::string result_name(tmrl::ResultCode code) {
    switch (code) {
        case tmrl::ResultCode::Ok: return "OK";
        case tmrl::ResultCode::WrongBuild: return "WRONG_BUILD";
        case tmrl::ResultCode::InvalidHandle: return "INVALID_HANDLE";
        case tmrl::ResultCode::InvalidArgument: return "INVALID_ARGUMENT";
        case tmrl::ResultCode::EntityLimit: return "ENTITY_LIMIT";
        case tmrl::ResultCode::HumanPlayerProtected: return "HUMAN_PLAYER_PROTECTED";
        default: return "INTERNAL_ERROR";
    }
}

std::string find_json_string(const std::string& body, const char* key) {
    const std::string needle = std::string(""") + key + """;
    auto pos = body.find(needle);
    if (pos == std::string::npos) return {};
    pos = body.find(':', pos);
    if (pos == std::string::npos) return {};
    pos = body.find('"', pos);
    if (pos == std::string::npos) return {};
    auto end = body.find('"', pos + 1);
    if (end == std::string::npos) return {};
    return body.substr(pos + 1, end - pos - 1);
}

std::uint32_t find_json_u32(const std::string& body, const char* key, std::uint32_t fallback = 0) {
    const std::string needle = std::string(""") + key + """;
    auto pos = body.find(needle);
    if (pos == std::string::npos) return fallback;
    pos = body.find(':', pos);
    if (pos == std::string::npos) return fallback;
    ++pos;
    while (pos < body.size() && (body[pos] == ' ' || body[pos] == '\t')) ++pos;
    char* end = nullptr;
    auto value = std::strtoul(body.c_str() + pos, &end, 10);
    return end == body.c_str() + pos ? fallback : static_cast<std::uint32_t>(value);
}

std::uint64_t find_json_u64(const std::string& body, const char* key, std::uint64_t fallback = 0) {
    const std::string needle = std::string(""") + key + """;
    auto pos = body.find(needle);
    if (pos == std::string::npos) return fallback;
    pos = body.find(':', pos);
    if (pos == std::string::npos) return fallback;
    ++pos;
    while (pos < body.size() && (body[pos] == ' ' || body[pos] == '\t')) ++pos;
    char* end = nullptr;
    auto value = std::strtoull(body.c_str() + pos, &end, 10);
    return end == body.c_str() + pos ? fallback : static_cast<std::uint64_t>(value);
}

std::string json_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char ch : value) {
        if (ch == '"' || ch == '\') out.push_back('\');
        out.push_back(ch);
    }
    return out;
}

} // namespace

namespace tmrl {

BridgeServer::BridgeServer() = default;

BridgeServer::~BridgeServer() = default;

void BridgeServer::stop() {
    stopping_.store(true);
}

std::string BridgeServer::json_ok(const std::string& extra) {
    return std::string("{"ok":true,") + extra + "}";
}

std::string BridgeServer::json_error(ResultCode code, const char* detail) {
    return std::string("{"ok":false,"code":"") +
           result_name(code) +
           "","message":"" +
           detail +
           ""}";
}

bool BridgeServer::read_frame(
    HANDLE pipe,
    std::uint16_t& message,
    std::uint64_t& sequence,
    std::string& body
) {
    Header header{};
    DWORD read = 0;
    if (!ReadFile(pipe, &header, sizeof(header), &read, nullptr) ||
        read != sizeof(header)) {
        return false;
    }

    if (std::memcmp(header.magic, "TMRB", 4) != 0 ||
        header.version != kProtocolVersion ||
        header.length > kMaxFrame) {
        return false;
    }

    body.resize(header.length);
    if (header.length == 0) {
        body.clear();
        message = header.message;
        sequence = header.sequence;
        return true;
    }

    if (!ReadFile(pipe, body.data(), header.length, &read, nullptr) ||
        read != header.length) {
        return false;
    }

    message = header.message;
    sequence = header.sequence;
    return true;
}

bool BridgeServer::write_frame(
    HANDLE pipe,
    std::uint16_t message,
    std::uint64_t sequence,
    const std::string& body
) {
    Header header{};
    std::memcpy(header.magic, "TMRB", 4);
    header.version = kProtocolVersion;
    header.message = message;
    header.sequence = sequence;
    header.length = static_cast<std::uint32_t>(body.size());

    DWORD written = 0;
    if (!WriteFile(pipe, &header, sizeof(header), &written, nullptr) ||
        written != sizeof(header)) {
        return false;
    }

    if (!body.empty() &&
        (!WriteFile(pipe, body.data(), static_cast<DWORD>(body.size()), &written, nullptr) ||
         written != body.size())) {
        return false;
    }

    return true;
}

void BridgeServer::serve_client(HANDLE pipe) {
    std::uint16_t message = 0;
    std::uint64_t sequence = 0;
    std::string body;
    std::uint64_t session = 0x544D524C00000001ull;

    while (!stopping_.load() && read_frame(pipe, message, sequence, body)) {
        std::string response;

        switch (message) {
            case kHello:
                response = json_ok(
                    ""protocol_version":1,"
                    ""bridge_version":"0.1.0-native-bridge","
                    ""session_id":"1469598103934665603","
                    ""supported_build":false,"
                    ""native_vehicle_spawn":false,"
                    ""native_vehicle_physics":false,"
                    ""native_vehicle_input":false,"
                    ""native_vehicle_pose":false,"
                    ""native_telemetry":false,"
                    ""native_camera":false,"
                    ""max_ai_slots":50,"
                    ""build_id":"UNVERIFIED","
                    ""read_only_reason":"No verified TmForever.exe build profile is installed""
                );
                break;

            case kCapabilities:
                response = json_ok(
                    ""supported_build":false,"
                    ""native_vehicle_spawn":false,"
                    ""native_vehicle_physics":false,"
                    ""native_vehicle_input":false,"
                    ""native_vehicle_pose":false,"
                    ""native_telemetry":false,"
                    ""native_camera":false,"
                    ""max_ai_slots":50,"
                    ""bridge_version":"0.1.0-native-bridge","
                    ""protocol_version":1,"
                    ""build_id":"UNVERIFIED","
                    ""read_only_reason":"No verified TmForever.exe build profile is installed""
                );
                break;

            case kPing:
                response = json_ok(
                    ""bridge_version":"0.1.0-native-bridge","
                    ""game_thread":"not_attached","
                    ""native_mode":false"
                );
                break;

            case kStartSession:
                response = json_ok(
                    ""session_id":"1469598103934665603""
                );
                break;

            case kStopSession:
                state_.destroy_all(session);
                response = json_ok("");
                break;

            case kCreateAgent: {
                std::uint32_t agent_id = find_json_u32(body, "agent_id");
                VehicleHandle handle{};
                auto code = state_.create_ai(session, agent_id, handle);
                if (code != ResultCode::Ok) {
                    response = json_error(code, "native vehicle creation is not enabled for this build");
                } else {
                    response = json_ok(
                        std::string(""slot_id":") + std::to_string(handle.slot) +
                        ","generation":" + std::to_string(handle.generation) +
                        ","vehicle_id":"ai_thread_" + std::to_string(agent_id + 1) + """
                    );
                }
                break;
            }

            case kDestroyAgent:
                response = json_ok("");
                break;

            case kDestroyAll:
                state_.destroy_all(session);
                response = json_ok("");
                break;

            case kCameraTarget:
            case kCameraState: {
                std::uint32_t slot = find_json_u32(body, "slot_id");
                std::uint32_t generation = find_json_u32(body, "generation");
                VehicleHandle handle{session, slot, generation};
                auto code = state_.camera_target(session, handle);
                if (code != ResultCode::Ok) {
                    response = json_error(code, "camera target handle is invalid");
                } else {
                    const auto* vehicle = state_.get_vehicle(slot);
                    response = json_ok(
                        std::string(""camera_id":"") +
                        (vehicle ? vehicle->camera_id : "ai_camera_" + std::to_string(slot + 1)) +
                        "","vehicle_id":"" +
                        (vehicle ? vehicle->vehicle_id : "ai_thread_" + std::to_string(slot + 1)) +
                        "","mode":"chase","fov_deg":90.0,"distance":6.0,"height":2.0,"
                        ""active":true,"native_supported":false"
                    );
                }
                break;
            }

            case kCameraRelease:
                state_.camera_release(session);
                response = json_ok("");
                break;

            default:
                response = json_error(ResultCode::InvalidArgument, "unknown bridge message");
                break;
        }

        if (!write_frame(pipe, message, sequence, response)) {
            break;
        }
    }

    FlushFileBuffers(pipe);
    DisconnectNamedPipe(pipe);
    CloseHandle(pipe);
}

void BridgeServer::run() {
    while (!stopping_.load()) {
        HANDLE pipe = CreateNamedPipeW(
            L"\\.\pipe\TMRL.TMNF.Bridge.v1",
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
            1,
            1024 * 1024,
            1024 * 1024,
            0,
            nullptr
        );

        if (pipe == INVALID_HANDLE_VALUE) {
            return;
        }

        BOOL connected = ConnectNamedPipe(pipe, nullptr)
            ? TRUE
            : (GetLastError() == ERROR_PIPE_CONNECTED);

        if (connected) {
            serve_client(pipe);
        } else {
            CloseHandle(pipe);
        }
    }
}

} // namespace tmrl
