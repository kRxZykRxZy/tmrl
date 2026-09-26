#pragma once

#include "bridge_types.h"
#include "camera_manager.h"

#include <array>
#include <mutex>
#include <string>

namespace tmrl {

class BridgeState {
public:
    BridgeState();

    const char* bridge_version() const;
    const char* build_id() const;
    bool supported_build() const;

    ResultCode create_ai(std::uint64_t session,
                         std::uint32_t agent_id,
                         VehicleHandle& out);
    ResultCode destroy_ai(std::uint64_t session, const VehicleHandle& handle);
    ResultCode destroy_all(std::uint64_t session);

    ResultCode camera_target(std::uint64_t session, const VehicleHandle& handle);
    ResultCode camera_release(std::uint64_t session);
    CameraState camera_state(std::uint64_t session, const VehicleHandle& handle) const;

    const VehicleRecord* get_vehicle(std::uint32_t slot) const;

private:
    mutable std::mutex mutex_;
    std::array<VehicleRecord, kMaxAiSlots> vehicles_{};
    CameraManager cameras_{};
    std::uint32_t next_generation_{1};

    bool session_owns(const VehicleRecord& vehicle, std::uint64_t session) const;
    static std::string make_vehicle_id(std::uint32_t agent_id);
    static std::string make_camera_id(std::uint32_t agent_id);
};

} // namespace tmrl
