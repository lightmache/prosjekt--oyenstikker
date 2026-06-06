#include <Wire.h>
#include <math.h>

#define ACCEL_ADDR 0x19
#define MAG_ADDR   0x1E
#define LD9        PE12

void writeAccel(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ACCEL_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

int16_t readAccel(uint8_t regL) {
  Wire.beginTransmission(ACCEL_ADDR);
  Wire.write(regL | 0x80);
  Wire.endTransmission(false);
  Wire.requestFrom(ACCEL_ADDR, (uint8_t)2);
  uint8_t lo = Wire.read();
  uint8_t hi = Wire.read();
  return (int16_t)((hi << 8) | lo);
}

void writeMag(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

int16_t readMag16(uint8_t reg) {
  Wire.beginTransmission(MAG_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(MAG_ADDR, (uint8_t)2);
  uint8_t hi = Wire.read();
  uint8_t lo = Wire.read();
  return (int16_t)((hi << 8) | lo);
}

void setup() {
  pinMode(LD9, OUTPUT);
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n===== STM32F3 ATTITUDE SNAPSHOT =====");
  Wire.begin();
  Serial.println("[1] Serial OK");
  Serial.println("[2] I2C OK");

  writeAccel(0x20, 0x47);
  writeMag(0x00, 0x14);
  writeMag(0x01, 0x20);
  writeMag(0x02, 0x00);

  delay(200);
  Serial.println("[3] Sensors initialized");

  digitalWrite(LD9, HIGH);
  delay(200);
  digitalWrite(LD9, LOW);

  int16_t ax = readAccel(0x28);
  int16_t ay = readAccel(0x2A);
  int16_t az = readAccel(0x2C);
  int16_t mx = readMag16(0x03);
  int16_t mz = readMag16(0x05);
  int16_t my = readMag16(0x07);

  float roll  = atan2((float)ay, (float)az) * 180.0 / PI;
  float pitch = atan2(-(float)ax, sqrt((float)ay*ay + (float)az*az)) * 180.0 / PI;
  float yaw   = atan2((float)my, (float)mx) * 180.0 / PI;
  if (yaw < 0) yaw += 360.0;

  Serial.println("\n===== ATTITUDE SNAPSHOT =====");
  Serial.print("ACCEL  AX="); Serial.print(ax);
  Serial.print(" AY=");       Serial.print(ay);
  Serial.print(" AZ=");       Serial.println(az);
  Serial.print("MAG    MX="); Serial.print(mx);
  Serial.print(" MY=");       Serial.print(my);
  Serial.print(" MZ=");       Serial.println(mz);
  Serial.print("\nROLL  = "); Serial.print(roll, 2);  Serial.println(" deg");
  Serial.print("PITCH = ");   Serial.print(pitch, 2); Serial.println(" deg");
  Serial.print("YAW   = ");   Serial.print(yaw, 2);   Serial.println(" deg");
  Serial.println("==============================");
}

void loop() {}
