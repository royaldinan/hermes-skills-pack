---
name: blender-scripting
description: "Use when automating Blender or procedural 3D modeling."
version: 1.2.0
category: creative
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [3d, blender, bpy, modeling, rendering, procedural, mcp]
---

# Blender Automation & Procedural 3D Scripting (`bpy`)

## When to use

Use when the user asks to create, modify, inspect, or render 3D scenes, objects, materials, or animations in Blender using Python (`bpy`), either headless (background CLI) or connected live to an active Blender GUI session.

## Blender Discovery & Execution Modes

### 1. Locating Blender Executable
Check PATH first, then standard install directories:
- **Windows**: `which blender 2>/dev/null || find "C:/Program Files/Blender Foundation" -maxdepth 3 -iname "blender.exe" 2>/dev/null`
- **Windows git-bash fallback**: when the above finds nothing, probe versioned candidates directly — the real binary usually lives one level down (e.g. `Blender 5.2/blender.exe`) while the top folder holds only the version dir:
```bash
for f in "/c/Program Files/Blender Foundation/blender.exe" "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"; do [ -f "$f" ] && echo "FOUND: $f"; done
```
Invoke via the quoted POSIX path.
- **macOS**: `/Applications/Blender.app/Contents/MacOS/Blender`
- **Linux**: `which blender` or `/usr/bin/blender`

### 2. Headless Mode (Batch / Background Execution)
Run scripts without GUI overhead:
```bash
# Execute script, build scene, save .blend and/or render
blender -b -P script.py

# Open existing file, run script, save render frame
blender -b project.blend -P script.py -o //render_ -F PNG -f 1
```

### 3. Live Mode (Controlling Active Blender Viewport)
When the user is working inside Blender GUI and wants realtime additions:

#### A. Native MCP Server (`mcp-for-blender`) — Preferred for Hermes Agent
Hermes connects natively via stdio to the `mcp-for-blender` server, which relays tool calls over TCP (`127.0.0.1:9876`) to the Blender add-on.

1. **Ensure Addon Directory Exists**:
   ```bash
   # Windows (git-bash)
   mkdir -p "$APPDATA/Blender Foundation/Blender/<version>/scripts/addons"
   ```
2. **Install & Enable the Add-on**:
   ```bash
   uvx mcp-for-blender install-addon
   # Enable headlessly and save user preferences so it persists across sessions:
   blender --background --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='blender_mcp'); bpy.ops.wm.save_userpref()"
   ```
3. **Register in Hermes Non-Interactively**:
   ```bash
   printf "y\n" | hermes mcp add blender --command uvx --args mcp-for-blender
   hermes mcp test blender
   ```
   *Note: Piped `printf "y\n"` bypasses the interactive tool checklist prompt.*
4. **Operation**:
   - In Blender GUI: Press `N` in 3D Viewport -> **MCP for Blender** tab. Server starts automatically (`127.0.0.1:9876`).
   - In Hermes: MCP tools become directly callable:
     - `mcp_blender_execute_blender_code`: Executes arbitrary `bpy`/`bmesh` Python in live viewport.
     - `mcp_blender_get_scene_info`: Retrieves active scene hierarchy, objects, vertices, materials.
     - `mcp_blender_look`: Captures viewport snapshot/render for visual verification.
     - `mcp_blender_search_assets` / `import_asset`: Fetches models/textures (Poly Haven, Sketchfab).
     - `mcp_blender_generate_3d`: Procedural/AI 3D mesh generation.

#### B. Lightweight Fallback Socket Server (Direct Scripting)
If MCP is unavailable, user runs a lightweight socket server inside Blender's **Scripting** tab:
```python
import bpy, socket, threading

def handle_client(conn):
    try:
        data = conn.recv(65536).decode('utf-8')
        if data:
            bpy.app.timers.register(lambda: exec(data, {'bpy': bpy}))
            conn.sendall(b"OK")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', 9876))
    s.listen(5)
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle_client, args=(conn,)).start()

threading.Thread(target=start_server, daemon=True).start()
```
Agent connects to `127.0.0.1:9876` and sends `bpy` snippets that execute on the main thread via `bpy.app.timers`.

### Live Session Add-on Reconnection & Urgency Fallback Pitfall
- **Background CLI vs Running GUI**: Running `blender --background --python-expr "bpy.ops.preferences.addon_enable(module='blender_mcp')"` modifies `userpref.blend` on disk, but does NOT inject or start the server in an already-running Blender GUI process.
- **Do Not Stall on GUI Automation**: Never spend multiple round-trips attempting to drive Blender GUI menus via OS keystrokes/clicks to re-enable an add-on when the user is pressed for time ("udah gak cukup waktu", "cepet aja"). Pivot immediately to direct, concise manual UI instructions specifying exact icon names and panel tabs.

