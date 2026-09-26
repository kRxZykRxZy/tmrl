#include "camera_manager.h"

#include <cmath>

namespace tmrl {

CameraManager::CameraManager() = default;

CameraState CameraManager::default_state(const VehicleRecord& vehicle) {
    CameraState state;
    state.camera_id = vehicle.camera_id;
    state.vehicle_id = vehicle.vehicle_id;
    state.mode = CameraMode::Chase;
    state.fov_deg = 90.0f;
    state.distance = 6.0f;
    state.height = 2.0f;
    state.active = false;

    // "native_supported" becomes true only when the verified TMNF camera
    // adapter has been resolved for the exact executable build.
    state.native_supported = false;
    return state;
}

ResultCode CameraManager::target(const VehicleRecord& vehicle) {
    std::scoped_lock lock(mutex_);
    auto [it, inserted] = states_.try_emplace(vehicle.handle.slot, default_state(vehicle));
    if (inserted) {
        it->second.camera_id = vehicle.camera_id;
        it->second.vehicle_id = vehicle.vehicle_id;
    }

    for (auto& item : states_) {
        item.second.active = false;
    }

    it->second.active = true;
    active_slot_ = vehicle.handle.slot;
    active_vehicle_id_ = vehicle.vehicle_id;
    has_target_ = true;

    // The target exists even before the build-specific native camera hook is
    // enabled; callers can therefore display the requested per-AI camera ID.
    return ResultCode::Ok;
}

ResultCode CameraManager::release() {
    std::scoped_lock lock(mutex_);
    for (auto& item : states_) {
        item.second.active = false;
    }
    active_vehicle_id_.clear();
    has_target_ = false;
    return ResultCode::Ok;
}

CameraState CameraManager::get(const VehicleRecord& vehicle) const {
    std::scoped_lock lock(mutex_);
    auto it = states_.find(vehicle.handle.slot);
    if (it != states_.end()) {
        return it->second;
    }
    return default_state(vehicle);
}

void CameraManager::update_from_vehicle(
    const VehicleRecord& vehicle,
    Vec3 vehicle_position,
    float vehicle_yaw,
    float vehicle_pitch,
    float vehicle_roll,
    float /*speed*/
) {
    std::scoped_lock lock(mutex_);
    auto& state = states_[vehicle.handle.slot];
    if (state.camera_id.empty()) {
        state = default_state(vehicle);
    }

    state.yaw = vehicle_yaw;
    state.pitch = vehicle_pitch;
    state.roll = vehicle_roll;

    const float sy = std::sin(vehicle_yaw);
    const float cy = std::cos(vehicle_yaw);

    // Generic chase-camera transform. Once the build-specific camera adapter
    // is validated, these values are replaced with the game's actual camera
    // state rather than being used as a fake render.
    state.position = {
        vehicle_position.x - sy * state.distance,
        vehicle_position.y + state.height,
        vehicle_position.z - cy * state.distance,
    };

    state.look_at = {
        vehicle_position.x,
        vehicle_position.y + 0.8f,
        vehicle_position.z,
    };
}

const std::string& CameraManager::active_vehicle_id() const {
    return active_vehicle_id_;
}

bool CameraManager::has_active_target() const {
    return has_target_;
}

} // namespace tmrl
