#include "bridge_state.h"

#include <sstream>

namespace tmrl {

BridgeState::BridgeState() {
    for (auto& vehicle : vehicles_) {
        vehicle.active = false;
        vehicle.native_object_valid = false;
        vehicle.camera_active = false;
    }
}

const char* BridgeState::bridge_version() const {
    return "0.1.0-native-bridge";
}

const char* BridgeState::build_id() const {
    return "UNVERIFIED";
}

bool BridgeState::supported_build() const {
    // Write-capable native vehicle operations remain disabled until an exact
    // TmForever.exe build profile has been validated.
    return false;
}

std::string BridgeState::make_vehicle_id(std::uint32_t agent_id) {
    return "ai_thread_" + std::to_string(agent_id + 1);
}

std::string BridgeState::make_camera_id(std::uint32_t agent_id) {
    return "ai_camera_" + std::to_string(agent_id + 1);
}

bool BridgeState::session_owns(const VehicleRecord& vehicle, std::uint64_t session) const {
    return vehicle.active && vehicle.handle.session == session;
}

ResultCode BridgeState::create_ai(
    std::uint64_t session,
    std::uint32_t agent_id,
    VehicleHandle& out
) {
    std::scoped_lock lock(mutex_);
    if (!supported_build()) {
        return ResultCode::WrongBuild;
    }
    if (agent_id >= kMaxAiSlots) {
        return ResultCode::InvalidArgument;
    }

    VehicleRecord& slot = vehicles_[agent_id];
    if (slot.active) {
        return ResultCode::EntityLimit;
    }

    slot.handle = VehicleHandle{session, agent_id, next_generation_++};
    slot.vehicle_id = make_vehicle_id(agent_id);
    slot.camera_id = make_camera_id(agent_id);
    slot.agent_id = agent_id;
    slot.active = true;
    slot.native_object_valid = false;

    out = slot.handle;
    return ResultCode::Ok;
}

ResultCode BridgeState::destroy_ai(std::uint64_t session, const VehicleHandle& handle) {
    std::scoped_lock lock(mutex_);
    if (handle.slot >= kMaxAiSlots) {
        return ResultCode::InvalidHandle;
    }

    VehicleRecord& slot = vehicles_[handle.slot];
    if (!session_owns(slot, session) ||
        slot.handle.generation != handle.generation) {
        return ResultCode::InvalidHandle;
    }

    slot.active = false;
    slot.native_object_valid = false;
    slot.camera_active = false;
    return ResultCode::Ok;
}

ResultCode BridgeState::destroy_all(std::uint64_t session) {
    std::scoped_lock lock(mutex_);
    for (auto& slot : vehicles_) {
        if (session_owns(slot, session)) {
            slot.active = false;
            slot.native_object_valid = false;
            slot.camera_active = false;
        }
    }
    cameras_.release();
    return ResultCode::Ok;
}

ResultCode BridgeState::camera_target(
    std::uint64_t session,
    const VehicleHandle& handle
) {
    std::scoped_lock lock(mutex_);
    if (handle.slot >= kMaxAiSlots) {
        return ResultCode::InvalidHandle;
    }

    VehicleRecord& slot = vehicles_[handle.slot];
    if (!session_owns(slot, session) ||
        slot.handle.generation != handle.generation) {
        return ResultCode::InvalidHandle;
    }

    auto result = cameras_.target(slot);
    slot.camera_active = result == ResultCode::Ok;
    return result;
}

ResultCode BridgeState::camera_release(std::uint64_t session) {
    std::scoped_lock lock(mutex_);
    for (const auto& slot : vehicles_) {
        if (slot.active && slot.handle.session == session) {
            break;
        }
    }
    return cameras_.release();
}

CameraState BridgeState::camera_state(
    std::uint64_t session,
    const VehicleHandle& handle
) const {
    std::scoped_lock lock(mutex_);
    CameraState empty;
    if (handle.slot >= kMaxAiSlots) {
        return empty;
    }

    const VehicleRecord& slot = vehicles_[handle.slot];
    if (!session_owns(slot, session) ||
        slot.handle.generation != handle.generation) {
        return empty;
    }

    return cameras_.get(slot);
}

const VehicleRecord* BridgeState::get_vehicle(std::uint32_t slot) const {
    if (slot >= kMaxAiSlots) {
        return nullptr;
    }
    return &vehicles_[slot];
}

} // namespace tmrl