---

## Procedural Modeling Patterns

### Scene Initialization
Always wipe or initialize clean state when generating a standalone scene:
```python
import bpy

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for collection in [bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights]:
        for item in collection:
            collection.remove(item, do_unlink=True)
```

### Applying Scale Before Modifiers & Selective MESH Application
Always call transform apply on mesh objects before adding `BEVEL` or `SUBSURF` modifiers. If scale is unapplied, bevel widths and subdivision tension will be distorted unevenly across axes.
**Pitfall**: Calling `bpy.ops.object.transform_apply(scale=True)` on a broad selection containing Empties, lights, or armatures raises warnings or errors. Iterate selectively over mesh types:
```python
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type == 'MESH':
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        o.select_set(False)
```

### Smooth Shading
Enable smooth shading on mesh polygons:
```python
for poly in obj.data.polygons:
    poly.use_smooth = True
```

### Studio Corner Rooms & Enclosed Backdrop Geometry Pitfall
- **Solid Box vs 2D Plane**: Never use a rotated 2D primitive plane (`primitive_plane_add`) scaled up for tall studio walls. A plane has 0 local Z-thickness; rotating 90° on X swaps local Y and Z, leaving vertical gaps where external HDRI world lighting leaks into the room. Always build walls from 3D Cubes (`primitive_cube_add`) with real thickness (e.g. 0.3m) and height matching or exceeding the camera frustum (e.g. 8.0m).
- **Corner Seam Placement**: Always position the perpendicular corner seam beyond the outermost bounding box of all props, spotlights, and baseboards (`seam_x > max(prop_x)`). If a right wall is placed inside the props' coordinates (e.g. wall at X=1.1m while lamp post is at X=1.4m), the wall completely occludes the prop and blocks any spotlight mounted on it.

### Recessed / Framed Elements Pitfall
Never place a flat canvas or recessed object inside a solid box frame without hollow boundaries or insetting. An un-inset frame cube's front face completely hides the inner canvas. Use 4 border cubes or an inset face so the canvas remains visible.

### Matching a Reference Object's Dimensions (Build-Then-Normalize)
When a new model must match an existing .blend object's size exactly: read the reference world-space bbox first (`matrix_world @ v.co` per vertex), build new geometry in convenient units, then scale per-axis by `target_extent / built_extent` applied to both `location` and `scale`, and verify by re-measuring — avoids hand-tuning every part to fractional Blender units.

### Surface Detail Protrusion Pitfall
Face, trim, and button boxes placed flush with their host face z-fight or sink inside it at render time. Offset every appliqué detail outward along its face normal (even a fraction of a unit) so it sits visibly proud of the surface.

### Voxel / Minecraft Style Restraint
Blocky deliverables stay pure cuboids with flat materials — no bevel, subsurf, or extra detail geometry. When the user says boxy like Steve and not complex, reuse the reference silhouette and proportions exactly and change only skin colors/details; a fancier reshaped model reads as wrong even when it renders cleanly. Match the reference silhouette and proportions; recolor via materials rather than reshaping parts.

### Unifying Multi-Part Geometry into a Single Manifold Mesh
`bpy.ops.object.join()` (`Ctrl+J`) only groups separate meshes under one Object container in the Outliner; in Edit Mode, the geometry remains disconnected loose parts (intersecting boxes with hidden internal faces). To create a true single-manifold mesh:
1. **Deselect All Before Loose Separation**: Call `bpy.ops.object.select_all(action='DESELECT')` before selecting the target object for `bpy.ops.mesh.separate(type='LOOSE')` to avoid accidentally splitting other selected objects in the scene.
2. **Flush / Coplanar Boundary Overlap**: Boolean Union (`solver='EXACT'`) treats perfectly flush, touching coplanar faces (e.g. leg top touching tabletop at exact same Z) as non-intersecting and keeps them as separate mesh islands. Offset or translate the touching vertices slightly into the adjoining volume (e.g. 0.001–0.002m) so volume intersection occurs; Boolean Union will then cleanly delete interior faces and weld the outer boundary into 1 continuous island.
3. **Bevel Order**: Unify base geometry into 1 manifold mesh *before* applying Bevel modifiers. Beveling loose parts before unioning rounds contact corners and creates non-planar slivers that break boolean operations.
4. **Preserve Multi-Material Slots**: Pre-populate the base object's `data.materials` with all distinct materials from the incoming parts before boolean union, so face material indices are retained rather than overwritten by the base material.
5. **Solver Fallback**: Wrap `solver='EXACT'` in a try/except falling back to `solver='FAST'` when dealing with coplanar boundaries or complex manifold junctions that trigger solver exceptions.


---

## Materials & Shading (Blender 4.x / 5.x)

