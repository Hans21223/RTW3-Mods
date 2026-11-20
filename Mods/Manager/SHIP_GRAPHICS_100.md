# Extended Ship Graphics

The optional **Extended Ship Graphics - 100 Saved Visuals** submod raises the
designer's added `Equipment` graphics limit from 25 to 100. It requires
**Historical and Paper Hulls** because that mod draws added graphics above the
game's built-in superstructure, funnels and torpedo mounts, with guns above the
graphics.

The limit is raised in all five places the game keeps it: the Add, Mirror and
Copy commands, and both design-file loaders. Saving always wrote every graphic,
and campaign saves store their own count, but a design file loaded from disk
kept only its first 25 graphics before 1.0.1.

The game stores six native superstructure layers, each with 25 point slots.
This submod leaves that save format intact. Use added `Equipment` graphics as
extra visual layers; they are saved with the ship design and can be moved or
removed in the native graphics list. The six native layer controls remain the
same.

These added pieces are top-down plan graphics in the existing added-graphics
layer. They do not create extra 3D deck-height levels. Guns remain visible above
the graphics, following Historical and Paper Hulls' existing drawing order.

## Build a detailed added layer

`Mods/CampaignOverhaul/ship_visual_builder.py` takes a JSON outline and a
source `.sdf` design, then creates a separate importable data mod. It never
changes the source design. Filled simple polygons are split into native-sized
triangles; line paths are split into overlapping segments. The generated
`Equipment` entries use the native 25-point graphic format, and the builder
checks that the complete design stays within 100 visuals.

Example specification:

```json
{
  "design_name": "Example DD Extended",
  "layers": [
    {
      "mode": "fill",
      "color": "$00C8C8C8",
      "points": [[-200, 300], [200, 300], [150, 900], [-150, 900]]
    },
    {
      "mode": "line",
      "closed": false,
      "color": "$00000000",
      "points": [[-120, 450], [-80, 800], [0, 920], [80, 800], [120, 450]]
    }
  ]
}
```

Points use native graphic distance units: positive `y` is forward and positive
`x` is starboard. A filled layer must be a simple polygon without
self-intersections.
The builder rejects geometry it cannot safely split or a design that would
exceed the visual limit. A 100-point filled layer can use up to 49 visuals; a
100-point line layer uses at most three. Many smaller superstructure shapes fit
more layers into the same 100-visual budget.

Run from the game folder:

```text
python Mods/CampaignOverhaul/ship_visual_builder.py layer-spec.json Designs/Source.sdf Mods/Manager/generated/Example-Extended
```

The output contains `mod.json`, a separate design under `Designs`, and its
graphics under `Data/Graphics`. Import the output folder through **Add mod** in
RTW3 Mod Manager. Enable both **Historical and Paper Hulls** and **Extended
Ship Graphics** before starting the game, then import/enable the generated
design mod. Restart through **Play with mods**.

The generated shape is composed from native graphics, rather than a single
native polygon with more than 25 vertices. In-game visual appearance should be
checked on a test design before using it in a campaign.
