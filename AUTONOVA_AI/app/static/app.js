const $ = (id) => document.getElementById(id);
let pollTimer = null, aiTimer = null, commandBusy = false, demo = false;
let heldCommand = null;
function toast(msg){const t=$("toast");t.textContent=msg;t.style.display="block";clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.style.display="none",4500)}
function pill(el,text,kind="gray"){el.textContent=text;el.className="pill "+kind}
async function api(url,opts={}){const r=await fetch(url,{headers:{"Content-Type":"application/json"},...opts});let data;try{data=await r.json()}catch{data={detail:await r.text()}}if(!r.ok)throw new Error(data.detail||data.message||`HTTP ${r.status}`);return data}
async function refresh(){
  try{
    const s=await api("/api/status");
    pill($("appPill"),"LOCAL BACKEND ONLINE","green");
    $("cameraStatus").textContent=s.camera.status;
    $("cameraMeta").textContent=s.camera.error||`Source: ${s.camera.source??"not selected"} · ${s.camera.fps} FPS`;
    $("cameraFps").textContent=s.camera.fps?`${s.camera.fps} FPS`:"—";
    $("aiStatus").textContent=s.ai.loaded?"Model loaded":(s.ai.error?"AI error":"Not loaded");
    $("gpuMeta").textContent=s.ai.gpu_available?`CUDA available · ${s.ai.gpu_name}`:"CUDA unavailable; CPU fallback";
    $("device").textContent=s.ai.device;
    $("inferMs").textContent=s.ai.inference_ms==null?"—":`${s.ai.inference_ms} ms`;
    $("aiFps").textContent=s.ai.ai_fps==null?"—":`${s.ai.ai_fps} FPS`;
    $("espStatus").textContent=s.esp.connected?"Connected":"Not connected";
    $("espMeta").textContent=s.esp.message||"Not tested";
    $("lastCommand").textContent=s.last_command;
    $("commandMeta").textContent=s.esp.last_check||"";
    const d=s.detection||{};
    $("personDetected").textContent=d.error?`Error: ${d.error}`:(d.person?"YES":"NO / not detected");
    $("obstacles").textContent=d.error?"—":`${(d.obstacles||[]).length} detected`;
    if($("obstacleWarning")) $("obstacleWarning").textContent=d.error?"AI error":(d.obstacle_warning?"CAUTION — object in path":"No vision warning");
    if($("followToggle")) $("followToggle").checked=!!s.follow_enabled;
    if($("obstacleToggle")) $("obstacleToggle").checked=!!s.obstacle_enabled;
    pill($("detectionPill"),d.error?"AI ERROR":(d.person?"PERSON DETECTED":"Vision ready"),d.error?"red":(d.person?"green":"gray"));
    $("ocrStatus").textContent=s.settings.ocr_enabled?"Enabled (run on request)":"Disabled";
    $("events").innerHTML=(s.events||[]).slice().reverse().map(e=>`<div class="event ${e.level.toLowerCase()}"><time>${esc(e.time)}</time><span class="kind">${esc(e.kind)}</span><span>${esc(e.message)}</span></div>`).join("")||'<div class="event">No events</div>';
    if(s.camera.status==="Connected"){pill($("videoPill"),"CAMERA LIVE","green");$("videoOverlay").style.display="none";if($("video").getAttribute("src"))$("video").style.display="block";}
    else {pill($("videoPill"),s.camera.status,"gray");if(!$("video").getAttribute("src")){$("videoOverlay").style.display="block";$("video").style.display="none";}}
  }catch(e){pill($("appPill"),"BACKEND ERROR","red");toast(e.message)}
}
function esc(x){return String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function saveSettings(ev){
  ev?.preventDefault();
  try{
    const data=await api("/api/settings",{method:"POST",body:JSON.stringify({
      esp_url:$("espUrl").value,camera_source:$("cameraSource").value,model_path:$("modelPath").value,
      confidence:Number($("confidence").value),ocr_enabled:$("ocrToggle").checked,obstacle_demo:true
    })});
    toast("Settings saved for this session.");eventStatus("SETTINGS","Configuration saved.");
  }catch(e){toast(e.message)}
}
function eventStatus(kind,msg){$("commandStatus").textContent=`${kind}: ${msg}`}
async function command(cmd){
  if(commandBusy)return;commandBusy=true;
  if($("followToggle").checked){$("followToggle").checked=false;try{await api("/api/follow",{method:"POST",body:JSON.stringify({enabled:false})})}catch{}}
  if($("obstacleToggle").checked){$("obstacleToggle").checked=false;try{await api("/api/obstacle",{method:"POST",body:JSON.stringify({enabled:false})})}catch{}}
  try{
    const result=await api("/api/command",{method:"POST",body:JSON.stringify({command:cmd})});
    eventStatus("COMMAND",`${cmd} accepted by ESP. Delivery is not proof of physical motor execution.`);
    $("lastCommand").textContent=cmd;
    if(cmd==="STOP")pill($("appPill"),"STOP SENT","yellow");
  }catch(e){eventStatus("COMMAND ERROR",e.message);toast(e.message)}
  finally{commandBusy=false;refresh()}
}
function stop(){heldCommand=null;command("STOP")}
document.querySelectorAll("[data-command]").forEach(btn=>{
  const start=(ev)=>{ev.preventDefault();if(heldCommand)return;heldCommand=btn.dataset.command;command(heldCommand)};
  const end=(ev)=>{if(ev)ev.preventDefault();if(heldCommand){heldCommand=null;command("STOP")}};
  btn.addEventListener("pointerdown",start);
  btn.addEventListener("pointerup",end);btn.addEventListener("pointercancel",end);btn.addEventListener("pointerleave",end);
  btn.addEventListener("contextmenu",e=>e.preventDefault());
});
$("stopNow").addEventListener("click",stop);$("emergency").addEventListener("click",stop);
window.addEventListener("blur",stop);document.addEventListener("visibilitychange",()=>{if(document.hidden)stop()});
window.addEventListener("beforeunload",()=>{navigator.sendBeacon("/api/command",new Blob([JSON.stringify({command:"STOP"})],{type:"application/json"}))});
$("settingsForm").addEventListener("submit",saveSettings);
$("startCamera").addEventListener("click",async()=>{await saveSettings();try{await api("/api/camera/start",{method:"POST"});$("video").src="/video.mjpg?ts="+Date.now();$("video").style.display="block";$("videoOverlay").style.display="none";toast("Camera started")}catch(e){toast(e.message)}refresh()});
$("stopCamera").addEventListener("click",async()=>{try{await api("/api/camera/stop",{method:"POST"});$("video").removeAttribute("src");$("video").style.display="none";$("videoOverlay").style.display="block";toast("Camera stopped; STOP sent best-effort")}catch(e){toast(e.message)}refresh()});
$("loadAI").addEventListener("click",async()=>{await saveSettings();try{const r=await api("/api/ai/load");toast(`AI ready: ${r.device}`)}catch(e){toast(e.message)}refresh()});
$("aiPreview").addEventListener("click",()=>{if(aiTimer){clearInterval(aiTimer);aiTimer=null;$("aiPreview").textContent="AI Preview";$("video").src="/video.mjpg?ts="+Date.now();return}
  $("aiPreview").textContent="Stop AI Preview";
  aiTimer=setInterval(async()=>{try{const r=await fetch("/api/ai/frame.jpg");if(r.ok){const blob=await r.blob();const old=$("video").dataset.objectUrl;if(old)URL.revokeObjectURL(old);const u=URL.createObjectURL(blob);$("video").src=u;$("video").dataset.objectUrl=u}else{const d=await r.json();toast(d.detail||"AI frame unavailable")}}catch(e){toast(e.message)}},250);
});
$("testESP").addEventListener("click",async()=>{await saveSettings();try{const r=await api("/api/esp/test");eventStatus("ESP TEST","Connected; /status received.");toast("ESP connection test passed.")}catch(e){eventStatus("ESP TEST FAILED",e.message);toast(e.message)}refresh()});
$("followToggle").addEventListener("change",async()=>{
  if($("followToggle").checked){$("obstacleToggle").checked=false;try{await api("/api/obstacle",{method:"POST",body:JSON.stringify({enabled:false})})}catch{}}
  try{const r=await api("/api/follow",{method:"POST",body:JSON.stringify({enabled:$("followToggle").checked})});toast(r.follow_enabled?"Person Following Mode enabled":"Person Following Mode disabled; STOP requested")}catch(e){toast(e.message);$("followToggle").checked=false}refresh();
});
$("obstacleToggle").addEventListener("change",async()=>{
  if($("obstacleToggle").checked){$("followToggle").checked=false;try{await api("/api/follow",{method:"POST",body:JSON.stringify({enabled:false})})}catch{}}
  try{const r=await api("/api/obstacle",{method:"POST",body:JSON.stringify({enabled:$("obstacleToggle").checked})});toast(r.obstacle_enabled?"Obstacle Avoidance Mode enabled":"Obstacle Avoidance Mode disabled; STOP requested")}catch(e){toast(e.message);$("obstacleToggle").checked=false}refresh();
});
$("runOCR").addEventListener("click",async()=>{try{const r=await api("/api/ocr");toast(r.results.map(x=>`${x.text} (${x.confidence})`).join(" · ")||"No text found");$("demoStatus").textContent="OCR results: "+JSON.stringify(r.results)}catch(e){toast(e.message)}});
$("demoButton").addEventListener("click",()=>{demo=!demo;$("demoButton").textContent=demo?"Teacher Demo: Stop":"Teacher Demo: Start";$("demoStatus").textContent=demo?"Teacher demo active: show camera, detection status, connection tests and event log. Movement remains manual unless explicitly enabled.":"Teacher demo idle.";toast(demo?"Teacher demo mode enabled":"Teacher demo mode stopped")});
$("clearEvents").addEventListener("click",()=>$("events").innerHTML='<div class="event">View cleared locally; server log retained.</div>');
setInterval(()=>{$("clock").textContent=new Date().toLocaleTimeString()},1000);
refresh();pollTimer=setInterval(refresh,2000);