### sRGB to Linear Color Space Conversion
Blender's Principled BSDF `Base Color` input expects Linear RGB. Directly dividing 0-255 sRGB or hex values by 255 causes colors to appear washed out and over-bright due to gamma disparity. Always convert sRGB/hex to linear:
```python
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def hex_to_linear(hex_str):
    h = hex_str.lstrip('#')
    return tuple(srgb_to_linear(int(h[i:i+2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)
```

### Shared Material Slot Re-assignment Pitfall
When recoloring scenes where multiple distinct objects share a placeholder material (e.g. walls, sofa, and rug all bound to `Mat_Pink`), modifying the shared material in-place recolors every object indiscriminately. Inspect `obj.material_slots` and assign distinct semantic materials (`Mat_Wall`, `Mat_Sofa`, `Mat_Rug`) to preserve visual hierarchy and contrast.

### Principled BSDF Node Compatibility
Blender 4.0+ updated the Principled BSDF socket names:
- `Base Color`: `"Base Color"`
- `Roughness`: `"Roughness"`
- `Metallic`: `"Metallic"`
- `Emission`: Use `"Emission Color"` (or fallback to `"Emission"` in legacy 3.x) and `"Emission Strength"`.

Helper function:
```python
def create_material(name, color, roughness=0.5, metallic=0.0, emission_color=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission_color and emission_strength > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = emission_color
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = emission_color
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat
```

### EEVEE Next (Blender 4.2+ / 5.x) Emission & Bloom Pitfall
In Blender 4.2+ and 5.x (EEVEE Next), the legacy "Bloom" checkbox in Render Properties was removed completely, and emission materials do not cast indirect light onto surrounding geometry unless `scene.eevee.use_raytracing = True` (Raytracing / Screen Space GI) or Light Probe volumes are present.
- Without raytracing enabled, an emission material only self-illuminates its own polygons as flat, unshaded color; it casts zero light onto adjacent geometry, walls, or floors.
- Without Bloom or a Compositor `Glare` node (`type='FOG_GLOW'`), emissive surfaces have no optical halo or glare, appearing like flat colored plastic.
- Separation of concerns: Always combine an emission material on the physical bulb/glass mesh (providing the visible camera-facing light source) with a real `SPOT` or `POINT` light object at the same position (projecting directional illumination and shadow-casting light pools), since point/spot lights are invisible in camera renders while emission geometry lacks directional punch.

### Dark Floor Reflectance for Spotlight Pools Pitfall
When aiming a theatrical spotlight to create a bright circular or oval pool of light on a dark studio floor:
- Never use ultra-dark albedo (e.g. `#100305`, linear reflectance < 0.01) — it absorbs ~99% of incident photons, rendering even a 5000W spotlight pool completely invisible and flat.
- Set the floor base color to a rich mid-dark tone (`#4A151B` to `#541922`, linear ~0.08–0.12) with moderate roughness (`0.28–0.38`) and specular (`0.5`).
- Aim the spotlight target at open floor space in the foreground, well clear of plinths or pedestals that cast large blocking shadows across the camera view.
- In Cycles, scale spotlight wattage with distance squared (`6000W–9500W` for distances of 3m–5m with soft blend `0.25–0.35`).

---

## Studio Camera & Lighting Workflows

### Robust Camera Framing with Track-To Constraint
Manual Euler camera rotations frequently look at the back of models or skew framing. Use a dedicated `TRACK_TO` constraint pointing at an Empty target:
```python
empty = bpy.data.objects.new("CamTarget", None)
empty.location = (target_x, target_y, target_z)
bpy.context.collection.objects.link(empty)

cam_data = bpy.data.cameras.new("HeroCamera")
cam_data.lens = 28.0  # Wide-normal to capture tall props (e.g. 3m lamp posts) without clipping
cam_obj = bpy.data.objects.new("HeroCamera", cam_data)
cam_obj.location = (cam_x, cam_y, target_z)  # Same Z as target = level camera, 0 vertical keystone distortion!
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

tt = cam_obj.constraints.new(type='TRACK_TO')
tt.target = empty
tt.track_axis = 'TRACK_NEGATIVE_Z'
tt.up_axis = 'UP_Y'
```
*Level Camera Rule*: Keeping `cam_obj.location.z == empty.location.z` produces architectural two-point perspective where vertical columns and room seams remain 100% parallel with no keystone perspective distortion.

### 3-Point Lighting Setup Pattern
- **Key Light**: High-energy downward Spot Light (`6000W–9500W`, spot size ~50°, blend 0.3) casting a warm, feathered elliptical pool on the floor and grazing subject contours.
- **Fill Light**: Broad, soft Area Light (`size=3.5m`, `350W–550W`) positioned front-left with cool tone (`#D8E8FC`) to lift shadow valleys on matte/stealth surfaces.
- **Rim / Back Light**: High-angle Area Light (`size=3.0m`, `800W–1200W`) behind subjects pointing toward camera (`#FFF6ED`) to cleanly silhouette dark shells from dark background walls.
- **HDRI World Fill**: Set background strength to `0.04–0.06` so environment reflections populate metallic PBR surfaces without washing out low-key chiaroscuro contrast.

