#pragma once

#include "bridge_types.h"
#include <unordered_map>
#include <mutex>

namespace tmrl {

class CameraManager {
public:
    CameraManager();

    ResultCode target(const VehicleRecord& vehicle);
    ResultCode release();

    CameraState get(const VehicleRecord& vehicle) const;

    void update_from_vehicle(
        const VehicleRecord& vehicle,
        Vec3 vehicle_position,
        float vehicle_yaw,
        float vehicle_pitch,
        float vehicle_roll,
        float speed
    );

    const std::string& active_vehicle_id() const;
    bool has_active_target() const;

private:
    mutable std::mutex mutex_;
    std::unordered_map<std::uint32_t, CameraState> states_;
    std::uint32_t active_slot_{};
    bool has_target_{false};
    std::string active_vehicle_id_;

    static CameraState default_state(const VehicleRecord& vehicle);
};

} // namespace tmrl
