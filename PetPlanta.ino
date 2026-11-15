#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ES32Lab.h>
#include <math.h>

// Pinos dos sensores
#define PINO_LDR 36
#define PINO_TEMP 39
#define PINO_SOLO 35
#define PINO_BOTAO_FESTA 0  // botao BOOT da placa ESP32, ativo em LOW

// LEDs da ES32Lab (cores fixas)
#define LED_VERDE 17
#define LED_AMARELO 16
#define LED_VERMELHO 13

// Rede criada pelo proprio ESP32
const char* NOME_WIFI = "osguri";
const char* SENHA_WIFI = "planta123";

// DNS local: digitar http://pet.planta no celular.
const char* NOME_DNS = "pet.planta";

// Endereco do notebook onde o Flask esta rodando.
// Confira com ipconfig: o notebook deve continuar neste IP.
IPAddress IP_NOTEBOOK(192, 168, 4, 2);

// Endereco fixo do ESP32 na rede osguri.
IPAddress IP_ESP32(192, 168, 4, 1);
IPAddress MASCARA_REDE(255, 255, 255, 0);

// Mantemos os valores de luz e solo entre 0 e 1023 para o Python.
// Se algum sensor indicar o contrario do esperado, troque false/true.
const bool INVERTER_LUZ = false;
const bool INVERTER_SOLO = true;

ES_TFT tela;
WebServer servidor(80);
DNSServer dns;

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

// Acende apenas o LED correspondente ao estado da planta.
// O sinal CRITICO tem prioridade sobre o humor.
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
  // Dormindo ou aguardando: todos apagados.
}

// Le os sensores analogicos do PetPlanta.
void lerSensores() {
  int leituraLuz = analogRead(PINO_LDR);
  int leituraSolo = analogRead(PINO_SOLO);
  int leituraTemp = analogRead(PINO_TEMP);

  // O ADC do ESP32 usa 12 bits (0 a 4095).
  // O programa Python antigo espera 10 bits (0 a 1023).
  luz = leituraLuz / 4;
  solo = leituraSolo / 4;

  if (INVERTER_LUZ) {
    luz = 1023 - luz;
  }
  if (INVERTER_SOLO) {
    solo = 1023 - solo;
  }

  // Conversao aproximada, com a referencia usada nos nossos testes:
  // leitura 1850 corresponde a aproximadamente 23 graus Celsius.
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

// Mostra as leituras no display TFT, que utiliza SPI.
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

// Alterna o modo festa pelo botao BOOT da placa. O debounce impede que um
// unico aperto mecanico seja interpretado como varios cliques.
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

// Redireciona o navegador para a pagina Flask no notebook.
// O DNS aponta pet.planta para o ESP32, e o ESP32 faz o redirecionamento.
void paginaInicial() {
  // O Flask escuta na porta HTTP padrao (80), entao o endereco fica limpo
  // para o usuario e pode ser acessado apenas como http://pet.planta.
  String destino = "http://" + IP_NOTEBOOK.toString() + "/";
  servidor.sendHeader("Location", destino);
  servidor.send(302, "text/plain", "Abrindo PetPlanta: " + destino);
}

// O Python acessa GET /dados para receber as leituras em JSON.
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

// O Python acessa POST /comando para mudar o humor ou o alerta.
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

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PINO_BOTAO_FESTA, INPUT_PULLUP);
  atualizarLeds();

  // Inicializa o display da ES32Lab.
  tela.begin();
  tela.setRotation(3);
  tela.fillScreen(TFT_BLACK);
  tela.drawString("Iniciando...", 5, 15, 2);

  // Rede propria, sem depender da internet da universidade.
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(IP_ESP32, IP_ESP32, MASCARA_REDE);
  bool redeOK = WiFi.softAP(NOME_WIFI, SENHA_WIFI);

  if (redeOK) {
    Serial.print("Rede iniciada. IP ESP32: ");
    Serial.println(WiFi.softAPIP());

    // Responde pet.planta com o IP do ESP32.
    // Quando o navegador abre /, sera redirecionado para o Flask.
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

  // Enderecos que o notebook pode acessar por HTTP.
  servidor.on("/", HTTP_GET, paginaInicial);
  servidor.on("/dados", HTTP_GET, enviarDados);
  servidor.on("/comando", HTTP_POST, receberComando);
  servidor.begin();

  ultimaLeitura = millis();
}

void loop() {
  // Servidor HTTP e DNS da rede local.
  servidor.handleClient();
  dns.processNextRequest();
  lerBotaoFesta();

  // Atualiza os sensores uma vez por segundo.
  // millis() evita parar o atendimento HTTP com delay(1000).
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
