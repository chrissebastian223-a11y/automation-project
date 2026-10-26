#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// Set these to your own 2.4 GHz Wi-Fi credentials before uploading.
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// User wiring: ESP8266 TX0 (GPIO1) -> Arduino UNO D2 (SoftwareSerial RX).
// Commands share the ESP hardware UART at 9600 baud. Disconnect TX0 from UNO D2 while flashing ESP firmware.
ESP8266WebServer server(80);
String lastCommand = "STOP";
unsigned long lastCommandAt = 0;
const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Serving Cart</title>
<style>body{font:16px Arial;background:#101827;color:#fff;text-align:center;padding:20px}.grid{display:grid;grid-template-columns:repeat(3,100px);gap:10px;justify-content:center}button{height:65px;border:0;border-radius:10px;font-weight:bold}.move{background:#477cf5;color:#fff}.stop{background:#e53935;color:#fff}#s{margin:20px}</style></head><body><h2>Autonomous Serving Cart</h2><div class="grid"><span></span><button class="move" onclick="send('FORWARD')">FORWARD</button><span></span><button class="move" onclick="send('LEFT')">LEFT</button><button class="stop" onclick="send('STOP')">STOP</button><button class="move" onclick="send('RIGHT')">RIGHT</button><span></span><button class="move" onclick="send('BACKWARD')">BACKWARD</button><span></span></div><p id="s">Ready</p><script>async function send(c){try{let r=await fetch('/command?cmd='+c);document.getElementById('s').textContent=await r.text()}catch(e){document.getElementById('s').textContent='Request failed'}}window.addEventListener('pagehide',()=>fetch('/command?cmd=STOP',{keepalive:true}));document.addEventListener('visibilitychange',()=>{if(document.hidden)send('STOP')});</script></body></html>
)HTML";

bool validCommand(const String& c) {
  return c == "FORWARD" || c == "BACKWARD" || c == "LEFT" || c == "RIGHT" || c == "STOP";
}
void stopOnDisconnect() { Serial.println("STOP"); lastCommand = "STOP"; }
void handleRoot() { server.send_P(200, "text/html", PAGE); }
void handleStatus() {
  String json = "{\"device\":\"ESP8266\",\"wifi\":\"";
  json += WiFi.status() == WL_CONNECTED ? "connected" : "disconnected";
  json += "\",\"ip\":\"" + WiFi.localIP().toString() + "\",\"lastCommand\":\"" + lastCommand + "\"}";
  server.send(200, "application/json", json);
}
void handleCommand() {
  if (!server.hasArg("cmd")) { server.send(400, "application/json", "{\"ok\":false,\"error\":\"missing cmd\"}"); return; }
  String cmd = server.arg("cmd"); cmd.trim(); cmd.toUpperCase();
  if (!validCommand(cmd)) { server.send(400, "application/json", "{\"ok\":false,\"error\":\"invalid command\"}"); return; }
  Serial.println(cmd); lastCommand = cmd; lastCommandAt = millis();
  String json = "{\"ok\":true,\"command\":\"" + cmd + "\",\"delivery\":\"serial_sent_not_acknowledged_by_Arduino\"}";
  server.send(200, "application/json", json);
}
void setup() {
  Serial.begin(9600);
  WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 25000) { delay(500); }
  server.on("/", HTTP_GET, handleRoot); server.on("/status", HTTP_GET, handleStatus); server.on("/command", HTTP_GET, handleCommand);
  server.begin();
}
void loop() {
  server.handleClient();
  // Keep the web server responsive. Arduino firmware also has its own watchdog.
  if (WiFi.status() != WL_CONNECTED && lastCommand != "STOP") stopOnDisconnect();
}
