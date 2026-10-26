#include <AFMotor.h>
#include <SoftwareSerial.h>

// For a classic L293D AFMotor Shield V1 / HW-130 clone.
// Motor mapping: M1 front-right, M2 front-left, M3 rear-left, M4 rear-right.
AF_DCMotor m1(1), m2(2), m3(3), m4(4);
// ESP8266 D6 (TX) -> Arduino D2 (RX). D3 is unused by the ESP in this wiring.
SoftwareSerial espSerial(2, 3);

// HC-SR04: TRIG -> A0, ECHO -> A1, VCC -> 5V, GND -> GND.
const uint8_t TRIG_PIN = A0;
const uint8_t ECHO_PIN = A1;
const uint8_t SPEED = 135;                 // keep low for first tests
const uint8_t TURN_SPEED = 125;
const int STOP_DISTANCE_CM = 18;           // stop before the obstacle, not at 3 cm
const unsigned long COMMAND_TIMEOUT_MS = 1200;
const unsigned long AVOID_COOLDOWN_MS = 1400;

unsigned long lastCommandAt = 0;
unsigned long avoidUntil = 0;
String line;

void allSpeed(uint8_t s) {
  m1.setSpeed(s); m2.setSpeed(s); m3.setSpeed(s); m4.setSpeed(s);
}
void stopMotors() {
  m1.run(RELEASE); m2.run(RELEASE); m3.run(RELEASE); m4.run(RELEASE);
}

// Wheel direction compensation: M1 and M3 are inverted for this project's current layout.
// If a wheel still spins the wrong way, change only its FORWARD/BACKWARD here.
void logicalForward() {
  m1.run(BACKWARD); m2.run(FORWARD); m3.run(BACKWARD); m4.run(FORWARD);
}
void logicalBackward() {
  m1.run(FORWARD); m2.run(BACKWARD); m3.run(FORWARD); m4.run(BACKWARD);
}
void turnLeft() {
  // Pivot left: left wheels backward, right wheels forward (compensated for wheel orientation).
  m1.run(BACKWARD); m2.run(BACKWARD); m3.run(FORWARD); m4.run(FORWARD);
}
void turnRight() {
  m1.run(FORWARD); m2.run(FORWARD); m3.run(BACKWARD); m4.run(BACKWARD);
}

long readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 25000UL);
  if (duration == 0) return -1;  // no echo: treat as unknown and fail safe
  return (long)(duration * 0.0343 / 2.0);
}

void avoidObstacle(long distanceCm) {
  stopMotors();
  Serial.print("OBSTACLE: "); Serial.print(distanceCm); Serial.println(" cm; avoiding");
  // Pivot in place rather than reversing, because there is no rear-facing sensor.
  allSpeed(TURN_SPEED);
  turnRight(); delay(360);
  stopMotors();
  avoidUntil = millis() + AVOID_COOLDOWN_MS;
}

void drive(const String& c) {
  if (c == "STOP") { stopMotors(); return; }
  if (c == "FORWARD") {
    if ((long)(avoidUntil - millis()) > 0) { stopMotors(); return; }
    long distanceCm = readDistanceCm();
    if (distanceCm < 0) {
      stopMotors();
      Serial.println("SAFETY STOP: HC-SR04 returned no echo; check sensor/wiring");
      return;
    }
    if (distanceCm <= STOP_DISTANCE_CM) { avoidObstacle(distanceCm); return; }
    allSpeed(SPEED); logicalForward(); return;
  }
  if (c == "BACKWARD") { allSpeed(SPEED); logicalBackward(); return; }
  if (c == "LEFT") { allSpeed(TURN_SPEED); turnLeft(); return; }
  if (c == "RIGHT") { allSpeed(TURN_SPEED); turnRight(); return; }
  stopMotors();
}

void setup() {
  Serial.begin(115200);
  espSerial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  stopMotors();
  lastCommandAt = millis();
  Serial.println("AUTONOVA Arduino ready; ultrasonic forward guard enabled; motors stopped");
}

void loop() {
  while (espSerial.available()) {
    char c = (char)espSerial.read();
    if (c == '\n' || c == '\r') {
      line.trim(); line.toUpperCase();
      if (line.length()) {
        if (line == "FORWARD" || line == "BACKWARD" || line == "LEFT" || line == "RIGHT" || line == "STOP") {
          drive(line);
        } else {
          stopMotors();
          Serial.print("Unknown command, stopped: "); Serial.println(line);
        }
        lastCommandAt = millis();
        Serial.print("Command received: "); Serial.println(line);
        line = "";
      }
    } else if (line.length() < 24) {
      line += c;
    } else {
      line = ""; stopMotors();
    }
  }
  // If the laptop/ESP stops refreshing commands, the robot stops locally.
  if (millis() - lastCommandAt > COMMAND_TIMEOUT_MS) stopMotors();
}
