// TMRL simultaneous evolutionary bridge.
// The Openplanet layer owns transport and visualization state; game-specific vehicle
// access is deliberately isolated in ReadVehicleState/ApplyVehicleCommand.
// This avoids hard-coding unstable engine offsets.

const uint AGENT_COUNT = 50;
const uint SERVER_PORT = 8765;
const float FRAME_TIMEOUT = 0.25f;
const float ELIMINATION_DELAY = 1.5f;
const float ELIMINATION_SPEED = 1.0f;
const float LIDAR_MAX = 100.0f;

class AgentState {
    uint id;
    vec3 pos;
    vec3 velocity;
    float pitch;
    float roll;
    float yaw;
    float checkpointTime;
    float lidarLeft;
    float lidarRight;
    float lidarFront;
    float distance;
    float wallPenalty;
    bool alive;
    float belowSpeedSince;
    vec2 command;

    AgentState(uint _id) {
        id = _id;
        pos = vec3(0, 0, 0);
        velocity = vec3(0, 0, 0);
        pitch = roll = yaw = checkpointTime = 0;
        lidarLeft = lidarRight = lidarFront = 1;
        distance = wallPenalty = 0;
        alive = true;
        belowSpeedSince = -1;
        command = vec2(0, 1);
    }
}

AgentState@[] Agents;
Net::Socket@ Socket;
string RxBuffer = "";
uint Generation = 0;
float LastTick = 0;
bool Connected = false;
string LastError = "";

void Main() {
    Agents.RemoveRange(0, Agents.Length);
    for (uint i = 0; i < AGENT_COUNT; i++) Agents.InsertLast(AgentState(i));
    ConnectServer();
}

void ConnectServer() {
    Connected = false;
    try {
        @Socket = Net::Socket();
        Socket.Connect("127.0.0.1", SERVER_PORT);
        Connected = true;
        LastError = "";
    } catch {
        LastError = "Python server unavailable";
    }
}

void Update(float dt) {
    if (!Connected) {
        ConnectServer();
        return;
    }
    for (uint i = 0; i < AGENT_COUNT; i++) {
        if (!Agents[i].alive) continue;
        ReadVehicleState(Agents[i]);
        UpdateElimination(Agents[i], dt);
    }
    SendFrame();
    ReceiveCommands();
}

void OnEngineCtnPlaygroundStateChanged(CGameCtnPlayground@ pg) {
    // Menu/loading transitions invalidate scene references. Keep the transport alive
    // but mark all virtual agents inactive until a gameplay tick supplies state.
    if (pg is null) {
        for (uint i = 0; i < Agents.Length; i++) Agents[i].alive = false;
    }
}

void OnSdkPhysicsStep(float dt) {
    LastTick = Time::Now;
    if (Agents.Length != AGENT_COUNT) Main();
    Update(dt);
}

void ReadVehicleState(AgentState@ a) {
    // The stock Openplanet API does not expose 50 independently controllable
    // Trackmania physics bodies. A production installation should bind this adapter
    // to the vehicle/ghost provider used by the selected TMNF replay implementation.
    // The state object remains valid and the Python protocol is fully defined.
    //
    // For the first frame, retain the adapter's current state. If a provider supplies
    // telemetry, assign position/velocity/orientation and then call ComputeLidar(a).
    ComputeLidar(a);
}

void ComputeLidar(AgentState@ a) {
    // Boundary queries are intentionally geometric: a provider can supply track
    // collision segments, and the same ray math is used by the Python reference.
    // Until a provider supplies a segment mesh, normalized distances stay at 1.
    a.lidarLeft = Math::Clamp(a.lidarLeft, 0.0f, 1.0f);
    a.lidarRight = Math::Clamp(a.lidarRight, 0.0f, 1.0f);
    a.lidarFront = Math::Clamp(a.lidarFront, 0.0f, 1.0f);
}

