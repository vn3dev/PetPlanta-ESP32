# PetPlanta

Projeto de uma planta virtual controlada por um ESP32. A placa lê os sensores,
mostra informações no LCD da ES32Lab e cria uma rede Wi-Fi própria. O notebook
executa o servidor Flask e entrega a interface para computadores e celulares.

O sketch principal é [PetPlanta.ino](PetPlanta.ino). A interface, os sprites,
os cenários, as transições e os sons ficam em [webapp](webapp/).

## 1. Instalação rápida

### Arduino IDE

1. Instale o Arduino IDE e o suporte para placas ESP32.
2. Instale a biblioteca `ES32Lab`.
3. Abra [PetPlanta.ino](PetPlanta.ino), selecione a placa ESP32 e a porta USB.
4. Compile e envie o sketch para a placa.

O sketch inclui `WiFi`, `WebServer`, `DNSServer`, `ES32Lab` e `math`:

```cpp
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <ES32Lab.h>
#include <math.h>
```

### Python

No PowerShell:

```powershell
cd C:\Users\vinic\Desktop\PetPlanta-Arduino\webapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Se a `.venv` já existir, basta ativá-la antes de executar o app. O servidor
atual é iniciado em `0.0.0.0:80`, conforme [app.py](webapp/app.py):

```python
app.run(host="0.0.0.0", port=80, debug=False, use_reloader=False)
```

O código atual usa `port=80` diretamente em `app.py`; o valor `PORT` de
`config.py` não é usado nessa inicialização.

## 2. Rede, HTTP e DNS

O ESP32 cria uma rede Wi-Fi própria, sem depender da internet:

```cpp
const char* NOME_WIFI = "osguri";
const char* SENHA_WIFI = "planta123";
IPAddress IP_ESP32(192, 168, 4, 1);
IPAddress MASCARA_REDE(255, 255, 255, 0);

WiFi.mode(WIFI_AP);
WiFi.softAPConfig(IP_ESP32, IP_ESP32, MASCARA_REDE);
WiFi.softAP(NOME_WIFI, SENHA_WIFI);
```

Conecte o notebook e o celular à rede `osguri`, com a senha `planta123`. O
notebook deve estar no endereço definido no sketch:

```cpp
IPAddress IP_NOTEBOOK(192, 168, 4, 2);
```

Se o notebook receber outro endereço, confira com `ipconfig`, altere
`IP_NOTEBOOK` e envie o sketch novamente.

O DNS local responde `pet.planta` com o IP do ESP32:

```cpp
const char* NOME_DNS = "pet.planta";
dns.start(53, NOME_DNS, IP_ESP32);
```

Quando o navegador acessa a raiz do ESP32, ele recebe um redirecionamento para
o Flask no notebook:

```cpp
String destino = "http://" + IP_NOTEBOOK.toString() + "/";
servidor.sendHeader("Location", destino);
servidor.send(302, "text/plain", "Abrindo PetPlanta: " + destino);
```

Use `http://pet.planta`. Alguns navegadores tratam `pet.planta` sem `http://`
como pesquisa, dependendo da configuração da barra de endereços.

O ESP32 oferece estas rotas:

```cpp
servidor.on("/", HTTP_GET, paginaInicial);
servidor.on("/dados", HTTP_GET, enviarDados);
servidor.on("/comando", HTTP_POST, receberComando);
```

- `GET /` redireciona para o notebook.
- `GET /dados` entrega luz, solo, temperatura, crítico e festa em JSON.
- `POST /comando` recebe `MOOD:<estado>` e `CRITICO:1` ou `CRITICO:0`.

O Python consulta o ESP32 por padrão em `http://192.168.4.1`, em
[wifi_reader.py](webapp/wifi_reader.py):

```python
ESP32_URL = os.environ.get(
    "PETPLANTA_ESP32_URL", "http://192.168.4.1"
).rstrip("/")
```

## 3. Sensores

Os pinos estão definidos no início de [PetPlanta.ino](PetPlanta.ino):

```cpp
#define PINO_LDR 36
#define PINO_TEMP 39
#define PINO_SOLO 35
```

### Luz

O LDR é lido no GPIO 36. O ADC de 12 bits é convertido para a faixa 0--1023:

```cpp
int leituraLuz = analogRead(PINO_LDR);
luz = leituraLuz / 4;
```

O código considera que valores maiores representam mais luz. `INVERTER_LUZ`
permite inverter essa interpretação se a montagem exigir.

### Solo

O sensor resistivo de umidade está no GPIO 35 e também é convertido para
0--1023. Na montagem atual a leitura é invertida:

```cpp
int leituraSolo = analogRead(PINO_SOLO);
solo = leituraSolo / 4;
const bool INVERTER_SOLO = true;
```

Depois da inversão, valores menores que o limite configurado representam solo
seco para o Python.

### Temperatura

O código atual **não usa DHT11**. A temperatura é lida analogicamente no GPIO
39 e convertida por uma fórmula aproximada baseada na referência de teste de
1850 para cerca de 23 °C:

```cpp
int leituraTemp = analogRead(PINO_TEMP);
float r = (float)leituraTemp / (4095.0 - leituraTemp);
float rRef = 1850.0 / (4095.0 - 1850.0);
temperatura = 1.0 / (
  1.0 / 296.15 + log(r / rRef) / 3950.0
) - 273.15;
```

Se a leitura for inválida, o ESP32 envia `temperatura: null`.

## 4. LCD TFT da ES32Lab

O LCD é controlado pela classe `ES_TFT` da biblioteca `ES32Lab`:

```cpp
ES_TFT tela;

tela.begin();
tela.setRotation(3);
tela.fillScreen(TFT_BLACK);
tela.drawString("Iniciando...", 5, 15, 2);
```

