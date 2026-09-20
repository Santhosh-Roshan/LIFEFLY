
>     <script type="module">
          import { 
initializeApp } from "https:/
/www.gstatic.com/firebasejs/1
0.9.0/firebase-app.js";
          import { 
getDatabase, ref, push, 
onValue, remove } from "https
://www.gstatic.com/firebasejs
/10.9.0/firebase-database.js"
;
          import { getAuth, 
signInAnonymously } from "htt
ps://www.gstatic.com/firebase
js/10.9.0/firebase-auth.js";
          const 
firebaseConfig = { 
databaseURL: "https://lifefly
-default-rtdb.firebaseio.com"
 };
          const appInfo = ini
tializeApp(firebaseConfig);
          const db = 
getDatabase(appInfo);
          const auth = 
getAuth(appInfo);
          signInAnonymously(a
uth).catch(e => 
console.error(e));
          const missionsRef 
= ref(db, 'missions');
          const statusRef = 
ref(db, 'uav_status');
          const trackRef = 
ref(db, 'drone_track');
          window.missionsRef 
= missionsRef;
          const $ = id => 
document.getElementById(id); 
const toast = m => { const t 
= $('toast'); t.textContent 
= m; 
t.classList.add('show'); 
clearTimeout(window.tt); 
window.tt = setTimeout(() => 
t.classList.remove('show'), 
2800) }; function clock() { 
$('clock').textContent = 
'UTC ' + new Date().toISOStri
ng().slice(11, 19) } 
setInterval(clock, 1000); 
clock();
          const keys = { 
critical: ['blood', 
'plasma', 'organ', 'kidney', 
'lung', 'heart', 'venom', 
'anti-venom', 'epinephrine', 
'trauma', 'hemorrhage', 
'stroke', 'emergency', 
'critical', 'resuscitation', 
'sepsis', 'defibrillator'], 
urgent: ['insulin', 
'diabetic', 'surgery', 
'surgical', 'oxygen', 'o2', 
'burn', 'fracture', 
'urgent', 'chemotherapy', 
'asthma'], low: ['records', 
'paperwork', 'ppe', 
'gloves', 'document', 
'routine', 'supplies', 
'inventory'] }; function 
priority(text) { const t = 
text.toLowerCase(); for 
(const k of keys.critical) 
if (t.includes(k)) return { 
n: 1, l: 'P1-CRITICAL', c: 
'var(--red)', d: 
'Life-threatening â€” 
immediate UAV dispatch', r: 
k }; for (const k of 
keys.urgent) if 
(t.includes(k)) return { n: 
2, l: 'P2-URGENT', c: 
'var(--orange)', d: 
'Time-sensitive â€” dispatch 
within 10 minutes', r: k }; 
for (const k of keys.low) if 
(t.includes(k)) return { n: 
4, l: 'P4-LOW', c: 
'var(--blue)', d: 
'Non-urgent â€” batch 
delivery recommended', r: k 
}; return { n: 3, l: 
'P3-STANDARD', c: 
'var(--mint)', d: 'Routine 
â€” standard scheduled 
delivery', r: 'default' } } $
('payload').addEventListener(
'input', () => { const v = 
$('payload').value.trim(), b 
= $('priority-info'); if 
(!v) { b.style.display = 
'none'; return } const p = 
priority(v); b.style.display 
= 'block'; 
b.style.borderColor = p.c; 
b.innerHTML = '<strong 
style="color:' + p.c + '">' 
+ p.l + '</strong>' + p.d + 
' Â· ' + (p.r === 'default' 
? 'default classification' : 
'detected: ' + p.r) });
          
$('btn-gps').onclick = () => 
{ if (navigator.geolocation) 
navigator.geolocation.getCurr
entPosition(p => { 
$('lat').value = p.coords.lat
itude.toFixed(6); 
$('lng').value = p.coords.lon
gitude.toFixed(6); 
toast('Station coordinates 
synchronized') }, () => { 
$('lat').value = '17.3850'; 
$('lng').value = '78.4867'; 
toast('Using GCS base 
coordinates') }); else 
toast('Geolocation 
unavailable â€” enter 
coordinates manually') };
          let mCount = 1000;
          
$('dispatch-form').onsubmit 
= async e => { 
e.preventDefault(); 
mCount++; const p = priority(
$('payload').value), btn = 
$('btn-submit'), name = 
$('branch').value.trim(), 
payload = 
$('payload').value.trim(); 
btn.disabled = true; btn.quer
ySelector('span').textContent
 = 'Securing corridorâ€¦'; 
$('spinner').style.display = 
'inline'; const mission = { 
request_id: `LF-${mCount}`, 
branch_name: name, latitude: 
parseFloat($('lat').value), 
longitude: 
parseFloat($('lng').value), 
request_details: payload, 
priority: p.n, 
priority_label: p.l, 
ai_priority_reason: p.r, 
status: 'QUEUED', timestamp: 
new Date().toISOString(), 
dispatched_from: 'WEB_GCS' 
}; try { if 
(window.missionsRef) { await 
push(window.missionsRef, 
mission); } 
$('spinner').style.display = 
'none'; $('priority-info').st
yle.display = 'none'; 
e.target.reset(); 
toast(mission.request_id + ' 
staged for ' + name); } 
catch (err) { toast('Error: 
' + err.message); } finally 
{ btn.disabled = false; btn.q
uerySelector('span').textCont
ent = 'Initiate launch'; 
$('spinner').style.display = 
'none'; } };
          document.querySelec
torAll('.tab').forEach(t => 
t.onclick = () => { document.
querySelectorAll('.tab').forE
ach(x => x.classList.remove('
active')); document.querySele
ctorAll('.tab-content').forEa
ch(x => x.classList.remove('a
ctive')); 
t.classList.add('active'); $(
t.dataset.tab).classList.add(
'active') });
          // Three.js 3D 
flight volume
          const canvas = 
$('drone-canvas'), scene = 
new THREE.Scene(); scene.fog 
= new 
THREE.FogExp2(0x071718, 
.012); const camera = new 
THREE.PerspectiveCamera(43, 
1, .1, 100); 
camera.position.set(5, 3.7, 
7.4); const renderer = new 
THREE.WebGLRenderer({ 
canvas, antialias: true, 
alpha: true }); renderer.setP
ixelRatio(Math.min(devicePixe
lRatio, 2)); 
renderer.outputColorSpace = 
THREE.SRGBColorSpace; 
renderer.shadowMap.enabled = 
true; scene.add(new THREE.Hem
isphereLight(0x9deac5, 
0x071414, 2.4)); const key = 
new THREE.DirectionalLight(0x
d9ffbd, 4); 
key.position.set(4, 8, 5); 
key.castShadow = true; 
scene.add(key); const fill = 
new 
THREE.PointLight(0x52c8c4, 
25, 18); 
fill.position.set(-4, 2, 3); 
scene.add(fill);
          function 
mat(color, metal = .2, rough 
= .4, emissive = 0) { return 
new 
THREE.MeshStandardMaterial({ 
color, metalness: metal, 
roughness: rough, emissive, 
emissiveIntensity: emissive 
? 1.8 : 0 }) } const drone = 
new THREE.Group(); 
scene.add(drone); 
drone.position.y = .5; const 
body = new THREE.Mesh(new 
THREE.SphereGeometry(1.05, 
.42, 24, 14), mat(0xcdf4df, 
.55, .22)); 
body.scale.set(1.55, .48, 
.8); body.castShadow = true; 
drone.add(body); const nose 
= new THREE.Mesh(new 
THREE.SphereGeometry(.5, 20, 
12), mat(0x153d3c, .45, 
.12)); nose.scale.set(.7, 
.38, .5); 
nose.position.set(.75, .02, 
.04); drone.add(nose); const 
lens = new THREE.Mesh(new 
THREE.SphereGeometry(.16, 
16, 10), mat(0xd8ff72, .4, 
.12, 0xb5dc43)); 
lens.position.set(1.11, .03, 
.12); drone.add(lens); const 
arms = []; const rotors = 
[]; for (const s of [-1, 1]) 
{ const arm = new 
THREE.Mesh(new 
THREE.BoxGeometry(2.6, .11, 
.12), mat(0x7ebda7, .65, 
.3)); arm.rotation.z = s * 
.18; arm.position.x = -.03; 
drone.add(arm); 
arms.push(arm); for (const z 
of [-1, 1]) { const pod = 
new THREE.Mesh(new 
THREE.CylinderGeometry(.18, 
.2, .18, 18), mat(0x183a36, 
.5, .3)); pod.rotation.x = 
Math.PI / 2; 
pod.position.set(-.88, s * 
.42, z * .48); 
drone.add(pod); const rotor 
= new THREE.Mesh(new 
THREE.TorusGeometry(.42, 
.018, 6, 44), new 
THREE.MeshBasicMaterial({ 
color: 0xd8ff72, 
transparent: true, opacity: 
.8 })); rotor.position.copy(p
od.position); 
rotor.rotation.x = Math.PI / 
2; drone.add(rotor); 
rotors.push(rotor) } } const 
cargo = new THREE.Mesh(new 
THREE.BoxGeometry(.48, .42, 
.48), mat(0xffb86b, .35, 
.3)); 
cargo.position.set(-.15, 
-.48, 0); cargo.castShadow = 
true; drone.add(cargo); 
const beam = new 
THREE.Mesh(new 
THREE.ConeGeometry(.48, 2.5, 
32, 1, true), new 
THREE.MeshBasicMaterial({ 
color: 0xd8ff72, 
transparent: true, opacity: 
.07, side: THREE.DoubleSide, 
depthWrite: false })); 
beam.position.set(.3, -1.65, 
0); drone.add(beam);
          const grid = new 
THREE.GridHelper(15, 28, 
0x32736d, 0x16403e); 
grid.position.y = -1.25; 
scene.add(grid); const ring 
= new THREE.Mesh(new 
THREE.TorusGeometry(2.8, 
.015, 8, 96), new 
THREE.MeshBasicMaterial({ 
color: 0x8de8c2, 
transparent: true, opacity: 
.45 })); ring.rotation.x = 
Math.PI / 2.4; 
ring.position.y = -.25; 
scene.add(ring); const ring2 
= ring.clone(); 
ring2.scale.set(.72, .72, 
.72); ring2.rotation.z = .8; 
ring2.material = 
ring.material.clone(); ring2.
material.color.set(0xd8ff72);
 ring2.position.y = .7; 
scene.add(ring2); const 
particles = new 
THREE.Group(); for (let i = 
0; i < 100; i++) { const g = 
new THREE.Mesh(new 
THREE.SphereGeometry(.012, 
5, 5), new 
THREE.MeshBasicMaterial({ 
color: i % 3 ? 0x8de8c2 : 
0xd8ff72 })); g.position.set(
(Math.random() - .5) * 12, 
Math.random() * 5 - 1.2, 
(Math.random() - .5) * 9); 
particles.add(g) } 
scene.add(particles);
          let rx = -.13, ry 
= .12, zoom = 7.4, drag = 
false, px = 0, py = 0, 
paused = false; function 
resize() { const r = canvas.g
etBoundingClientRect(); 
renderer.setSize(r.width, 
r.height, false); 
camera.aspect = r.width / 
r.height; camera.updateProjec
tionMatrix() } new ResizeObse
rver(resize).observe(canvas);
 resize(); function 
applyCam() { camera.position.
set(Math.sin(ry) * 
Math.cos(rx) * zoom, 
Math.sin(rx) * zoom + 1.3, 
Math.cos(ry) * Math.cos(rx) 
* zoom); camera.lookAt(0, 
.1, 0) } canvas.addEventListe
ner('pointerdown', e => { 
drag = true; px = e.clientX; 
py = e.clientY; canvas.setPoi
nterCapture(e.pointerId) }); 
canvas.addEventListener('poin
termove', e => { if (!drag) 
return; ry += (e.clientX - 
px) * .008; rx += (e.clientY 
- py) * .006; rx = 
Math.max(-.9, Math.min(.8, 
rx)); px = e.clientX; py = 
e.clientY; applyCam() }); can
vas.addEventListener('pointer
up', () => drag = false); can
vas.addEventListener('pointer
cancel', () => drag = 
false); canvas.addEventListen
er('wheel', e => { 
e.preventDefault(); zoom = 
Math.max(4, Math.min(11, 
zoom + e.deltaY * .008)); 
applyCam() }, { passive: 
false }); canvas.addEventList
ener('dblclick', () => { rx 
= -.13; ry = .12; zoom = 
7.4; applyCam(); toast('3D 
flight camera reset') }); 
$('reset-view').onclick = () 
=> { rx = -.13; ry = .12; 
zoom = 7.4; applyCam() }; 
$('pause-view').onclick = () 
=> { paused = !paused; 
$('pause-view').textContent 
= paused ? 'RESUME DRONE' : 
'PAUSE DRONE'; toast(paused 
? 'Drone animation paused' : 
'Autonomous flight resumed') 
}; applyCam(); const timer = 
new THREE.Clock(); function 
animate() { requestAnimationF
rame(animate); const t = 
timer.getElapsedTime(); if 
(!paused) { drone.position.y 
= .55 + Math.sin(t * 1.7) * 
.12; drone.rotation.y = 
Math.sin(t * .55) * .18; 
drone.rotation.z = 
Math.sin(t * 1.1) * .035; 
rotors.forEach((r, i) => { 
r.rotation.z = t * 8 * (i % 
2 ? -1 : 1) }); 
ring.rotation.z = t * .16; 
ring2.rotation.z = -t * .28; 
particles.rotation.y = t * 
.025 } 
renderer.render(scene, 
camera) } animate();
          // Right-side 
Leaflet tactical map
          // Right-side 
Leaflet tactical map
          const map = 
L.map('map', { zoomControl: 
false, attributionControl: 
true }).setView([17.385, 
78.4867], 16); 
L.control.zoom({ position: 
'bottomright' }).addTo(map); 
L.tileLayer('https://{s}.base
maps.cartocdn.com/dark_all/{z
}/{x}/{y}{r}.png', { 
maxZoom: 20, attribution: 
'Â© OpenStreetMap Â© CARTO' 
}).addTo(map); const base = 
L.divIcon({ className: '', 
html: '<div class="hospital-m
arker"></div>', iconSize: 
[24, 24], iconAnchor: [12, 
12] }), uav = L.divIcon({ 
className: '', html: '<div cl
ass="drone-marker"></div>', 
iconSize: [28, 28], 
iconAnchor: [14, 14] }); 
const basePos = [17.385, 
78.4867]; L.marker(basePos, 
{ icon: base }).addTo(map).bi
ndPopup('<b>GCS 
BASE</b><br>Clinical command 
station'); const droneMarker 
= L.marker([0, 0], { icon: 
uav }).addTo(map).bindTooltip
('LF-01  /  IN FLIGHT', { 
permanent: true, direction: 
'top', offset: [0, -12], 
className: 'route-label' }); 
droneMarker.setOpacity(0);
          let mapMarkers = 
{};
          onValue(statusRef, 
(snapshot) => { const data = 
snapshot.val(); if (data) { 
$('telem-mode').textContent 
= data.mode || 'â€”'; $('tele
m-battery').textContent = `${
parseFloat(data.battery_pct).
toFixed(1)}%`; $('telem-altit
ude').textContent = `${parseF
loat(data.altitude_m).toFixed
(1)} m`; 
$('telem-gps').textContent = 
(data.gps_satellites || 
'â€”') + ' FIX'; 
$('telem-speed').textContent 
= `${parseFloat(data.ground_s
peed_ms).toFixed(1)} m/s`; 
$('telem-pos').textContent = 
`${parseFloat(data.lat).toFix
ed(6)}, ${parseFloat(data.lng
).toFixed(6)}`; } });
          onValue(trackRef, 
(snapshot) => { const data = 
snapshot.val(); if (data && 
data.lat) { 
droneMarker.setOpacity(1); dr
oneMarker.setLatLng([data.lat
, data.lng]); } });
          
onValue(missionsRef, 
(snapshot) => { const data = 
snapshot.val(); const 
dataArray = data ? Object.ent
ries(data).map(([key, val]) 
=> ({ key, ...val })) : []; $
('mission-count').textContent
 = String(dataArray.length).p
adStart(2, '0') + " ACTIVE 
MISSIONS"; const tbody = 
$('queue-body'); if 
(dataArray.length === 0) { 
tbody.innerHTML = '<tr><td 
colspan="5" style="text-align
:center;padding:20px;opacity:
0.5">No active missions in 
queue</td></tr>'; } else { 
dataArray.sort((a, b) => 
(a.priority || 3) - 
(b.priority || 3) || a.timest
amp.localeCompare(b.timestamp
)); tbody.innerHTML = 
dataArray.map(m => 
`<tr><td><span class="badge 
p${m.priority || 3}">${m.prio
rity_label}</span></td><td 
class="mono">${m.request_id 
|| m.key}</td><td>${m.branch_
name}</td><td>${m.request_det
ails.slice(0, 28)}${m.request
_details.length > 28 ? 'â€¦' 
: ''}</td><td 
class="status">${m.status || 
'QUEUED'}</td></tr>`).join(''
); } Object.values(mapMarkers
).forEach(m => 
map.removeLayer(m)); 
mapMarkers = {}; 
dataArray.forEach(m => { if 
(m.latitude && m.longitude 
&& m.status !== 'COMPLETED') 
{ const colorClass = 
['critical', 'amber', 
'green', 'blue'][(m.priority 
|| 3) - 1]; const icon = 
L.divIcon({ className: '', 
html: '<div 
class="legend-dot ' + 
colorClass + '" style="width:
12px;height:12px;display:bloc
k;border:1px solid 
#061013"></div>', iconSize: 
[12, 12], iconAnchor: [6, 6] 
}); const marker = 
L.marker([m.latitude, 
m.longitude], { icon }).addTo
(map).bindPopup('<b>' + 
m.branch_name + 
'</b><br>Approved delivery 
node'); mapMarkers[m.key] = 
marker; } }); });
  
          // 
Intro-to-console gesture 
layer
          (function () {
              const intro = d
ocument.getElementById('intro
'), open = document.getElemen
tById('open-console'), close 
= document.getElementById('cl
ose-console'); let sx = 0, 
sy = 0; function reveal() { d
ocument.body.classList.add('c
onsole-open'); setTimeout(() 
=> document.getElementById('b
ranch')?.focus(), 750) } 
function hide() { document.bo
dy.classList.remove('console-
open') } open.addEventListene
r('click', reveal); close.add
EventListener('click', hide);
              function 
down(e) { sx = e.clientX || 
(e.touches ? 
e.touches[0].clientX : 0); 
sy = e.clientY || (e.touches 
? e.touches[0].clientY : 0); 
}
              function up(e) 
{ let cx = e.clientX || 
(e.changedTouches ? 
e.changedTouches[0].clientX 
: 0); let cy = e.clientY || 
(e.changedTouches ? 
e.changedTouches[0].clientY 
: 0); if (cx - sx > 50 || 
Math.abs(cy - sy) > 80 || sx 
- cx > 50) reveal(); }
              intro.addEventL
istener('mousedown', down); i
ntro.addEventListener('mouseu
p', up); intro.addEventListen
er('touchstart', down, { 
passive: true }); intro.addEv
entListener('touchend', up);
              document.addEve
ntListener('keydown', e => { 
if ((e.key === 'ArrowRight' 
|| e.key === 'Enter') && !doc
ument.body.classList.contains
('console-open')) reveal(); 
if (e.key === 'Escape' && doc
ument.body.classList.contains
('console-open')) hide() })
          })();
      </script>
  </body>
  
  </html>