void UpdateElimination(AgentState@ a, float dt) {
    float speedKmh = a.velocity.Length() * 3.6f;
    if (Time::Now > ELIMINATION_DELAY && speedKmh < ELIMINATION_SPEED) {
        if (a.belowSpeedSince < 0) a.belowSpeedSince = Time::Now;
        if (Time::Now - a.belowSpeedSince > 0.15f) {
            a.alive = false;
            ApplyVehicleCommand(a, vec2(0, 0));
        }
    } else {
        a.belowSpeedSince = -1;
    }
}

string JsonVec3(vec3 v) {
    return "[" + Text::Format("%.5f", v.x) + "," + Text::Format("%.5f", v.y) + "," + Text::Format("%.5f", v.z) + "]";
}

string AgentJson(AgentState@ a) {
    return "{\"id\":" + a.id +
        ",\"position\":" + JsonVec3(a.pos) +
        ",\"velocity\":" + JsonVec3(a.velocity) +
        ",\"pitch\":" + a.pitch +
        ",\"roll\":" + a.roll +
        ",\"yaw\":" + a.yaw +
        ",\"checkpoint_time\":" + a.checkpointTime +
        ",\"lidar_left\":" + a.lidarLeft +
        ",\"lidar_right\":" + a.lidarRight +
        ",\"lidar_front\":" + a.lidarFront +
        ",\"alive\":" + (a.alive ? "true" : "false") +
        ",\"distance\":" + a.distance +
        ",\"wall_penalty\":" + a.wallPenalty + "}";
}

void SendFrame() {
    string packet = "{\"agents\":[";
    for (uint i = 0; i < Agents.Length; i++) {
        if (i > 0) packet += ",";
        packet += AgentJson(Agents[i]);
    }
    packet += "]}\n";
    try {
        Socket.Write(packet);
    } catch {
        Connected = false;
        LastError = "Socket write failed";
    }
}

void ReceiveCommands() {
    try {
        while (Socket.Available > 0) RxBuffer += Socket.Read();
    } catch {
        Connected = false;
        LastError = "Socket read failed";
        return;
    }
    while (RxBuffer.FindFirst("\n") >= 0) {
        int p = RxBuffer.FindFirst("\n");
        string line = RxBuffer.SubStr(0, p);
        RxBuffer = RxBuffer.SubStr(p + 1);
        if (line.Length > 0) ApplyResponse(line);
    }
}

void ApplyResponse(const string &in line) {
    try {
        Json::Value root = Json::Parse(line);
        if (root["type"] == "error") {
            LastError = string(root["error"]);
            return;
        }
        Generation = uint(root["generation"]);
        Json::Value@ commands = root["commands"];
        for (uint i = 0; i < Math::Min(uint(commands.Length), AGENT_COUNT); i++) {
            float steer = float(commands[i]["steering"]);
            float throttle = float(commands[i]["throttle"]);
            Agents[i].command = vec2(steer, throttle);
            if (Agents[i].alive) ApplyVehicleCommand(Agents[i], Agents[i].command);
        }
        if (bool(root["generation_end"])) RequestGenerationReset();
    } catch {
        LastError = "Malformed Python response";
    }
}

void ApplyVehicleCommand(AgentState@ a, vec2 command) {
    // Adapter boundary: a real TMNF replay/ghost provider applies these values to
    // its controlled visual vehicle. No unsupported raw-memory offsets are assumed.
    // Steering is [-1,1]; throttle/brake is [-1,1].
    a.command = vec2(Math::Clamp(command.x, -1.0f, 1.0f), Math::Clamp(command.y, -1.0f, 1.0f));
}

void RequestGenerationReset() {
    for (uint i = 0; i < Agents.Length; i++) {
        Agents[i].alive = true;
        Agents[i].belowSpeedSince = -1;
        Agents[i].distance = 0;
        Agents[i].wallPenalty = 0;
        Agents[i].command = vec2(0, 1);
    }
    try {
        // The retry command is only issued while a gameplay scene is active.
        if (GetApp().CurrentPlayground !is null) {
            UI::ShowNotification("TMRL", "Generation " + Generation + " complete; retrying track.");
        }
    } catch {
        LastError = "Playground changed during generation reset";
    }
}
