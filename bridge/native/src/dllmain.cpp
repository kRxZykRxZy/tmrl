#include "bridge_server.h"
#include <windows.h>

namespace {
tmrl::BridgeServer* g_server = nullptr;
HANDLE g_thread = nullptr;
}

DWORD WINAPI BridgeThread(LPVOID) {
    tmrl::BridgeServer server;
    g_server = &server;
    server.run();
    g_server = nullptr;
    return 0;
}

BOOL APIENTRY DllMain(HMODULE h_module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h_module);
        g_thread = CreateThread(nullptr, 0, BridgeThread, nullptr, 0, nullptr);
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_server) {
            g_server->stop();
        }
    }
    return TRUE;
}
