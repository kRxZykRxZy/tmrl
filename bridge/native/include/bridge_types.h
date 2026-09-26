#pragma once

#include <cstdint>
#include <string>
#include <array>

namespace tmrl {

constexpr std::uint32_t kProtocolVersion = 1;
constexpr std::uint32_t kMaxAiSlots = 50;

enum class ResultCode : std::uint32_t {
    Ok = 0,
    NotConnected,
    WrongBuild,
    CapabilityUnavailable,
    InvalidHandle,
    InvalidArgument,
    SessionMismatch,
    EntityLimit,
    QueueFull,
    GameNotReady,
    NativeCallFailed,
    HumanPlayerProtected,
    StaleSequence,
    InternalError,
};

enum class CameraMode : std::uint32_t {
    Chase = 0,
    Cockpit = 1,
    Hood = 2,
    Wheel = 3,
    Orbit = 4,
};

enum class ControlMode : std::uint32_t {
    NativePhysics = 0,
    PoseDebug = 1,
};

struct Vec3 {
    float x{};
    float y{};
    float z{};
};

struct Quat {
    float x{};
    float y{};
    float z{};
    float w{1.0f};
};

struct VehicleHandle {
    std::uint64_t session{};
    std::uint32_t slot{};
    std::uint32_t generation{};
};

struct CameraState {
    std::string camera_id;
    std::string vehicle_id;
    CameraMode mode{CameraMode::Chase};
    Vec3 position{};
    Vec3 look_at{};
    float yaw{};
    float pitch{};
    float roll{};
    float fov_deg{90.0f};
    float distance{6.0f};
    float height{2.0f};
    bool active{};
    bool native_supported{};
};

struct VehicleRecord {
    VehicleHandle handle{};
    std::string vehicle_id;
    std::string camera_id;
    std::uint32_t agent_id{};
    ControlMode control_mode{ControlMode::NativePhysics};
    bool active{};
    bool native_object_valid{};
    bool camera_active{};
    std::uintptr_t native_object{};
};

} // namespace tmrl
