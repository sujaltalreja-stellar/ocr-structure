# ============================================================
# DULB ENGINEERING QA POC - PRO 3D AUTOCAD BIM VIEWER (THREE.JS)
# ============================================================

import json
import streamlit as st
import streamlit.components.v1 as components


def render_3d_cad_viewer(cad_model, theme_mode="light", height=660):
    """
    Renders an elite Three.js WebGL 3D architectural CAD/BIM viewer.
    Features:
    - Architectural wall edge highlighting (EdgesGeometry)
    - Dynamic Wall Extrusion & Horizontal Section Slicer
    - Walkthrough & Camera view presets (Iso, Top Floor Plan, Elevation, Walk)
    - Interactive 3D Measurement Ruler (Click to measure distance in meters)
    - Click-to-inspect BIM Property HUD Card
    - Shading Modes (Realistic BIM, Blueprint, X-Ray)
    - 3D Consultant Comment Pins with pulsing beacons
    """
    if not cad_model:
        st.info("Upload drawings to generate the interactive 3D AutoCAD model.")
        return

    cad_json = json.dumps(cad_model)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            * {{
                box-sizing: border-box;
                user-select: none;
            }}
            body, html {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #0b0f19;
            }}
            #viewport-container {{
                width: 100%;
                height: {height}px;
                position: relative;
                background: radial-gradient(circle at center, #1e293b 0%, #0b0f19 100%);
            }}
            /* Glassmorphic Top Toolbar */
            #top-nav {{
                position: absolute;
                top: 14px;
                left: 14px;
                right: 14px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 8px;
                z-index: 100;
                pointer-events: none;
            }}
            .nav-group {{
                display: flex;
                gap: 6px;
                background: rgba(15, 23, 42, 0.75);
                backdrop-filter: blur(12px);
                padding: 6px 10px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                pointer-events: auto;
            }}
            .btn {{
                background: rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 4px;
            }}
            .btn:hover {{
                background: #2563eb;
                color: #ffffff;
                border-color: #3b82f6;
                transform: translateY(-1px);
            }}
            .btn.active {{
                background: #2563eb;
                color: #ffffff;
                border-color: #60a5fa;
                box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
            }}

            /* Floating BIM Property Card */
            #prop-card {{
                position: absolute;
                top: 70px;
                right: 14px;
                width: 240px;
                background: rgba(15, 23, 42, 0.88);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 12px 14px;
                color: #f1f5f9;
                font-size: 11px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
                display: none;
                z-index: 100;
            }}
            #prop-card h4 {{
                margin: 0 0 8px 0;
                font-size: 12px;
                color: #38bdf8;
                font-weight: 700;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                padding-bottom: 4px;
            }}
            .prop-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 5px;
            }}
            .prop-label {{ color: #94a3b8; font-weight: 500; }}
            .prop-val {{ color: #ffffff; font-weight: 600; }}

            /* Bottom Controls Tray */
            #bottom-tray {{
                position: absolute;
                bottom: 14px;
                left: 14px;
                right: 14px;
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                align-items: center;
                background: rgba(15, 23, 42, 0.82);
                backdrop-filter: blur(12px);
                padding: 8px 16px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                font-size: 11px;
                color: #cbd5e1;
                z-index: 100;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            }}
            .control-group {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            input[type="range"] {{
                width: 100px;
                cursor: pointer;
                accent-color: #2563eb;
            }}
            label {{
                display: flex;
                align-items: center;
                gap: 4px;
                cursor: pointer;
            }}

            /* HUD Measurement Tool readout */
            #measure-readout {{
                position: absolute;
                bottom: 60px;
                left: 50%;
                transform: translateX(-50%);
                background: #0284c7;
                color: #ffffff;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
                display: none;
                z-index: 150;
                box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
            }}

            #pin-popup {{
                position: absolute;
                display: none;
                background: rgba(15, 23, 42, 0.95);
                color: #ffffff;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 11px;
                pointer-events: none;
                z-index: 200;
                border-left: 3px solid #ef4444;
                box-shadow: 0 6px 16px rgba(0,0,0,0.4);
                max-width: 250px;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="viewport-container">
            <!-- Top Controls -->
            <div id="top-nav">
                <div class="nav-group">
                    <button class="btn active" id="btn-iso" onclick="setCam('iso')">📐 3D Iso</button>
                    <button class="btn" id="btn-top" onclick="setCam('top')">🔝 Floor Plan</button>
                    <button class="btn" id="btn-walk" onclick="setCam('walk')">🚶 Walk Mode</button>
                    <button class="btn" id="btn-front" onclick="setCam('front')">🏢 Elevation</button>
                    <button class="btn" onclick="resetView()">🔄 Center</button>
                </div>

                <div class="nav-group">
                    <button class="btn active" id="style-bim" onclick="setShading('bim')">🏢 BIM Shaded</button>
                    <button class="btn" id="style-blue" onclick="setShading('blueprint')">📐 Blueprint</button>
                    <button class="btn" id="style-xray" onclick="setShading('xray')">🩻 X-Ray</button>
                    <button class="btn" id="btn-ruler" onclick="toggleRuler()">📏 Ruler Tool</button>
                </div>
            </div>

            <!-- Property Inspector Card -->
            <div id="prop-card">
                <h4 id="prop-title">BIM Element</h4>
                <div class="prop-row"><span class="prop-label">Type:</span><span class="prop-val" id="prop-type">-</span></div>
                <div class="prop-row"><span class="prop-label">Layer:</span><span class="prop-val" id="prop-layer">-</span></div>
                <div class="prop-row"><span class="prop-label">Dimensions:</span><span class="prop-val" id="prop-dim">-</span></div>
                <div class="prop-row"><span class="prop-label">Coordinates:</span><span class="prop-val" id="prop-coords">-</span></div>
            </div>

            <div id="measure-readout">Click two points to measure distance</div>

            <!-- Bottom Controls -->
            <div id="bottom-tray">
                <div class="control-group">
                    <span>Wall Height:</span>
                    <input type="range" id="heightSlider" min="0" max="6" step="0.2" value="3.0" oninput="updateExtrusion(this.value)">
                    <span id="heightValue">3.0m</span>
                </div>
                <div class="control-group">
                    <span>Section Cut:</span>
                    <input type="range" id="sliceSlider" min="0" max="6" step="0.1" value="6.0" oninput="updateClipping(this.value)">
                    <span id="sliceValue">Max</span>
                </div>
                <div class="control-group">
                    <label><input type="checkbox" id="chkConduit" checked onchange="toggleGroup('conduits', this.checked)"> MEP Conduits</label>
                    <label><input type="checkbox" id="chkColumn" checked onchange="toggleGroup('columns', this.checked)"> Columns</label>
                    <label><input type="checkbox" id="chkPins" checked onchange="toggleGroup('pins', this.checked)"> Comment Pins</label>
                    <label><input type="checkbox" id="chkEdges" checked onchange="toggleEdges(this.checked)"> Architectural Edges</label>
                </div>
                <div>
                    <span style="opacity: 0.8;">💡 Left: Orbit • Right: Pan • Wheel: Zoom • Click: Inspect</span>
                </div>
            </div>

            <div id="pin-popup"></div>
        </div>

        <script>
            const data = {cad_json};
            const container = document.getElementById("viewport-container");
            const propCard = document.getElementById("prop-card");
            const pinPopup = document.getElementById("pin-popup");
            const measureReadout = document.getElementById("measure-readout");

            // 1. Scene & Setup
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0b0f19);

            const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio || 1);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            renderer.localClippingEnabled = true;
            renderer.toneMapping = THREE.ACESFilmicToneMapping;
            renderer.toneMappingExposure = 1.1;
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;

            // 2. Architectural Lighting
            const ambient = new THREE.AmbientLight(0xffffff, 0.65);
            scene.add(ambient);

            const hemiLight = new THREE.HemisphereLight(0xffffff, 0x1e293b, 0.45);
            scene.add(hemiLight);

            const dirLight = new THREE.DirectionalLight(0xffffff, 0.85);
            dirLight.position.set(45, 65, 35);
            dirLight.castShadow = true;
            dirLight.shadow.mapSize.width = 2048;
            dirLight.shadow.mapSize.height = 2048;
            dirLight.shadow.camera.near = 0.5;
            dirLight.shadow.camera.far = 250;
            const d = 40;
            dirLight.shadow.camera.left = -d;
            dirLight.shadow.camera.right = d;
            dirLight.shadow.camera.top = d;
            dirLight.shadow.camera.bottom = -d;
            scene.add(dirLight);

            // 3. Ground Slab with Architectural Grid
            const spanW = data.dimensions ? data.dimensions.width : 50;
            const spanD = data.dimensions ? data.dimensions.depth : 50;
            const maxSpan = Math.max(spanW, spanD, 35);

            const grid = new THREE.GridHelper(maxSpan * 1.5, 30, 0x38bdf8, 0x334155);
            grid.position.y = 0.01;
            scene.add(grid);

            const floorGeo = new THREE.PlaneGeometry(maxSpan * 1.5, maxSpan * 1.5);
            const floorMat = new THREE.MeshStandardMaterial({{
                color: 0x111827,
                roughness: 0.8,
                metalness: 0.2
            }});
            const floorMesh = new THREE.Mesh(floorGeo, floorMat);
            floorMesh.rotation.x = -Math.PI / 2;
            floorMesh.receiveShadow = true;
            scene.add(floorMesh);

            // 4. Clipping plane for horizontal section slicing
            const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 6.0);

            // 5. Geometry Groups
            const wallGroup = new THREE.Group();
            const colGroup = new THREE.Group();
            const lineGroup = new THREE.Group();
            const conduitGroup = new THREE.Group();
            const pinGroup = new THREE.Group();
            const edgeGroup = new THREE.Group();
            scene.add(wallGroup);
            scene.add(colGroup);
            scene.add(lineGroup);
            scene.add(conduitGroup);
            scene.add(pinGroup);
            scene.add(edgeGroup);

            const interactableMeshes = [];
            const pinMeshes = [];

            // Shading materials
            let currentShading = "bim";
            const edgeLineMat = new THREE.LineBasicMaterial({{ color: 0x1e293b, linewidth: 1.5 }});

            // Populate Walls with Architectural Edges
            if (data.walls) {{
                data.walls.forEach(w => {{
                    const geo = new THREE.BoxGeometry(w.w, w.h, w.d);
                    const mat = new THREE.MeshStandardMaterial({{
                        color: new THREE.Color(w.color || "#e2e8f0"),
                        roughness: 0.45,
                        metalness: 0.1,
                        clippingPlanes: [clipPlane],
                        clipShadows: true
                    }});
                    const mesh = new THREE.Mesh(geo, mat);
                    mesh.position.set(w.x, w.h / 2, w.z);
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    if (w.rotation) mesh.rotation.y = -w.rotation;

                    mesh.userData = {{
                        type: w.category || "Wall",
                        layer: w.layer || "A-WALL",
                        dim: `${{w.w}}m × ${{w.d}}m × ${{w.h}}m`,
                        coords: `X:${{w.x}}, Z:${{w.z}}`,
                        initialHeight: w.h,
                        diffStatus: w.diff_status
                    }};

                    // Architectural silhouette edge lines
                    const edgeGeo = new THREE.EdgesGeometry(geo);
                    const edgeLines = new THREE.LineSegments(edgeGeo, edgeLineMat);
                    mesh.add(edgeLines);

                    wallGroup.add(mesh);
                    interactableMeshes.push(mesh);
                }});
            }}

            // Populate Structural Columns
            if (data.columns) {{
                data.columns.forEach(col => {{
                    const geo = new THREE.BoxGeometry(col.w, col.h, col.d);
                    const mat = new THREE.MeshStandardMaterial({{
                        color: 0x475569,
                        roughness: 0.6,
                        metalness: 0.3,
                        clippingPlanes: [clipPlane]
                    }});
                    const mesh = new THREE.Mesh(geo, mat);
                    mesh.position.set(col.x, col.h / 2, col.z);
                    mesh.castShadow = true;
                    mesh.receiveShadow = true;
                    mesh.userData = {{
                        type: "Structural Column",
                        layer: col.layer || "S-COL",
                        dim: `${{col.w}}m × ${{col.d}}m × ${{col.h}}m`,
                        coords: `X:${{col.x}}, Z:${{col.z}}`,
                        initialHeight: col.h
                    }};
                    colGroup.add(mesh);
                    interactableMeshes.push(mesh);
                }});
            }}

            // Populate 3D Conduits / Cable Trays
            if (data.conduits) {{
                data.conduits.forEach(c => {{
                    const p1 = new THREE.Vector3(c.x1, c.elev || 2.65, c.z1);
                    const p2 = new THREE.Vector3(c.x2, c.elev || 2.65, c.z2);
                    const dist = p1.distanceTo(p2);
                    if (dist > 0.1) {{
                        const radius = c.radius || 0.08;
                        const geo = new THREE.CylinderGeometry(radius, radius, dist, 8);
                        const mat = new THREE.MeshStandardMaterial({{
                            color: new THREE.Color(c.color || "#0ea5e9"),
                            metalness: 0.85,
                            roughness: 0.25,
                            clippingPlanes: [clipPlane]
                        }});
                        const mesh = new THREE.Mesh(geo, mat);
                        mesh.position.copy(p1).add(p2).multiplyScalar(0.5);
                        mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p2.clone().sub(p1).normalize());
                        mesh.castShadow = true;
                        mesh.userData = {{
                            type: c.category || "MEP Conduit / Tray",
                            layer: "E-CABLE-TRAY",
                            dim: `L:${{dist.toFixed(2)}}m, Ø:${{(radius*2).toFixed(2)}}m`,
                            coords: `X:${{mesh.position.x.toFixed(1)}}, Z:${{mesh.position.z.toFixed(1)}}`
                        }};
                        conduitGroup.add(mesh);
                        interactableMeshes.push(mesh);
                    }}
                }});
            }}

            // Populate CAD Linework
            if (data.lines) {{
                const lineMat = new THREE.LineBasicMaterial({{ color: 0x64748b, transparent: true, opacity: 0.75 }});
                const pts = [];
                data.lines.forEach(l => {{
                    pts.push(new THREE.Vector3(l.x1, l.elev || 0.04, l.z1));
                    pts.push(new THREE.Vector3(l.x2, l.elev || 0.04, l.z2));
                }});
                if (pts.length > 0) {{
                    const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
                    const lineMesh = new THREE.LineSegments(lineGeo, lineMat);
                    lineGroup.add(lineMesh);
                }}
            }}

            // Populate 3D Consultant Comment Pins
            if (data.pins) {{
                data.pins.forEach(pin => {{
                    const pinObj = new THREE.Group();
                    pinObj.position.set(pin.x, 0, pin.z);

                    // Glowing vertical stem
                    const stemGeo = new THREE.CylinderGeometry(0.04, 0.04, 3.8, 6);
                    const stemMat = new THREE.MeshBasicMaterial({{ color: 0xef4444 }});
                    const stem = new THREE.Mesh(stemGeo, stemMat);
                    stem.position.y = 1.9;
                    pinObj.add(stem);

                    // Beacon sphere
                    const sphereGeo = new THREE.SphereGeometry(0.48, 16, 16);
                    const sphereMat = new THREE.MeshStandardMaterial({{
                        color: 0xef4444,
                        emissive: 0xdc2626,
                        emissiveIntensity: 0.8,
                        roughness: 0.2
                    }});
                    const beacon = new THREE.Mesh(sphereGeo, sphereMat);
                    beacon.position.y = 3.8;
                    beacon.userData = {{ pinData: pin }};
                    pinObj.add(beacon);
                    pinMeshes.push(beacon);

                    pinGroup.add(pinObj);
                }});
            }}

            // Camera Transitions
            function setCam(mode) {{
                document.querySelectorAll(".nav-group button").forEach(b => {{
                    if (["btn-iso","btn-top","btn-walk","btn-front"].includes(b.id)) b.classList.remove("active");
                }});
                if (mode === "iso") {{
                    document.getElementById("btn-iso").classList.add("active");
                    animateCamera(new THREE.Vector3(maxSpan * 0.85, maxSpan * 0.85, maxSpan * 0.85), new THREE.Vector3(0, 1.5, 0));
                }} else if (mode === "top") {{
                    document.getElementById("btn-top").classList.add("active");
                    animateCamera(new THREE.Vector3(0, maxSpan * 1.5, 0.01), new THREE.Vector3(0, 0, 0));
                }} else if (mode === "walk") {{
                    document.getElementById("btn-walk").classList.add("active");
                    animateCamera(new THREE.Vector3(0, 1.7, maxSpan * 0.4), new THREE.Vector3(0, 1.7, 0));
                }} else if (mode === "front") {{
                    document.getElementById("btn-front").classList.add("active");
                    animateCamera(new THREE.Vector3(0, maxSpan * 0.25, maxSpan * 1.25), new THREE.Vector3(0, 1.5, 0));
                }}
            }}

            function resetView() {{
                setCam("iso");
            }}

            function animateCamera(targetPos, targetLookAt) {{
                camera.position.copy(targetPos);
                controls.target.copy(targetLookAt);
                controls.update();
            }}

            setCam("iso");

            // Shading Modes
            window.setShading = function(mode) {{
                document.querySelectorAll("#style-bim, #style-blue, #style-xray").forEach(b => b.classList.remove("active"));
                document.getElementById(`style-${{mode === 'blueprint' ? 'blue' : mode}}`).classList.add("active");
                currentShading = mode;

                wallGroup.children.forEach(mesh => {{
                    if (mode === "blueprint") {{
                        mesh.material.color.set(0x0284c7);
                        mesh.material.wireframe = false;
                        mesh.material.transparent = true;
                        mesh.material.opacity = 0.85;
                        edgeLineMat.color.set(0x38bdf8);
                    }} else if (mode === "xray") {{
                        mesh.material.color.set(0x94a3b8);
                        mesh.material.wireframe = false;
                        mesh.material.transparent = true;
                        mesh.material.opacity = 0.25;
                        edgeLineMat.color.set(0x64748b);
                    }} else {{
                        // BIM Real
                        mesh.material.color.set(mesh.userData.diffStatus === 'added' ? 0x10b981 : (mesh.userData.diffStatus === 'removed' ? 0xef4444 : 0xe2e8f0));
                        mesh.material.wireframe = false;
                        mesh.material.transparent = false;
                        mesh.material.opacity = 1.0;
                        edgeLineMat.color.set(0x1e293b);
                    }}
                }});
            }};

            // Extrusion & Slicing Controls
            window.updateExtrusion = function(val) {{
                const height = parseFloat(val);
                document.getElementById("heightValue").innerText = height.toFixed(1) + "m";
                wallGroup.children.forEach(mesh => {{
                    const ratio = height / (mesh.userData.initialHeight || 3.0);
                    mesh.scale.y = ratio;
                    mesh.position.y = (mesh.userData.initialHeight * ratio) / 2;
                }});
                colGroup.children.forEach(mesh => {{
                    const ratio = height / (mesh.userData.initialHeight || 3.0);
                    mesh.scale.y = ratio;
                    mesh.position.y = (mesh.userData.initialHeight * ratio) / 2;
                }});
            }};

            window.updateClipping = function(val) {{
                const cut = parseFloat(val);
                clipPlane.constant = cut;
                document.getElementById("sliceValue").innerText = cut.toFixed(1) + "m";
            }};

            window.toggleGroup = function(groupName, visible) {{
                if (groupName === "conduits") conduitGroup.visible = visible;
                if (groupName === "columns") colGroup.visible = visible;
                if (groupName === "pins") pinGroup.visible = visible;
            }};

            window.toggleEdges = function(enabled) {{
                edgeLineMat.visible = enabled;
            }};

            // Raycaster: Click to Inspect BIM Element
            const raycaster = new THREE.Raycaster();
            const mouse = new THREE.Vector2();

            container.addEventListener("click", e => {{
                if (rulerActive) return;
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const hits = raycaster.intersectObjects(interactableMeshes);

                if (hits.length > 0) {{
                    const obj = hits[0].object;
                    const u = obj.userData;
                    propCard.style.display = "block";
                    document.getElementById("prop-title").innerText = u.type || "BIM Element";
                    document.getElementById("prop-type").innerText = u.type || "Element";
                    document.getElementById("prop-layer").innerText = u.layer || "Default";
                    document.getElementById("prop-dim").innerText = u.dim || "Standard";
                    document.getElementById("prop-coords").innerText = u.coords || "0, 0";
                }} else {{
                    propCard.style.display = "none";
                }}
            }});

            // Hover on 3D Comment Pins
            container.addEventListener("mousemove", e => {{
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const pinHits = raycaster.intersectObjects(pinMeshes);

                if (pinHits.length > 0) {{
                    const pin = pinHits[0].object.userData.pinData;
                    pinPopup.style.display = "block";
                    pinPopup.style.left = (e.clientX - rect.left + 15) + "px";
                    pinPopup.style.top = (e.clientY - rect.top - 10) + "px";
                    pinPopup.innerHTML = `<strong>${{pin.id}} (Consultant Markup)</strong><br>${{pin.comment}}`;
                }} else {{
                    pinPopup.style.display = "none";
                }}
            }});

            // 3D Measurement Ruler Tool
            let rulerActive = false;
            let rulerPoints = [];
            let rulerLine = null;

            window.toggleRuler = function() {{
                rulerActive = !rulerActive;
                document.getElementById("btn-ruler").classList.toggle("active", rulerActive);
                measureReadout.style.display = rulerActive ? "block" : "none";
                measureReadout.innerText = "Click 1st point in 3D scene...";
                rulerPoints = [];
                if (rulerLine) scene.remove(rulerLine);
            }};

            container.addEventListener("pointerdown", e => {{
                if (!rulerActive) return;
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

                raycaster.setFromCamera(mouse, camera);
                const intersects = raycaster.intersectObjects([...interactableMeshes, floorMesh]);

                if (intersects.length > 0) {{
                    const pt = intersects[0].point;
                    rulerPoints.push(pt);

                    if (rulerPoints.length === 1) {{
                        measureReadout.innerText = "Point 1 selected. Click 2nd point...";
                    }} else if (rulerPoints.length === 2) {{
                        const dist = rulerPoints[0].distanceTo(rulerPoints[1]);
                        const ft = dist * 3.28084;
                        measureReadout.innerText = `Measured: ${{dist.toFixed(2)}}m (${{ft.toFixed(1)}} ft)`;

                        // Draw 3D dimension line
                        if (rulerLine) scene.remove(rulerLine);
                        const lineGeo = new THREE.BufferGeometry().setFromPoints(rulerPoints);
                        const lineMat = new THREE.LineBasicMaterial({{ color: 0x38bdf8, linewidth: 3 }});
                        rulerLine = new THREE.Line(lineGeo, lineMat);
                        scene.add(rulerLine);

                        rulerPoints = [];
                    }}
                }}
            }});

            // Render loop with pulse animation
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();

                // Gentle pulsing on comment pins
                const t = Date.now() * 0.003;
                pinMeshes.forEach(p => {{
                    p.scale.setScalar(1 + Math.sin(t) * 0.08);
                }});

                renderer.render(scene, camera);
            }}
            animate();

            window.addEventListener("resize", () => {{
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            }});
        </script>
    </body>
    </html>
    """

    components.html(html_content, height=height + 20)
