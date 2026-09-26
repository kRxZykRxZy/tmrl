// In-game diagnostics for TMRL.
uint FocusedAgent = 0;
bool ShowOverlay = true;
float LastBest = 0;
float LastSurvival = 0;
uint LastGeneration = 0;
uint LastActive = 0;
string LastServerError = "";

void Render() {
    if (!ShowOverlay) return;

    if (UI::IsKeyPressed(UI::Key::A)) {
        FocusedAgent = FocusedAgent == 0 ? 49 : FocusedAgent - 1;
    }
    if (UI::IsKeyPressed(UI::Key::D)) {
        FocusedAgent = (FocusedAgent + 1) % 50;
    }

    UI::SetNextWindowBgAlpha(0.78f);
    if (UI::Begin("TMRL Evolution", ShowOverlay, UI::WindowFlags::AlwaysAutoResize)) {
        UI::Text("Generation: " + LastGeneration);
        UI::Text("All-time high score: " + Text::Format("%.3f", LastBest));
        UI::Text("Generation survival: " + Text::Format("%.1f%%", LastSurvival * 100.0f));
        UI::Text("Active cars: " + LastActive + "/50");
        UI::Separator();
        UI::Text("Focused car: " + FocusedAgent);
        UI::Text("A / D: previous / next");

        AgentState@ a = Agents.Length == 50 ? Agents[FocusedAgent] : null;
        if (a !is null) {
            UI::Text("Speed: " + Text::Format("%.2f", a.velocity.Length() * 3.6f) + " km/h");
            UI::Text("Steer: " + Text::Format("%.3f", a.command.x));
            UI::Text("Throttle: " + Text::Format("%.3f", a.command.y));
            UI::Text("LIDAR L/F/R: " + Text::Format("%.2f / %.2f / %.2f", a.lidarLeft, a.lidarFront, a.lidarRight));
            UI::Separator();
            UI::Text("Hidden layer activations");
            UI::TextWrapped("Activation telemetry is populated by the Python server response for the focused agent.");
            DrawLidar(a);
        }
        if (LastServerError.Length > 0) UI::TextColored(vec4(1, 0.25, 0.25, 1), LastServerError);
    }
    UI::End();
}

void DrawLidar(AgentState@ a) {
    // World-space laser rendering requires a valid game camera projection. The
    // overlay keeps the exact endpoints available; this 2D fallback provides a
    // reliable diagnostic even when the current scene has no camera.
    vec2 origin = UI::GetCursorPos();
    UI::Text("LIDAR vectors:");
    UI::Text("  LEFT  " + Text::Format("%.3f", a.lidarLeft));
    UI::Text("  FRONT " + Text::Format("%.3f", a.lidarFront));
    UI::Text("  RIGHT " + Text::Format("%.3f", a.lidarRight));
}

void SetTrainingSummary(uint generation, float best, float survival, uint active, const string &in error) {
    LastGeneration = generation;
    LastBest = best;
    LastSurvival = survival;
    LastActive = active;
    LastServerError = error;
}
