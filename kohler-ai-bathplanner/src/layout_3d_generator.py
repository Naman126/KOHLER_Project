def generate_3d_html(requirements, products):
    bath_req = requirements.get('bathroom', {})
    L = float(bath_req.get('length_ft') or bath_req.get('length') or 8.0)
    W = float(bath_req.get('width_ft') or bath_req.get('width') or 6.0)
    
    style = str(requirements.get('style', 'modern')).lower()

    profiles = {
        "japanese_zen": {
            "floor": "#D2B48C", "wall": "#F0EAD6", "vanity": "#8B5A2B", "faucet": "#2B2B2B", "counter": "#E8D8C8",
            "ambient_color": "0xFFE4C4", "ambient_int": 0.85,
            "extra_geometry": f"""
                const matGeo = new THREE.BoxGeometry(2.5, 0.05, 2.5); 
                const matMat = new THREE.MeshStandardMaterial({{color: '#8B5A2B', roughness: 0.9}}); 
                const showerMat = new THREE.Mesh(matGeo, matMat); 
                showerMat.position.set(1.5, 0.15, {L} - 1.5); 
                scene.add(showerMat);
            """
        },
        "luxury": {
            "floor": "#0A0A0A", "wall": "#1C1C1C", "vanity": "#111111", "faucet": "#D4AF37", "counter": "#050505",
            "ambient_color": "0xFFFFFF", "ambient_int": 0.45,
            "extra_geometry": """
                const backLight = new THREE.PointLight(0xD4AF37, 2, 8); 
                backLight.position.set(1.5, 4.0, 0.3); 
                scene.add(backLight);
            """
        },
        "classic": {
            "floor": "#E8E8E8", "wall": "#FFFFFF", "vanity": "#FFFFFF", "faucet": "#C0C0C0", "counter": "#F5F5F5",
            "ambient_color": "0xFFF5E1", "ambient_int": 0.8,
            "extra_geometry": f"""
                const wGeo = new THREE.BoxGeometry({W}, 3, 0.3); 
                const wMat = new THREE.MeshStandardMaterial({{color: '#DCDCDC', roughness: 1.0}}); 
                const wainscot = new THREE.Mesh(wGeo, wMat); 
                wainscot.position.set({W}/2, 1.5, -0.1); 
                scene.add(wainscot);
            """
        },
        "minimalist": {
            "floor": "#F5F5F5", "wall": "#FFFFFF", "vanity": "#000000", "faucet": "#000000", "counter": "#FFFFFF",
            "ambient_color": "0xFFFFFF", "ambient_int": 0.9,
            "extra_geometry": ""
        },
        "modern": {
            "floor": "#2B2D35", "wall": "#E8EAED", "vanity": "#4A4E59", "faucet": "#888888", "counter": "#FFFFFF",
            "ambient_color": "0xE0F7FA", "ambient_int": 0.65,
            "extra_geometry": ""
        }
    }
    
    prof = profiles.get(style, profiles["modern"])

    if isinstance(products, dict):
        item_list = products.get("selected_products") or products.get("products") or []
    elif isinstance(products, list):
        item_list = products
    else:
        item_list = []

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; overflow: hidden; background-color: #121316; }}
            #canvas-container {{ width: 100vw; height: 100vh; display: block; }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="canvas-container"></div>
        <script>
            const container = document.getElementById('canvas-container');
            const scene = new THREE.Scene();
            scene.background = new THREE.Color('#16181D'); 

            const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set({W * 1.5}, 10, {L * 1.5});

            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: false }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap; // High quality shadows
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.target.set({W/2}, 1, {L/2});
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;

            // Lighting
            scene.add(new THREE.AmbientLight({prof['ambient_color']}, {prof['ambient_int']}));
            
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.85);
            dirLight.position.set(10, 15, 10);
            dirLight.castShadow = true;
            dirLight.shadow.mapSize.width = 2048; // HD Shadows
            dirLight.shadow.mapSize.height = 2048;
            scene.add(dirLight);

            // Floor
            const floorGeo = new THREE.PlaneGeometry({W}, {L});
            const floorMat = new THREE.MeshStandardMaterial({{ color: '{prof['floor']}', roughness: 0.1, metalness: 0.1 }});
            const floor = new THREE.Mesh(floorGeo, floorMat);
            floor.rotation.x = -Math.PI / 2;
            floor.position.set({W/2}, 0, {L/2});
            floor.receiveShadow = true;
            scene.add(floor);
            
            // Walls
            const wallMat = new THREE.MeshStandardMaterial({{ color: '{prof['wall']}', roughness: 0.95 }});
            const backWall = new THREE.Mesh(new THREE.BoxGeometry({W}, 8, 0.2), wallMat);
            backWall.position.set({W/2}, 4, -0.1);
            backWall.receiveShadow = true;
            scene.add(backWall);

            // Add Procedural Potted Plant (Biophilic Decor)
            const plantGroup = new THREE.Group();
            const potMat = new THREE.MeshStandardMaterial({{color: 0xEEEEEE, roughness: 0.8}});
            const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.2, 0.6, 16), potMat);
            pot.position.set(0, 0.3, 0);
            pot.castShadow = true;
            plantGroup.add(pot);
            
            const leafMat = new THREE.MeshStandardMaterial({{color: 0x2E5A27, roughness: 0.6}});
            const leaf1 = new THREE.Mesh(new THREE.SphereGeometry(0.3, 16, 16), leafMat);
            leaf1.position.set(0, 0.7, 0);
            leaf1.scale.set(1, 1.5, 1);
            leaf1.castShadow = true;
            plantGroup.add(leaf1);
            
            const leaf2 = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 16), leafMat);
            leaf2.position.set(0.2, 0.5, 0.2);
            leaf2.scale.set(1.5, 1, 1.5);
            leaf2.castShadow = true;
            plantGroup.add(leaf2);
            
            plantGroup.position.set({W - 0.8}, 0, {L - 0.8}); // Corner placement
            scene.add(plantGroup);

            // Inject Unique Style Geometry
            {prof['extra_geometry']}

    """

    for p in item_list:
        cat = p.get('category', '').lower()
        vanity_y = 1.3
        vanity_h = 2.6
        if style == "japanese_zen":
            vanity_h = 1.6
            vanity_y = 0.8
        elif style == "classic":
            vanity_y = 1.5

        if "toilet" in cat:
            html += f"""
            const tGroup = new THREE.Group();
            const tMat = new THREE.MeshStandardMaterial({{ color: 0xFFFFFF, roughness: 0.1, metalness: 0.1 }});
            
            const base = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.4, 1.8), tMat);
            base.position.set(0, 0.7, 0);
            base.castShadow = true;
            tGroup.add(base);
            
            // Smoother tank
            const tank = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.0, 0.6), tMat);
            tank.position.set(0, 1.9, -0.6);
            tank.castShadow = true;
            tGroup.add(tank);

            tGroup.position.set({W - 1.2}, 0, 1.2);
            scene.add(tGroup);
            """
        elif "vanity" in cat:
            html += f"""
            const vGroup = new THREE.Group();
            const vMat = new THREE.MeshStandardMaterial({{ color: '{prof['vanity']}', roughness: 0.8 }});
            const vanity = new THREE.Mesh(new THREE.BoxGeometry(3.0, {vanity_h}, 1.8), vMat);
            vanity.position.set(0, {vanity_y}, 0);
            vanity.castShadow = true;
            vGroup.add(vanity);
            
            const topMat = new THREE.MeshStandardMaterial({{ color: '{prof['counter']}', roughness: 0.2 }});
            const counter = new THREE.Mesh(new THREE.BoxGeometry(3.1, 0.15, 1.9), topMat);
            counter.position.set(0, {vanity_y + (vanity_h/2)}, 0);
            counter.castShadow = true;
            vGroup.add(counter);
            
            // Ceramic Vessel Sink Basin
            const sinkMat = new THREE.MeshStandardMaterial({{ color: 0xFFFFFF, roughness: 0.1 }});
            const sink = new THREE.Mesh(new THREE.SphereGeometry(0.6, 32, 16, 0, Math.PI*2, 0, Math.PI/2), sinkMat);
            sink.rotation.x = Math.PI; // Flip it to create a bowl
            sink.position.set(0, {vanity_y + (vanity_h/2) + 0.3}, 0.2);
            sink.scale.set(1, 0.5, 0.8);
            sink.castShadow = true;
            vGroup.add(sink);

            // High-Reflection Mirror
            const mirrorMat = new THREE.MeshStandardMaterial({{color: 0xDDDDDD, metalness: 1.0, roughness: 0.0}});
            const mirror = new THREE.Mesh(new THREE.BoxGeometry(2.6, 2.0, 0.1), mirrorMat);
            mirror.position.set(0, {vanity_y + (vanity_h/2) + 1.5}, -0.8);
            vGroup.add(mirror);
            
            vGroup.position.set(1.5, 0, 1);
            scene.add(vGroup);
            """
        elif "shower" in cat:
            html += f"""
            const sGroup = new THREE.Group();
            const sMat = new THREE.MeshStandardMaterial({{ color: '{prof['wall']}' }});
            const showerBase = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.2, 3.0), sMat);
            showerBase.position.set(1.5, 0.1, {L} - 1.5);
            showerBase.receiveShadow = true;
            scene.add(showerBase);
            
            // Advanced Frosted Glass Material
            const glassMat = new THREE.MeshPhysicalMaterial({{
                color: 0xE8FAFF, metalness: 0.1, roughness: 0.2, transmission: 0.9, transparent: true, opacity: 1.0
            }});
            const glass = new THREE.Mesh(new THREE.BoxGeometry(3.0, 6.0, 0.05), glassMat);
            glass.position.set(1.5, 3.0, {L} - 3.0);
            scene.add(glass);
            """
        elif "faucet" in cat:
            html += f"""
            const fGroup = new THREE.Group();
            const fMat = new THREE.MeshStandardMaterial({{ color: '{prof['faucet']}', metalness: 0.9, roughness: 0.1 }});
            
            // Faucet Base
            const faucetBase = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.5, 16), fMat);
            faucetBase.position.set(0, 0.25, 0);
            faucetBase.castShadow = true;
            fGroup.add(faucetBase);
            
            // Faucet Spout
            const spout = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.4, 16), fMat);
            spout.rotation.x = Math.PI / 2;
            spout.position.set(0, 0.45, 0.15);
            spout.castShadow = true;
            fGroup.add(spout);
            
            fGroup.position.set(1.5, {vanity_y + (vanity_h/2) + 0.1}, 0.7);
            scene.add(fGroup);
            """

    html += """
            window.addEventListener('resize', () => {
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }, false);

            function animate() {
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }
            animate();
        </script>
    </body>
    </html>
    """
    return html