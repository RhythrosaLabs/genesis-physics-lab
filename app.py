"""
Genesis Physics Lab — Web UI
A rich interactive web interface for the Genesis physics simulation engine.
Supports live simulation control, scene presets, entity inspection, Python export,
and a demo mode when Genesis is not available.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import threading
import time
import json
import uuid
import random
import math
from datetime import datetime

# ── Genesis import (graceful degradation to demo mode) ──────────────────────
try:
    import genesis as gs
    GENESIS_AVAILABLE = True
except ImportError:
    GENESIS_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# ── Global simulation state ──────────────────────────────────────────────────
_state = {
    "scene": None,
    "sim_thread": None,
    "running": False,
    "paused": False,
    "step_count": 0,
    "fps": 0.0,
    "entities": [],          # list of {id, name, type, pos, params}
    "gravity": [0.0, 0.0, -9.81],
    "dt": 0.01,
    "backend": "cpu",
    "log": [],               # activity log entries
    "created_at": None,
    "demo_mode": not GENESIS_AVAILABLE,
}
_lock = threading.Lock()
_fps_counter = {"frames": 0, "last_time": time.time()}

PRESETS = {
    "sandbox": {
        "label": "Sandbox",
        "description": "Empty scene with a ground plane — build anything.",
        "gravity": [0.0, 0.0, -9.81],
        "objects": [],
    },
    "falling_tower": {
        "label": "Falling Tower",
        "description": "A stack of boxes that topples under gravity.",
        "gravity": [0.0, 0.0, -9.81],
        "objects": [
            {"type": "box", "name": "Block 1", "params": {"size": [1.0, 1.0, 0.4], "pos": [0, 0, 0.2]}},
            {"type": "box", "name": "Block 2", "params": {"size": [0.9, 0.9, 0.4], "pos": [0.05, 0, 0.6]}},
            {"type": "box", "name": "Block 3", "params": {"size": [0.8, 0.8, 0.4], "pos": [0.1, 0, 1.0]}},
            {"type": "box", "name": "Block 4", "params": {"size": [0.7, 0.7, 0.4], "pos": [0.15, 0, 1.4]}},
            {"type": "sphere", "name": "Wrecking Ball", "params": {"radius": 0.4, "pos": [2.5, 0, 1.2]}},
        ],
    },
    "billiards": {
        "label": "Billiards",
        "description": "Sphere collisions on a flat plane — no gravity in Z for a table effect.",
        "gravity": [0.0, 0.0, -2.0],
        "objects": [
            {"type": "sphere", "name": "Cue Ball",  "params": {"radius": 0.15, "pos": [0, 0, 0.15]}},
            {"type": "sphere", "name": "Ball 1",    "params": {"radius": 0.15, "pos": [1.0, 0,   0.15]}},
            {"type": "sphere", "name": "Ball 2",    "params": {"radius": 0.15, "pos": [1.3, 0.15, 0.15]}},
            {"type": "sphere", "name": "Ball 3",    "params": {"radius": 0.15, "pos": [1.3, -0.15, 0.15]}},
            {"type": "sphere", "name": "Ball 4",    "params": {"radius": 0.15, "pos": [1.6, 0.3, 0.15]}},
            {"type": "sphere", "name": "Ball 5",    "params": {"radius": 0.15, "pos": [1.6, 0,   0.15]}},
        ],
    },
    "zero_gravity": {
        "label": "Zero Gravity",
        "description": "Objects float freely with zero gravity.",
        "gravity": [0.0, 0.0, 0.0],
        "objects": [
            {"type": "sphere", "name": "Orb 1",  "params": {"radius": 0.3, "pos": [0,   0, 1.0]}},
            {"type": "sphere", "name": "Orb 2",  "params": {"radius": 0.2, "pos": [1.0, 0, 0.5]}},
            {"type": "box",    "name": "Cube",   "params": {"size": [0.6, 0.6, 0.6], "pos": [-1.0, 0, 0.8]}},
            {"type": "cylinder", "name": "Cylinder", "params": {"radius": 0.25, "height": 0.8, "pos": [0, 1.0, 1.2]}},
        ],
    },
    "avalanche": {
        "label": "Avalanche",
        "description": "A cascade of mixed rigid bodies falling from height.",
        "gravity": [0.0, 0.0, -9.81],
        "objects": [
            {"type": "sphere",   "name": f"Rock {i}",
             "params": {"radius": round(random.uniform(0.1, 0.3), 2),
                        "pos": [round(random.uniform(-1.5, 1.5), 2),
                                round(random.uniform(-1.5, 1.5), 2),
                                round(random.uniform(2, 5), 2)]}}
            for i in range(1, 9)
        ],
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with _lock:
        _state["log"].append({"time": ts, "msg": msg})
        if len(_state["log"]) > 200:
            _state["log"].pop(0)


def _reset_state(keep_backend=True):
    with _lock:
        _state["scene"] = None
        _state["sim_thread"] = None
        _state["running"] = False
        _state["paused"] = False
        _state["step_count"] = 0
        _state["fps"] = 0.0
        _state["entities"] = []
        _state["log"] = []
        _state["created_at"] = None
        if not keep_backend:
            _state["backend"] = "cpu"
    _fps_counter["frames"] = 0
    _fps_counter["last_time"] = time.time()


def _run_simulation_demo():
    """Simulated playback loop used when Genesis is not available."""
    while True:
        with _lock:
            running = _state["running"]
            paused = _state["paused"]
        if not running:
            break
        if not paused:
            with _lock:
                _state["step_count"] += 1
                for ent in _state["entities"]:
                    if ent["type"] != "plane":
                        g = _state["gravity"]
                        ent["params"]["pos"][2] = max(
                            0.05,
                            ent["params"]["pos"][2] + g[2] * _state["dt"] * 0.1,
                        )
            _fps_counter["frames"] += 1
            now = time.time()
            elapsed = now - _fps_counter["last_time"]
            if elapsed >= 1.0:
                with _lock:
                    _state["fps"] = round(_fps_counter["frames"] / elapsed, 1)
                _fps_counter["frames"] = 0
                _fps_counter["last_time"] = now
        time.sleep(_state["dt"])


def _run_simulation_genesis():
    """Real Genesis simulation loop."""
    while True:
        with _lock:
            running = _state["running"]
            paused = _state["paused"]
            scene = _state["scene"]
        if not running or scene is None:
            break
        if not paused:
            try:
                scene.step()
                with _lock:
                    _state["step_count"] += 1
                _fps_counter["frames"] += 1
                now = time.time()
                elapsed = now - _fps_counter["last_time"]
                if elapsed >= 1.0:
                    with _lock:
                        _state["fps"] = round(_fps_counter["frames"] / elapsed, 1)
                    _fps_counter["frames"] = 0
                    _fps_counter["last_time"] = now
            except Exception as e:
                _log(f"Simulation error: {e}")
                with _lock:
                    _state["running"] = False
                break
        else:
            time.sleep(0.02)


def _build_scene_genesis(gravity, objects):
    """Build a Genesis scene and return it (called in the main/init thread)."""
    gs.init(backend=getattr(gs, _state["backend"], gs.cpu))
    scene = gs.Scene(
        show_viewer=True,
        viewer_options=gs.options.ViewerOptions(
            res=(1280, 960),
            camera_pos=(6.0, 6.0, 4.0),
            camera_lookat=(0.0, 0.0, 0.5),
            camera_fov=45,
            max_FPS=60,
        ),
        rigid_options=gs.options.RigidOptions(
            dt=_state["dt"],
            gravity=tuple(gravity),
        ),
    )
    scene.add_entity(gs.morphs.Plane())
    for obj in objects:
        _add_genesis_entity(scene, obj)
    scene.build()
    return scene


def _add_genesis_entity(scene, obj):
    t = obj["type"]
    p = obj.get("params", {})
    pos = tuple(p.get("pos", [0, 0, 1]))
    if t == "box":
        scene.add_entity(gs.morphs.Box(size=tuple(p.get("size", [1, 1, 1])), pos=pos))
    elif t == "sphere":
        scene.add_entity(gs.morphs.Sphere(radius=p.get("radius", 0.5), pos=pos))
    elif t == "cylinder":
        scene.add_entity(gs.morphs.Cylinder(
            radius=p.get("radius", 0.25), height=p.get("height", 1.0), pos=pos))
    elif t == "capsule":
        scene.add_entity(gs.morphs.Capsule(
            radius=p.get("radius", 0.2), height=p.get("height", 0.8), pos=pos))


def _add_entity_to_state(obj_type, name, params):
    eid = str(uuid.uuid4())[:8]
    entry = {"id": eid, "name": name, "type": obj_type, "params": params}
    with _lock:
        _state["entities"].append(entry)
    return eid


def _generate_python_script():
    """Generate a runnable Genesis Python script from the current scene state."""
    with _lock:
        gravity = list(_state["gravity"])
        dt = _state["dt"]
        entities = list(_state["entities"])
        backend = _state["backend"]

    lines = [
        "import genesis as gs",
        "",
        f"gs.init(backend=gs.{backend})",
        "",
        "scene = gs.Scene(",
        "    show_viewer=True,",
        "    viewer_options=gs.options.ViewerOptions(",
        "        res=(1280, 960),",
        "        camera_pos=(6.0, 6.0, 4.0),",
        "        camera_lookat=(0.0, 0.0, 0.5),",
        "        camera_fov=45,",
        "        max_FPS=60,",
        "    ),",
        "    rigid_options=gs.options.RigidOptions(",
        f"        dt={dt},",
        f"        gravity={tuple(gravity)},",
        "    ),",
        ")",
        "",
        "# Ground plane",
        "scene.add_entity(gs.morphs.Plane())",
        "",
        "# Scene entities",
    ]
    for ent in entities:
        if ent["type"] == "plane":
            continue
        t = ent["type"]
        p = ent["params"]
        name = ent["name"]
        lines.append(f"# {name}")
        pos = tuple(p.get("pos", [0, 0, 1]))
        if t == "box":
            size = tuple(p.get("size", [1, 1, 1]))
            lines.append(f"scene.add_entity(gs.morphs.Box(size={size}, pos={pos}))")
        elif t == "sphere":
            r = p.get("radius", 0.5)
            lines.append(f"scene.add_entity(gs.morphs.Sphere(radius={r}, pos={pos}))")
        elif t == "cylinder":
            r = p.get("radius", 0.25)
            h = p.get("height", 1.0)
            lines.append(f"scene.add_entity(gs.morphs.Cylinder(radius={r}, height={h}, pos={pos}))")
        elif t == "capsule":
            r = p.get("radius", 0.2)
            h = p.get("height", 0.8)
            lines.append(f"scene.add_entity(gs.morphs.Capsule(radius={r}, height={h}, pos={pos}))")
        lines.append("")

    lines += [
        "scene.build()",
        "",
        "# Run simulation",
        "for _ in range(1000):",
        "    scene.step()",
    ]
    return "\n".join(lines)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# -- Scene management ---------------------------------------------------------

@app.route("/api/scene/create", methods=["POST"])
def create_scene():
    global _state
    data = request.get_json(silent=True) or {}
    gravity = data.get("gravity", [0.0, 0.0, -9.81])
    dt = float(data.get("dt", 0.01))
    backend = data.get("backend", "cpu")

    # Stop any running simulation first
    with _lock:
        _state["running"] = False
    if _state["sim_thread"] and _state["sim_thread"].is_alive():
        _state["sim_thread"].join(timeout=2)

    _reset_state()
    with _lock:
        _state["gravity"] = gravity
        _state["dt"] = dt
        _state["backend"] = backend
        _state["created_at"] = datetime.now().isoformat()

    if GENESIS_AVAILABLE:
        try:
            scene = _build_scene_genesis(gravity, [])
            with _lock:
                _state["scene"] = scene
                _state["running"] = True
            t = threading.Thread(target=_run_simulation_genesis, daemon=True)
            with _lock:
                _state["sim_thread"] = t
            t.start()
        except Exception as e:
            _log(f"Genesis init error: {e}")
            with _lock:
                _state["demo_mode"] = True
            _start_demo_loop()
    else:
        _start_demo_loop()

    _log("Scene created")
    return jsonify({"status": "success", "message": "Scene created", "demo_mode": _state["demo_mode"]})


def _start_demo_loop():
    with _lock:
        _state["running"] = True
    t = threading.Thread(target=_run_simulation_demo, daemon=True)
    with _lock:
        _state["sim_thread"] = t
    t.start()


@app.route("/api/scene/reset", methods=["POST"])
def reset_scene():
    with _lock:
        _state["running"] = False
    if _state["sim_thread"] and _state["sim_thread"].is_alive():
        _state["sim_thread"].join(timeout=2)
    _reset_state()
    _log("Scene reset")
    return jsonify({"status": "success", "message": "Scene reset"})


@app.route("/api/scene/pause", methods=["POST"])
def pause_scene():
    with _lock:
        _state["paused"] = not _state["paused"]
        paused = _state["paused"]
    _log("Simulation paused" if paused else "Simulation resumed")
    return jsonify({"status": "success", "paused": paused})


@app.route("/api/scene/step", methods=["POST"])
def step_once():
    """Advance one step while paused."""
    with _lock:
        scene = _state["scene"]
        demo = _state["demo_mode"]
    if demo:
        with _lock:
            _state["step_count"] += 1
        _log("Stepped (demo)")
        return jsonify({"status": "success"})
    if scene is None:
        return jsonify({"status": "error", "message": "No active scene"})
    try:
        scene.step()
        with _lock:
            _state["step_count"] += 1
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/scene/status", methods=["GET"])
def scene_status():
    with _lock:
        return jsonify({
            "running": _state["running"],
            "paused": _state["paused"],
            "step_count": _state["step_count"],
            "fps": _state["fps"],
            "entity_count": len(_state["entities"]),
            "gravity": _state["gravity"],
            "dt": _state["dt"],
            "backend": _state["backend"],
            "demo_mode": _state["demo_mode"],
            "genesis_available": GENESIS_AVAILABLE,
            "created_at": _state["created_at"],
        })


@app.route("/api/scene/gravity", methods=["POST"])
def update_gravity():
    data = request.get_json(silent=True) or {}
    gravity = data.get("gravity", [0.0, 0.0, -9.81])
    with _lock:
        _state["gravity"] = gravity
        scene = _state["scene"]
    if scene and GENESIS_AVAILABLE:
        try:
            scene.rigid_options.gravity = tuple(gravity)
        except Exception:
            pass
    _log(f"Gravity → {gravity}")
    return jsonify({"status": "success", "gravity": gravity})


# -- Presets ------------------------------------------------------------------

@app.route("/api/presets", methods=["GET"])
def list_presets():
    return jsonify([
        {"id": k, "label": v["label"], "description": v["description"]}
        for k, v in PRESETS.items()
    ])


@app.route("/api/presets/<preset_id>", methods=["POST"])
def load_preset(preset_id):
    if preset_id not in PRESETS:
        return jsonify({"status": "error", "message": "Unknown preset"})
    preset = PRESETS[preset_id]

    # Stop running sim
    with _lock:
        _state["running"] = False
    if _state["sim_thread"] and _state["sim_thread"].is_alive():
        _state["sim_thread"].join(timeout=2)
    _reset_state()

    gravity = preset["gravity"]
    with _lock:
        _state["gravity"] = gravity
        _state["dt"] = 0.01
        _state["created_at"] = datetime.now().isoformat()

    # Populate entity list
    for obj in preset["objects"]:
        params = dict(obj["params"])
        if "pos" in params:
            params = dict(params)
            params["pos"] = list(params["pos"])
        _add_entity_to_state(obj["type"], obj["name"], params)

    if GENESIS_AVAILABLE:
        try:
            scene = _build_scene_genesis(gravity, preset["objects"])
            with _lock:
                _state["scene"] = scene
                _state["running"] = True
            t = threading.Thread(target=_run_simulation_genesis, daemon=True)
            with _lock:
                _state["sim_thread"] = t
            t.start()
        except Exception as e:
            _log(f"Genesis preset error: {e}")
            with _lock:
                _state["demo_mode"] = True
            _start_demo_loop()
    else:
        _start_demo_loop()

    _log(f"Preset loaded: {preset['label']}")
    return jsonify({"status": "success", "message": f"Preset '{preset['label']}' loaded",
                   "entity_count": len(preset["objects"])})


# -- Entities -----------------------------------------------------------------

@app.route("/api/entities", methods=["GET"])
def list_entities():
    with _lock:
        return jsonify(_state["entities"])


@app.route("/api/entities", methods=["POST"])
def add_entity():
    data = request.get_json(silent=True) or {}
    obj_type = data.get("type")
    name = data.get("name") or f"{obj_type.capitalize()} {len(_state['entities']) + 1}"
    params = data.get("params", {})

    VALID = {"box", "sphere", "cylinder", "capsule"}
    if obj_type not in VALID:
        return jsonify({"status": "error", "message": f"Invalid type. Use: {VALID}"})

    if "pos" not in params:
        params["pos"] = [0.0, 0.0, 1.5]

    eid = _add_entity_to_state(obj_type, name, params)

    # Add to live Genesis scene if running
    with _lock:
        scene = _state["scene"]
    if scene and GENESIS_AVAILABLE and not _state["demo_mode"]:
        try:
            _add_genesis_entity(scene, {"type": obj_type, "params": params})
        except Exception as e:
            _log(f"Live add entity failed (rebuild needed): {e}")

    _log(f"Added {name} ({obj_type})")
    return jsonify({"status": "success", "id": eid, "name": name})


@app.route("/api/entities/<eid>", methods=["DELETE"])
def delete_entity(eid):
    with _lock:
        before = len(_state["entities"])
        _state["entities"] = [e for e in _state["entities"] if e["id"] != eid]
        after = len(_state["entities"])
    if before == after:
        return jsonify({"status": "error", "message": "Entity not found"})
    _log(f"Deleted entity {eid}")
    return jsonify({"status": "success"})


# -- Log ----------------------------------------------------------------------

@app.route("/api/log", methods=["GET"])
def get_log():
    with _lock:
        return jsonify(_state["log"][-50:])


@app.route("/api/log/clear", methods=["POST"])
def clear_log():
    with _lock:
        _state["log"] = []
    return jsonify({"status": "success"})


# -- Export -------------------------------------------------------------------

@app.route("/api/export/python", methods=["GET"])
def export_python():
    script = _generate_python_script()
    return jsonify({"status": "success", "script": script})


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)