### HDRI / World Background Fast Configuration
- **Properties Editor**: Click the red globe icon (**World Properties**) -> Under **Surface**:
  - *Swap HDRI*: In the **Color** row, click Open on the Environment Texture node to select the image file.
  - *Solid Dark Night*: Click the yellow dot next to **Color** -> select solid color (dark navy/black) and drop **Strength** to `0.05–0.1` so ambient reflections remain subtle without blowing out night contrast.
- **Shader Editor**: Top tab **Shading** -> switch header dropdown from **Object** to **World** -> connect **Environment Texture** or plain **Background** node into **World Output**.

### Clean Outliner Naming (Anti-AI Slop)
Never use long, verbose, compound procedural names (`Studio_Key_DramaticSpotlight`, `Studio_BurgundyWall`, `Pedestal_ObsidianBeveled_Base`). Use natural, clean artist and student naming: `Key Light`, `Fill Light`, `Rim Light`, `Wall`, `Floor`, `Pedestal`, `Lamp Post`. It keeps scenes clean, professional, and readable.

### Blender 5.x Compositor Node Tree Compatibility
In Blender 5.0+, `Scene.node_tree` is deprecated/removed in favor of `scene.compositing_node_group`. Do not attempt to clear or rebuild `scene.node_tree.nodes` directly in Blender 5.x scripts without verifying attribute existence; rely on Cycles native raytraced global illumination and emission bounces for glowing visors and lamps.

---

## Isometric Camera & Lighting Setup

### Isometric / Orthographic Camera
Standard isometric cutaway setup looking into an open corner:
```python
import math

bpy.ops.object.camera_add(location=(16.5, -16.5, 14.2))
cam = bpy.context.active_object
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 11.0
# Exact isometric angle: X=58° (or 54.736°), Y=0°, Z=45°
cam.rotation_euler = (math.radians(58.0), 0, math.radians(45.0))
bpy.context.scene.camera = cam
```

### Soft Studio Lighting
- **Key Light**: Sun light with `angle = math.radians(25.0)` to create soft feathered shadow edges instead of harsh dark lines.
- **Fill Light**: Large Area light (`size = 6.0` to `8.0`) with soft cool/warm tone from front-left or front-right.
- **Ambient / Bounce Light**: Overhead low-energy area light (`size = 9.0`) to lift ambient occlusion without blowing out highlights.

### Color Management Pitfall
- In Blender 4.x / 5.x, default `AgX` tone mapping heavily desaturates high-key pastel colors and highlights, making stylized pastel / clay renders look washed out.
- For vibrant pastel, clay, or cartoon aesthetics, set `scene.view_settings.view_transform = 'Standard'` or `'Filmic'` with `'Medium High Contrast'`.
- If using `AgX`, use `scene.view_settings.look = 'AgX - Punchy'` and lower key light energy to prevent overexposure.

### Minecraft Skin Model Construction
Minecraft characters use 6 cuboids (head 8×8×8, torso 8×12×4, 2 arms 4×12×4, 2 legs 4×12×4) with a single 64×64 PNG skin template UV-mapped onto all faces. The pixelated look comes from nearest-neighbor texture interpolation (`tex.interpolation = 'Closest'`), NOT from per-pixel geometry. When given a skin template PNG larger than 64×64 (e.g. upscaled to 680×402), resize to 64×64 with nearest-neighbor sampling before use. Identify cube faces by polygon normal after `transform_apply(scale=True)`, then map each to its UV region in Mojang's standard layout. Common pitfall: treating a render preview image as a skin template — always check image dimensions and whether the layout shows unwrapped UV faces vs a 3D character. Pack generated skin images into the .blend (`img.pack()`) so the delivered file renders with no external texture dependency. Never present vision-estimated hex colors from a 3D render as exact texture values — lighting, shading, and perspective shift every pixel, so label them approximations and prefer sampling the source template directly.

### Cutaway Wall Contrast vs Background Pitfall
Avoid pure white or very pale off-white on cutaway walls against a white/light world background. Without an enclosed ceiling or strong ambient occlusion, the wall silhouettes and hanging decor bleed into the background void. Use muted slate, concrete, or subtle tinted tones (e.g. `#8D9CAE` / `#97A5B5`) so cutaway borders remain sharply readable. The same camouflage hits white-clothed characters on a white void — bridge the gaps it exposes (e.g. a skin-tone neck block between head and torso) and always confirm with a rendered preview frame inspected visually before delivering.
