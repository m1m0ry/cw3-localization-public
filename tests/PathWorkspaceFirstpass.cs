// Test-only type identities for unrelated UI fields on GameSpace, Terrain and
// UnitManager. The fixed PathFindTerrain/Hfunc/CheckTerrainCell IL does not use
// these types. No firstpass behavior is simulated; accidental construction fails.
// Compile only in the isolated path-probe directory, never into a player payload.
using System;
public class VectorLine {public VectorLine(){throw new InvalidOperationException("UI is outside the path probe");}}
public class PackedSprite {public PackedSprite(){throw new InvalidOperationException("UI is outside the path probe");}}
public class UVAnimation {public UVAnimation(){throw new InvalidOperationException("UI is outside the path probe");}}
