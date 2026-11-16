#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ES32Lab.h>
#include <math.h>

// pinos
#define PINO_LDR 36
#define PINO_TEMP 39
#define PINO_SOLO 35
#define PINO_BOTAO_FESTA 0

// leds
#define LED_VERDE 17
#define LED_AMARELO 16
#define LED_VERMELHO 13

// wifi
const char* NOME_WIFI = "osguri";
const char* SENHA_WIFI = "planta123";

// dns
const char* NOME_DNS = "pet.planta";

// config do ip
IPAddress IP_NOTEBOOK(192, 168, 4, 2);

IPAddress IP_ESP32(192, 168, 4, 1);
IPAddress MASCARA_REDE(255, 255, 255, 0);

const bool INVERTER_LUZ = false;
const bool INVERTER_SOLO = true;

// lcd
ES_TFT tela;
WebServer servidor(80);
DNSServer dns;

// variaveis
int luz = 0;
int solo = 0;
float temperatura = NAN;
String humor = "aguardando";
bool critico = false;
bool modoFesta = false;
unsigned long ultimaLeitura = 0;
bool botaoFestaEstavel = HIGH;
bool ultimaLeituraBotaoFesta = HIGH;
unsigned long ultimaMudancaBotaoFesta = 0;

// leds
void atualizarLeds() {
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_AMARELO, LOW);
  digitalWrite(LED_VERMELHO, LOW);

  if (modoFesta) {
    digitalWrite(LED_VERDE, HIGH);
  } else if (critico) {
    digitalWrite(LED_VERMELHO, HIGH);
  } else if (humor == "feliz" || humor == "oculos" || humor == "festa") {
    digitalWrite(LED_VERDE, HIGH);
  } else if (humor == "seca" || humor == "frio" || humor == "doente") {
    digitalWrite(LED_AMARELO, HIGH);
  }
}

// sensores
void lerSensores() {
  int leituraLuz = analogRead(PINO_LDR);
  int leituraSolo = analogRead(PINO_SOLO);
  int leituraTemp = analogRead(PINO_TEMP);

  luz = leituraLuz / 4;
  solo = leituraSolo / 4;

  if (INVERTER_LUZ) {
    luz = 1023 - luz;
  }
  if (INVERTER_SOLO) {
    solo = 1023 - solo;
  }

  if (leituraTemp > 0 && leituraTemp < 4095) {
    float r = (float)leituraTemp / (4095.0 - leituraTemp);
    float rRef = 1850.0 / (4095.0 - 1850.0);

    temperatura = 1.0 / (
      1.0 / 296.15 + log(r / rRef) / 3950.0
    ) - 273.15;
  } else {
    temperatura = NAN;
  }
}

// lcd
void mostrarDisplay() {
  tela.fillScreen(TFT_BLACK);

  tela.setTextColor(TFT_GREEN);
  tela.drawString("PETPLANTA", 5, 4, 2);

  tela.setTextColor(TFT_WHITE);
  if (isfinite(temperatura)) {
    tela.drawString("Temp: " + String(temperatura, 1) + " C", 5, 28, 2);
  } else {
    tela.drawString("Temp: erro", 5, 28, 2);
  }

  tela.drawString("Luz: " + String(luz), 5, 50, 2);
  tela.drawString("Solo: " + String(solo), 5, 72, 2);

  tela.setTextColor(modoFesta ? TFT_MAGENTA : (critico ? TFT_RED : TFT_CYAN));
  tela.drawString("Humor: " + String(modoFesta ? "festa" : humor), 5, 94, 1);

  tela.setTextColor(TFT_YELLOW);
  tela.drawString("Acesse: pet.planta", 5, 110, 1);
}

