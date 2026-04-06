char command = "";      // a String to hold incoming data
const int DRIVER1_1 = 8;
const int DRIVER1_2 = 9;
const int DRIVER2_1 = 10;
const int DRIVER2_2 = 11;
const int DRIVER3_1 = 4;
const int DRIVER3_2 = 5;
const int DRIVER4_1 = 6;
const int DRIVER4_2 = 7;

const int SENSOR_FR = 0;
const int SENSOR_FL = 1;
const int SENSOR_BR = 2;
const int SENSOR_BL = 3;

const int ENGINES_POWER = 12;

// Motor enum definition
enum Motor {
  BackLeft = 0,
  FrontLeft = 1,
  BackRight = 2,
  FrontRight = 3
};

// State enum definition
enum State {
  Stop = 0,
  Forward = 1,
  Reverse = 2
};

// Motor reversal flags: true means the motor's forward/reverse are inverted
bool motorReversed[4] = {false, false, false, false};

void setup() {
  Serial.begin(9600);
  pinMode(DRIVER4_2, OUTPUT);
  pinMode(DRIVER4_1, OUTPUT);
  pinMode(DRIVER3_2, OUTPUT);
  pinMode(DRIVER3_1, OUTPUT);
  pinMode(DRIVER2_2, OUTPUT);
  pinMode(DRIVER2_1, OUTPUT);
  pinMode(DRIVER1_2, OUTPUT);
  pinMode(DRIVER1_1, OUTPUT);
  pinMode(ENGINES_POWER, OUTPUT);

  pinMode(SENSOR_FR, INPUT);
  pinMode(SENSOR_FL, INPUT);
  pinMode(SENSOR_BR, INPUT);
  pinMode(SENSOR_BL, INPUT);

  setMotorReversed(FrontLeft, true);
  setMotorReversed(BackRight, true);
}

void loop() {
  switch (command) {
    case 'W':
    case 'w':
      forward();
      break;
    case 'S':
    case 's':
      backward();
      break;
    case 'A':
    case 'a':
      left();
      break;
    case 'D':
    case 'd':
      right();
      break;
    case 'L':
    case 'l':
      rotate_cw();
      break;
    case 'J':
    case 'j':
      rotate_ccw();
      break;
    case 'E':
    case 'e':
      top_right();
      break;
    case 'Q':
    case 'q':
      top_left();
      break;
    case 'C':
    case 'c':
      bottom_right();
      break;
    case 'Z':
    case 'z':
      bottom_left();
      break;
    case '1':
      turn_engines_on();
      break;
    case '0':
      turn_engines_off();
      break;    
    default:
      stop();
      break;
  }
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    command = inChar;
  }
}

void turn_engines_on() {
  stop();
  digitalWrite(ENGINES_POWER, HIGH);
}

void turn_engines_off() {
  stop();
  digitalWrite(ENGINES_POWER, LOW);
}

// Set motor state (Forward, Reverse, or Stop)
// Handles motor reversal by checking motorReversed[] array
void setMotorState(Motor motor, State state) {
  int pin1, pin2;
  bool forward_pin_active = true;  // Assume normal wiring
  
  // Map motor enum to driver pins
  switch(motor) {
    case BackLeft:
      pin1 = DRIVER1_1;
      pin2 = DRIVER1_2;
      break;
    case FrontLeft:
      pin1 = DRIVER2_1;
      pin2 = DRIVER2_2;
      break;
    case BackRight:
      pin1 = DRIVER3_1;
      pin2 = DRIVER3_2;
      break;
    case FrontRight:
      pin1 = DRIVER4_1;
      pin2 = DRIVER4_2;
      break;
  }
  
  // Check if motor is reversed, and invert the logic if needed
  if (motorReversed[motor]) {
    forward_pin_active = !forward_pin_active;
  }
  
  // Apply state to motor pins
  switch(state) {
    case Forward:
      digitalWrite(forward_pin_active ? pin2 : pin1, HIGH);
      digitalWrite(forward_pin_active ? pin1 : pin2, LOW);
      break;
    case Reverse:
      digitalWrite(forward_pin_active ? pin2 : pin1, LOW);
      digitalWrite(forward_pin_active ? pin1 : pin2, HIGH);
      break;
    case Stop:
      digitalWrite(pin1, LOW);
      digitalWrite(pin2, LOW);
      break;
  }
}

// Set motor reversal flag for a specific motor
void setMotorReversed(Motor motor, bool reversed) {
  motorReversed[motor] = reversed;
}

void forward() {
  setMotorState(FrontRight, Forward);
  setMotorState(BackRight, Forward);
  setMotorState(FrontLeft, Forward);
  setMotorState(BackLeft, Forward);
}

void backward() {
  setMotorState(FrontRight, Reverse);
  setMotorState(BackRight, Reverse);
  setMotorState(FrontLeft, Reverse);
  setMotorState(BackLeft, Reverse);
}

void left() {
  setMotorState(FrontLeft, Forward);
  setMotorState(BackLeft, Reverse);
  setMotorState(FrontRight, Reverse);
  setMotorState(BackRight, Forward);
}

void right() {
  setMotorState(FrontLeft, Reverse);
  setMotorState(BackLeft, Forward);
  setMotorState(FrontRight, Forward);
  setMotorState(BackRight, Reverse);
}

void rotate_ccw() {
  setMotorState(FrontLeft, Stop);
  setMotorState(BackLeft, Stop);
  setMotorState(FrontRight, Forward);
  setMotorState(BackRight, Forward);
}

void rotate_cw() {
  setMotorState(FrontLeft, Forward);
  setMotorState(BackLeft, Forward);
  setMotorState(FrontRight, Stop);
  setMotorState(BackRight, Stop);
}

void top_right() {
  setMotorState(FrontLeft, Forward);
  setMotorState(BackLeft, Stop);
  setMotorState(FrontRight, Stop);
  setMotorState(BackRight, Forward);
}

void top_left() {
  setMotorState(FrontLeft, Stop);
  setMotorState(BackLeft, Forward);
  setMotorState(FrontRight, Forward);
  setMotorState(BackRight, Stop);
}

void bottom_right() {
  setMotorState(FrontLeft, Reverse);
  setMotorState(BackLeft, Stop);
  setMotorState(FrontRight, Stop);
  setMotorState(BackRight, Reverse);
}

void bottom_left() {
  setMotorState(FrontLeft, Stop);
  setMotorState(BackLeft, Reverse);
  setMotorState(FrontRight, Reverse);
  setMotorState(BackRight, Stop);
}

void stop() {
  setMotorState(FrontRight, Stop);
  setMotorState(BackRight, Stop);
  setMotorState(FrontLeft, Stop);
  setMotorState(BackLeft, Stop);
}