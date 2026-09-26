cmake_minimum_required(VERSION 3.20)
project(tmrl_tmnf_bridge LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "TMNF bridge is Windows-only")
endif()

add_library(tmrl_tmnf_bridge SHARED
    src/dllmain.cpp
    src/bridge_server.cpp
    src/bridge_state.cpp
    src/camera_manager.cpp
)

target_compile_features(tmrl_tmnf_bridge PRIVATE cxx_std_17)
target_compile_definitions(tmrl_tmnf_bridge PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
target_include_directories(tmrl_tmnf_bridge PRIVATE include)

target_link_libraries(tmrl_tmnf_bridge PRIVATE
    kernel32
    user32
)
