#include "bridge_server.h"

#include <cstdlib>
#include <cstring>
#include <string>

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
constexpr std::uint32_t kMaxFrame = 1024u * 1024u;

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
    const std::string needle = std::string("\"") + key + "\"";
    const auto key_pos = body.find(needle);
    if (key_pos == std::string::npos) return {};
    const auto colon = body.find(':', key_pos + needle.size());
    if (colon == std::string::npos) return {};
    const auto begin = body.find('"', colon + 1);
    if (begin == std::string::npos) return {};
    const auto end = body.find('"', begin + 1);
    if (end == std::string::npos) return {};
    return body.substr(begin + 1, end - begin - 1);
}

std::uint32_t find_json_u32(const std::string& body, const char* key,
                            std::uint32_t fallback = 0) {
    const std::string needle = std::string("\"") + key + "\"";
    const auto key_pos = body.find(needle);
    if (key_pos == std::string::npos) return fallback;
    const auto colon = body.find(':', key_pos + needle.size());
    if (colon == std::string::npos) return fallback;

    const char* begin = body.c_str() + colon + 1;
    while (*begin == ' ' || *begin == '\t') ++begin;

    char* end = nullptr;
    const auto value = std::strtoul(begin, &end, 10);
    return end == begin ? fallback : static_cast<std::uint32_t>(value);
}

std::string json_ok(const std::string& extra = {}) {
    if (extra.empty()) return R"({"ok":true})";
    return std::string(R"({"ok":true,)") + extra + "}";
}

std::string json_error(tmrl::ResultCode code, const char* detail) {
    return std::string(R"({"ok":false,"code":")") +
           result_name(code) +
           R"(","message":")" +
           detail +
           R"("})";
}

} // namespace

namespace tmrl {

BridgeServer::BridgeServer() = default;
BridgeServer::~BridgeServer() = default;

void BridgeServer::stop() {
    stopping_.store(true);
}

bool BridgeServer::read_frame(
    HANDLE pipe,
    std::uint16_t& message,
    std::uint64_t& sequence,
    std::string& body) {
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
    if (header.length != 0) {
        if (!ReadFile(pipe, body.data(), header.length, &read, nullptr) ||
            read != header.length) {
            return false;
        }
    }

    message = header.message;
    sequence = header.sequence;
    return true;
}

bool BridgeServer::write_frame(
    HANDLE pipe,
    std::uint16_t message,
    std::uint64_t sequence,
    const std::string& body) {
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

    if (!body.empty()) {
        if (!WriteFile(pipe, body.data(), static_cast<DWORD>(body.size()), &written, nullptr) ||
            written != body.size()) {
            return false;
        }
    }

    return true;
}

void BridgeServer::serve_client(HANDLE pipe) {
    std::uint16_t message = 0;
    std::uint64_t sequence = 0;
    std::string body;
    constexpr std::uint64_t kSession = 0x544D524C00000001ull;

    while (!stopping_.load() && read_frame(pipe, message, sequence, body)) {
        std::string response;

        switch (message) {
            case kHello:
                response = json_ok(
                    R"("protocol_version":1,"bridge_version":"0.1.0-native-bridge",)"
                    R"("session_id":"1469598103934665603","supported_build":false,)"
                    R"("native_vehicle_spawn":false,"native_vehicle_physics":false,)"
                    R"("native_vehicle_input":false,"native_vehicle_pose":false,)"
                    R"("native_telemetry":false,"native_camera":false,"max_ai_slots":50,)"
                    R"("build_id":"UNVERIFIED","read_only_reason":"No verified TmForever.exe build profile is installed")"
                );
                break;

            case kCapabilities:
                response = json_ok(
                    R"("supported_build":false,"native_vehicle_spawn":false,)"
                    R"("native_vehicle_physics":false,"native_vehicle_input":false,)"
                    R"("native_vehicle_pose":false,"native_telemetry":false,)"
                    R"("native_camera":false,"max_ai_slots":50,)"
                    R"("bridge_version":"0.1.0-native-bridge","protocol_version":1,)"
                    R"("build_id":"UNVERIFIED","read_only_reason":"No verified TmForever.exe build profile is installed")"
                );
                break;

            case kPing:
                response = json_ok(
                    R"("bridge_version":"0.1.0-native-bridge","game_thread":"not_attached","native_mode":false)"
                );
                break;

            case kStartSession:
                response = json_ok(R"("session_id":"1469598103934665603")");
                break;

            case kStopSession:
                state_.destroy_all(kSession);
                response = json_ok();
                break;

            case kCreateAgent: {
                const auto agent_id = find_json_u32(body, "agent_id");
                VehicleHandle handle{};
                const auto code = state_.create_ai(kSession, agent_id, handle);
                if (code != ResultCode::Ok) {
                    response = json_error(
                        code,
                        "native vehicle creation is not enabled for this build");
                } else {
                    response = json_ok(
                        std::string(R"("slot_id":)") + std::to_string(handle.slot) +
                        R"(,"generation":)" + std::to_string(handle.generation) +
                        R"(,"vehicle_id":")" +
                        "ai_thread_" + std::to_string(agent_id + 1) + R"(")"
                    );
                }
                break;
            }

            case kDestroyAgent: {
                const auto slot = find_json_u32(body, "slot_id");
                const auto generation = find_json_u32(body, "generation");
                const VehicleHandle handle{kSession, slot, generation};
                response = json_ok();
                state_.destroy_ai(kSession, handle);
                break;
            }

            case kDestroyAll:
                state_.destroy_all(kSession);
                response = json_ok();
                break;

            case kCameraTarget:
            case kCameraState: {
                const auto slot = find_json_u32(body, "slot_id");
                const auto generation = find_json_u32(body, "generation");
                const VehicleHandle handle{kSession, slot, generation};
                const auto code = state_.camera_target(kSession, handle);

                if (code != ResultCode::Ok) {
                    response = json_error(code, "camera target handle is invalid");
                } else {
                    const auto* vehicle = state_.get_vehicle(slot);
                    const std::string camera_id =
                        vehicle ? vehicle->camera_id
                                : "ai_camera_" + std::to_string(slot + 1);
                    const std::string vehicle_id =
                        vehicle ? vehicle->vehicle_id
                                : "ai_thread_" + std::to_string(slot + 1);

                    response = json_ok(
                        std::string(R"("camera_id":")") + camera_id +
                        R"(","vehicle_id":")" + vehicle_id +
                        R"(","mode":"chase","fov_deg":90.0,"distance":6.0,"height":2.0,)"
                        R"("active":true,"native_supported":false)"
                    );
                }
                break;
            }

            case kCameraRelease:
                state_.camera_release(kSession);
                response = json_ok();
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
            LR"(\.pipeTMRL.TMNF.Bridge.v1)",
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

        const BOOL connected = ConnectNamedPipe(pipe, nullptr)
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
