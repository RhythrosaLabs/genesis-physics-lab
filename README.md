<div align="center">

# 🔬 Genesis Physics Lab

**Interactive web UI for the Genesis physics simulation engine — no Genesis install required**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

</div>

---

A rich, dark-themed web UI for [Genesis](https://github.com/Genesis-Embodied-AI/Genesis) — the physics simulation engine. Runs in full live mode with Genesis installed, or in demo mode without it. Perfect for robotics researchers, game developers, and anyone exploring real-time physics.

## ✨ Features

| Feature | Description |
|---|---|
| **Scene Presets** | One-click load: Falling Tower, Billiards, Zero-G Sandbox, Avalanche |
| **Object Builder** | Add Box, Sphere, Cylinder, Capsule with full parameter control |
| **Quick Drop** | Randomized single-object drop or full tower stacks |
| **Physics Controls** | Live gravity presets — Earth, Moon, Mars, Zero-G, Reversed + per-axis control |
| **Python Export** | One-click export of the current scene as a runnable Genesis `.py` script |
| **Live Stats** | Real-time FPS, step counter, entity list, backend info |
| **Activity Log** | Per-action timestamped log |
| **Demo Mode** | Fully functional without Genesis installed |
| **Dark Theme** | GitHub/VS Code-inspired dark UI |

## 🚀 Quick Start

**Demo mode (no Genesis needed):**
```bash
git clone https://github.com/RhythrosaLabs/genesis-physics-lab.git
cd genesis-physics-lab
pip install -r requirements.txt
python app.py
# Open http://localhost:8080
```

**Live mode (with Genesis):** Install [Genesis](https://github.com/Genesis-Embodied-AI/Genesis) first, then run as above. The badge switches from `DEMO` to `LIVE`.

## 🛠️ Tech Stack

- **Python + Flask** — web server and Genesis integration
- **JavaScript** — browser UI, real-time controls
- **Genesis** — physics simulation engine (optional)

## 🤝 Contributing

PRs welcome. Open an issue first for major changes.

## 📄 License

MIT

## 💛 Support

If this project helps your research or game dev, consider supporting:

👉 [Donate via PayPal](https://paypal.me/noodlebake) — @noodlebake

🌐 [Portfolio: rhythrosalabs.github.io](https://rhythrosalabs.github.io) (more apps, music and sound design)

---
<div align="center">Made with ❤️ by <a href="https://github.com/RhythrosaLabs">RhythrosaLabs</a></div>
