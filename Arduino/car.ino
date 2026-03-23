char command = "";      // a String to hold incoming data
const int DRIVER1_1 = 8;
const int DRIVER1_2 = 9;
const int DRIVER2_1 = 10;
const int DRIVER2_2 = 11;

const int SENSOR_FR = 4;
const int SENSOR_FL = 5;
const int SENSOR_BR = 6;
const int SENSOR_BL = 7;

const int ENGINES_POWER = 3;

void setup() {
  Serial.begin(9600);
  pinMode(DRIVER2_2, OUTPUT);   //left motors forward
  pinMode(DRIVER2_1, OUTPUT);   //left motors reverse
  pinMode(DRIVER1_2, OUTPUT);   //right motors forward
  pinMode(DRIVER1_1, OUTPUT);   //right motors reverse
  pinMode(ENGINES_POWER, OUTPUT);

  pinMode(SENSOR_FR, INPUT);   //left motors forward
  pinMode(SENSOR_FL, INPUT);   //left motors reverse
  pinMode(SENSOR_BR, INPUT);   //right motors forward
  pinMode(SENSOR_BL, INPUT);   //right motors reverse
}

void loop() {
  switch (command) {
    case 'W':
      forward();
      break;
    case 'S':
      backward();
      break;
    case 'A':
      left();
      break;
    case 'D':
      right();
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
  digitalWrite(ENGINES_POWER, HIGH);
}

void turn_engines_off() {
  digitalWrite(ENGINES_POWER, LOW);
}


void forward() {
  digitalWrite(DRIVER2_2,HIGH);
  digitalWrite(DRIVER2_1,LOW);
  digitalWrite(DRIVER1_2,HIGH);
  digitalWrite(DRIVER1_1,LOW);
}

void backward() {
  digitalWrite(DRIVER2_2,LOW);
  digitalWrite(DRIVER2_1,HIGH);
  digitalWrite(DRIVER1_2,LOW);
  digitalWrite(DRIVER1_1,HIGH);
}

void left() {
  digitalWrite(DRIVER2_2,LOW);
  digitalWrite(DRIVER2_1,LOW);
  digitalWrite(DRIVER1_2,HIGH);
  digitalWrite(DRIVER1_1,LOW);
}

void right() {
  digitalWrite(DRIVER2_2,HIGH);
  digitalWrite(DRIVER2_1,LOW);
  digitalWrite(DRIVER1_2,LOW);
  digitalWrite(DRIVER1_1,LOW);
}

void stop() {
  digitalWrite(DRIVER2_2,LOW);
  digitalWrite(DRIVER2_1,LOW);
  digitalWrite(DRIVER1_2,LOW);
  digitalWrite(DRIVER1_1,LOW);
}
