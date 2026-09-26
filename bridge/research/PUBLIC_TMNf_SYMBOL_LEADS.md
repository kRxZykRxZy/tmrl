# Public TMNF Native Symbol Leads

These are research leads taken from public TMNF modding work. They are not
automatically safe addresses for the user's executable.

## Useful public symbols

The public ModTMNF address table exposes:

- CreateByMwClassId at 0x00923D30
- UpdateVehicleStateFromInputs at 0x004FE7E0
- UpdateVehicleStateFromInputsImpl at 0x004FE500
- UnregisterPlayer at 0x0059CC60

Its class-id table includes:

- CSceneVehicleCar = 0x0A02B000
- CSceneMobil = 0x0A011000
- CGameControlPlayerInput = 0x03013000
- CGameControlPlayer = 0x03003000
- camera-related classes including CGameCtnMediaBlockCamera,
  CGameCtnMediaBlockCameraGame, and CGameCtnMediaBlockCameraCustom.

The same project exposes the live race object and current player through:

- CTrackMania.TheGame.Race
- CTrackManiaRace.GetPlayingPlayerInfo()
- CTrackManiaRace.GetPlayingPlayer()

and demonstrates hooking UpdateVehicleStateFromInputsImpl in the game loop.

## What this proves

It proves that the TMNF executable has:

1. an internal object/class factory;
2. explicit vehicle-related class IDs;
3. a player-input update function;
4. accessible race/player structures;
5. multiple camera-related class types.

## What it does not prove

It does not by itself prove the complete lifecycle:

    create CSceneVehicleCar
      ->
    attach to world/scene
      ->
    attach controller
      ->
    attach physics
      ->
    register race/player identity
      ->
    render and simulate independently

That lifecycle still needs to be traced and validated.

## Required next discovery

Trace callers of CreateByMwClassId for the vehicle creation path and identify
the exact registration functions used after construction.

The target is a real live vehicle, not merely a CSceneVehicleCar heap object.

## Source

Public ModTMNF:
https://github.com/pixeltris/ModTMNF

Public TMNF ASI plugin example:
https://github.com/Delorean12DMC/tmnf-plugins