A função `mostrarDisplay()` limpa a tela e mostra título, temperatura, luz,
solo, humor e o endereço de acesso:

```cpp
tela.drawString("PETPLANTA", 5, 4, 2);
tela.drawString("Luz: " + String(luz), 5, 50, 2);
tela.drawString("Solo: " + String(solo), 5, 72, 2);
tela.drawString("Acesse: pet.planta", 5, 110, 1);
```

O sketch não declara os pinos SPI manualmente. A pinagem e a comunicação do
LCD são abstraídas pela biblioteca `ES32Lab` e pelo modelo da placa. Portanto,
o código confirma a inicialização e o uso do display, mas a ligação elétrica
deve seguir a documentação da ES32Lab.

## 5. Botão e LEDs

O botão BOOT da placa ativa o modo festa. Ele usa o GPIO 0, `INPUT_PULLUP` e é
ativo em nível baixo:

```cpp
#define PINO_BOTAO_FESTA 0
pinMode(PINO_BOTAO_FESTA, INPUT_PULLUP);
```

O sketch aplica debounce de 50 ms e alterna `modoFesta` a cada pressionamento.

Os LEDs de status da ES32Lab são:

```cpp
#define LED_VERDE 17
#define LED_AMARELO 16
#define LED_VERMELHO 13
```

`atualizarLeds()` aplica esta prioridade:

1. Festa: verde.
2. Crítico: vermelho.
3. `feliz`, `oculos` ou `festa`: verde.
4. `seca`, `frio` ou `doente`: amarelo.
5. `dormindo` ou `aguardando`: todos apagados.

Não há código de buzzer no [PetPlanta.ino](PetPlanta.ino). O crítico altera o
LED vermelho e o LCD no ESP32; o áudio de alerta, quando habilitado, é tratado
no notebook por [audio_player.py](webapp/audio_player.py).

## 6. Estados da planta

O humor ambiental é calculado por [mood.py](webapp/mood.py), nesta ordem:

1. `dormindo`: luz menor ou igual ao limite de escuro.
2. `frio`: temperatura menor ou igual ao limite de frio.
3. `doente`: temperatura maior ou igual ao limite de calor.
4. `seca`: solo abaixo do limite de solo seco.
5. `oculos`: luz maior ou igual ao limite de sol forte.
6. `feliz`: nenhuma condição especial.

O estado final do Python acrescenta duas prioridades:

- `festa` sobrepõe o humor ambiental enquanto o botão está ativo;
- `critico` sobrepõe o humor ambiental quando uma condição crítica persiste.

Na interface, crítico aparece visualmente como `doente`, mas o campo `critico`
continua separado no JSON.

O crítico é ativado por solo seco persistente, ausência de luz persistente ou
temperatura fora dos limites críticos. Ele só é liberado quando o humor
ambiental volta para `feliz` ou `oculos`.

## 7. Python e interface web

[app.py](webapp/app.py) cria o Flask, renderiza a página e oferece:

| Rota | Função |
|---|---|
| `GET /` | entrega a interface |
| `GET /api/state` | leituras, estado, conexão e temporizadores |
| `GET/POST /api/mode` | troca entre `live` e `simulation` |
| `GET/POST /api/audio` | habilita ou desabilita o áudio |
| `POST /api/heartbeat` | informa que o navegador desktop está aberto |
| `GET/POST /api/config` | consulta ou salva limites |
| `GET/POST /api/simulation` | consulta ou salva opções da simulação |

Em `live`, [wifi_reader.py](webapp/wifi_reader.py) consulta `/dados` a cada
segundo e envia comandos pendentes para `/comando`. Em `simulation`, o Python
percorre os sete estados a cada 5 segundos, em ordem aleatória sem repetir um
estado antes de completar o ciclo:

```python
_SIMULATION_STATES = [
    "feliz", "seca", "doente", "frio",
    "dormindo", "oculos", "festa",
]
```

O áudio do notebook usa os arquivos de [static/audio](webapp/static/audio/).
No celular, o navegador usa os elementos de áudio em
[app.js](webapp/static/js/app.js). A interface também pode solicitar vibração
quando o aparelho oferece essa API.

## 8. Configurações

Os limites padrão ficam em [config.py](webapp/config.py):

```python
LUZ_ESCURO_MAX = 400
LUZ_ENSOLARADO_MIN = 800
SOLO_SECO_MAX = 250
TEMP_FRIO_MAX = 15.0
TEMP_DOENTE_MIN = 40.0
```

Também existem os tempos e temperaturas do estado crítico e o limite para
detectar uma rega. A tela de configurações valida e aplica esses valores na
hora, salvando-os em `webapp/config_overrides.json`. Na próxima execução, o
arquivo é carregado automaticamente. Para voltar aos valores padrão, remova o
arquivo de overrides.

## 9. Estrutura

```text
PetPlanta.ino                 sketch principal do ESP32
README.md                     esta documentação
webapp/
  app.py                      servidor Flask
  audio_player.py             áudio do notebook
  config.py                   limites e configurações
  config_overrides.json       ajustes salvos
  mood.py                     regras de humor
  serial_reader.py            estado compartilhado e crítico
  wifi_reader.py              HTTP com o ESP32 e simulação
  requirements.txt            dependências Python
  templates/index.html        estrutura da página
  static/css/style.css        estilos
  static/js/app.js            comportamento da interface
  static/audio/               efeitos e música
  static/pet-planta/          sprites, cenários e transições
  _archive/                   fontes históricas, sem uso em execução
```

As fontes antigas estão descritas em
[`webapp/_archive/animation-sources/README.md`](webapp/_archive/animation-sources/README.md).
O navegador usa somente `static/pet-planta`; o conteúdo arquivado não participa
da execução do sistema.