// botao
void lerBotaoFesta() {
  bool leitura = digitalRead(PINO_BOTAO_FESTA);

  if (leitura != ultimaLeituraBotaoFesta) {
    ultimaMudancaBotaoFesta = millis();
    ultimaLeituraBotaoFesta = leitura;
  }

  if (millis() - ultimaMudancaBotaoFesta < 50) {
    return;
  }

  if (leitura != botaoFestaEstavel) {
    botaoFestaEstavel = leitura;
    if (botaoFestaEstavel == LOW) {
      modoFesta = !modoFesta;
      Serial.println(modoFesta ? ">> Modo festa ativado!" : ">> Modo festa desativado!");
      atualizarLeds();
      mostrarDisplay();
    }
  }
}

// rotas http
void paginaInicial() {
  String destino = "http://" + IP_NOTEBOOK.toString() + "/";
  servidor.sendHeader("Location", destino);
  servidor.send(302, "text/plain", "Abrindo PetPlanta: " + destino);
}

// dados dos sensores
void enviarDados() {
  String json = "{\"luz\":" + String(luz);
  json += ",\"solo\":" + String(solo);
  json += ",\"temperatura\":";

  if (isfinite(temperatura)) {
    json += String(temperatura, 1);
  } else {
    json += "null";
  }

  json += ",\"humor\":\"" + humor + "\"";
  json += ",\"critico\":";
  json += (critico ? "true" : "false");
  json += ",\"festa\":";
  json += (modoFesta ? "true" : "false");
  json += ",\"tempo_ms\":" + String(millis()) + "}";

  servidor.sendHeader("Cache-Control", "no-store");
  servidor.send(200, "application/json", json);
}

// comandos
void receberComando() {
  if (!servidor.hasArg("comando")) {
    servidor.send(400, "text/plain", "Faltou comando");
    return;
  }

  String comando = servidor.arg("comando");

  if (comando.startsWith("MOOD:")) {
    String novoHumor = comando.substring(5);

    if (novoHumor != "feliz" && novoHumor != "seca" &&
        novoHumor != "doente" && novoHumor != "frio" &&
        novoHumor != "dormindo" && novoHumor != "oculos" &&
        novoHumor != "festa") {
      servidor.send(400, "text/plain", "Humor invalido");
      return;
    }

    humor = novoHumor;
  } else if (comando == "CRITICO:1") {
    critico = true;
  } else if (comando == "CRITICO:0") {
    critico = false;
  } else {
    servidor.send(400, "text/plain", "Comando desconhecido");
    return;
  }

  atualizarLeds();
  mostrarDisplay();
  servidor.send(200, "application/json", "{\"ok\":true}");
}

// setup
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PINO_BOTAO_FESTA, INPUT_PULLUP);
  atualizarLeds();

  tela.begin();
  tela.setRotation(3);
  tela.fillScreen(TFT_BLACK);
  tela.drawString("Iniciando...", 5, 15, 2);

  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(IP_ESP32, IP_ESP32, MASCARA_REDE);
  bool redeOK = WiFi.softAP(NOME_WIFI, SENHA_WIFI);

  if (redeOK) {
    Serial.print("Rede iniciada. IP ESP32: ");
    Serial.println(WiFi.softAPIP());

    if (dns.start(53, NOME_DNS, IP_ESP32)) {
      Serial.println("DNS funcionando: http://pet.planta");
    } else {
      Serial.println("Nao foi possivel iniciar o DNS");
    }
  } else {
    Serial.println("Erro ao iniciar Wi-Fi");
  }

  lerSensores();
  mostrarDisplay();

  servidor.on("/", HTTP_GET, paginaInicial);
  servidor.on("/dados", HTTP_GET, enviarDados);
  servidor.on("/comando", HTTP_POST, receberComando);
  servidor.begin();

  ultimaLeitura = millis();
}

// loop
void loop() {
  servidor.handleClient();
  dns.processNextRequest();
  lerBotaoFesta();

  if (millis() - ultimaLeitura >= 1000) {
    ultimaLeitura = millis();

    lerSensores();
    mostrarDisplay();

    Serial.print("Luz: ");
    Serial.print(luz);
    Serial.print(" | Solo: ");
    Serial.print(solo);
    Serial.print(" | Temperatura: ");
    Serial.println(temperatura, 1);
  }
}
