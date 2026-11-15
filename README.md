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

## 3. Fluxo completo dos dados

O caminho principal do projeto é este:

```text
Sensores físicos
      ↓ analogRead() no ESP32
ESP32 transforma as leituras e disponibiliza GET /dados
      ↓ HTTP pela rede Wi-Fi criada pelo ESP32
Python consulta /dados a cada segundo
      ↓ calcula o humor e o estado crítico
Python atualiza o estado da aplicação e a interface web
      ├── envia MOOD:estado e CRITICO:0/1 de volta ao ESP32
      │       ↓ POST /comando
      │   ESP32 atualiza o LCD e os LEDs
      └── entrega /api/state ao navegador
              ↓ HTTP
          JavaScript atualiza textos, barras, cenário e planta
```

Em palavras simples: o ESP32 mede, o Python interpreta e o navegador mostra.
O ESP32 também recebe de volta o humor ambiental calculado pelo Python para que
o LCD e os LEDs físicos acompanhem o estado do sistema.

### Como os componentes conversam

| Origem | Destino | Como conversa | O que transporta |
|---|---|---|---|
| Sensores | ESP32 | ADC/`analogRead()` | Valores elétricos convertidos em números |
| ESP32 | Python | HTTP `GET /dados` | Luz, solo, temperatura, crítico e festa em JSON |
| Python | ESP32 | HTTP `POST /comando` | `MOOD:estado` e `CRITICO:0/1` |
| Python | Navegador | HTTP `GET /api/state` | Estado consolidado e leituras para a tela |
| Navegador | Python | HTTP `POST` | Troca de modo, áudio, configurações e heartbeat |
| ESP32 | LCD | SPI pela biblioteca `ES32Lab` | Pixels e textos do display |
| ESP32 | LEDs | GPIO digital | Sinal físico de verde, amarelo ou vermelho |

Aqui, HTTP é o protocolo usado para as mensagens entre dispositivos e
programas. O ESP32 não abre uma conexão permanente com o Python: o Python faz
uma requisição HTTP, o ESP32 responde e o ciclo se repete aproximadamente uma
vez por segundo.

### O que acontece com uma leitura real

1. O ESP32 lê os pinos analógicos da luz, do solo e da temperatura.
2. Ele converte luz e solo para a faixa `0..1023` e responde ao `GET /dados`.
3. O Python recebe essa resposta em [wifi_reader.py](webapp/wifi_reader.py) e
   passa os valores para o estado compartilhado.
4. [mood.py](webapp/mood.py) compara os valores com os limites configurados e
   escolhe o humor ambiental.
5. [serial_reader.py](webapp/serial_reader.py) aplica as prioridades de festa e
   crítico e calcula o estado final mostrado na aplicação.
6. Se o humor ambiental mudou, o Python envia `MOOD:estado` ao ESP32. Se o
   crítico mudou, envia `CRITICO:1` ou `CRITICO:0`.
7. O ESP32 atualiza a variável `humor`, recalcula os LEDs e redesenha o LCD.
8. O navegador consulta `/api/state` e atualiza a planta, o cenário, os cards,
   os valores dos sensores e o texto do estado.

O modo festa é uma exceção: o botão BOOT é lido diretamente pelo ESP32. O ESP32
marca `festa: true` na resposta de `/dados`; o Python usa essa informação para
sobrepor o humor ambiental, iniciar a música e informar o estado ao navegador.

No modo simulação, o Python cria os valores e estados localmente, sem consultar
o ESP32. Por isso a interface web muda, mas o LCD e os LEDs físicos continuam
com o último estado real que receberam.

## 4. Rede e protocolos em mais detalhe

O ESP32 funciona como um ponto de acesso Wi-Fi (`WIFI_AP`). Isso significa que
ele cria a própria rede `osguri`; o notebook e o celular entram nessa rede e
conversam diretamente com o endereço `192.168.4.1`, sem internet.

O DNS local associa `pet.planta` ao ESP32. Ao abrir a raiz do ESP32, ele devolve
um redirecionamento HTTP para o notebook, onde o Flask está escutando na porta
80. Assim, o DNS serve como porta de entrada amigável, enquanto a aplicação
final roda no Python.

O Python consulta o ESP32 em `http://192.168.4.1/dados`. Para enviar comandos,
usa `POST /comando` com um formulário contendo o campo `comando`. O navegador
não conversa diretamente com os sensores: ele conversa com o Flask através de
`/api/state`.

## 5. Sensores

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

## 6. LCD TFT da ES32Lab

O LCD é controlado pela classe `ES_TFT` da biblioteca `ES32Lab`:

```cpp
ES_TFT tela;

tela.begin();
tela.setRotation(3);
tela.fillScreen(TFT_BLACK);
tela.drawString("Iniciando...", 5, 15, 2);
```

SPI é o protocolo elétrico usado para transferir rapidamente os pixels entre o
ESP32 e o display. O ESP32 atua como controlador e envia os dados em sequência
usando clock, dados e sinais de seleção do display. No projeto, a biblioteca
`ES32Lab` esconde esses detalhes: o sketch cria `ES_TFT tela`, chama
`tela.begin()` e depois usa funções como `fillScreen()` e `drawString()`.

O [PetPlanta.ino](PetPlanta.ino) não informa os números dos pinos SPI
manualmente. Portanto, não é correto inventar uma pinagem a partir deste
arquivo: a ligação elétrica deve seguir o modelo da placa ES32Lab e a
configuração da própria biblioteca.

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

## 7. Botão e LEDs

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

## 8. Estados da planta

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

## 9. Python e interface web

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

## 10. Configurações

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

## 11. Falhas, desconexões e recuperação

O projeto possui tratamentos para falhas de comunicação e para alguns valores
inválidos, mas não deve ser tratado como um sistema de segurança elétrica. A
tabela abaixo resume o comportamento real:

| Situação | O que o código faz | Resultado esperado |
|---|---|---|
| Wi-Fi/HTTP entre ESP32 e notebook cai | Usa timeout de 2 segundos, captura a exceção, marca a conexão como perdida, para o áudio e tenta novamente | A interface informa desconexão; quando a rede volta, as leituras são retomadas |
| ESP32 é desligado ou reinicia | O `GET /dados` falha e entra no mesmo tratamento; o ESP32 refaz o `setup()` ao ligar | O Python continua tentando; o LCD e a rede voltam após o boot |
| Leitura fica antiga | O estado considera a leitura obsoleta depois de 6 segundos sem atualização | `connected` passa a ser falso, mesmo que os últimos números ainda permaneçam armazenados |
| Temperatura inválida | O ESP32 envia `temperatura: null` quando o ADC chega a 0 ou 4095 | O LCD mostra `Temp: erro` e o Python não aplica regras de temperatura nessa leitura |
| Comando HTTP inválido | O ESP32 rejeita humor ou comando desconhecido com HTTP 400 | O comando não altera o LCD nem os LEDs |
| Falha ao enviar comando de volta | O Python captura a falha e mantém o comando pendente para tentar novamente | O estado local continua funcionando, mas LCD/LED pode ficar temporariamente atrasado |
| Arquivo de áudio ausente ou erro no player | O Python verifica o arquivo, registra o erro e mantém o restante ativo | A interface continua funcionando sem aquele áudio |

### Se o Wi-Fi cair

O leitor em [wifi_reader.py](webapp/wifi_reader.py) faz `GET /dados` com
timeout de 2 segundos. Qualquer erro de rede, timeout, resposta inválida ou
valor fora da faixa esperada cai no tratamento de exceção. Nesse momento, o
Python:

1. Marca o ESP32 como desconectado.
2. Remove a conexão lógica usada para enviar comandos.
3. Desativa o estado de festa no Python.
4. Interrompe o áudio do notebook.
5. Continua o loop e tenta consultar o ESP32 novamente.

Enquanto não chegam novas leituras, a última leitura fica guardada em memória,
mas `connected` é considerado falso quando passa `READING_STALE_AFTER = 6.0`
em [config.py](webapp/config.py). Assim, a tela não apresenta uma leitura velha
como se fosse atual.

### Se o ESP32 desligar ou reiniciar

Para o Python, desligar o ESP32 aparece como uma falha no `GET /dados`. O
tratamento é o mesmo da queda de Wi-Fi. Ao voltar, o ESP32 executa novamente o
`setup()`: inicializa o LCD, recria a rede Wi-Fi, inicia o DNS, registra as
rotas HTTP e volta a medir os sensores.

Quando a comunicação retorna, o Python sincroniza os comandos conhecidos e
retoma as leituras. O estado do ESP32 é perdido durante um reset; por isso essa
sincronização depois da reconexão é importante.

### Se um sensor parar de funcionar

O código trata explicitamente a temperatura quando o ADC retorna `0` ou `4095`.
Para luz e solo, o ESP32 converte qualquer leitura para `0..1023`; ele não
consegue saber, apenas pelo número, se o sensor está desconectado, travado ou
realmente medindo um extremo.

Assim, um LDR ou sensor de solo rompido pode produzir um valor aparentemente
legítimo e ser interpretado como `dormindo`, `seca` ou outro estado. Atualmente
não há filtragem de média, detecção de variação impossível, sensor redundante
ou alarme específico de sensor desconectado.

### Se houver pico ou queda de energia

Não existe no código proteção elétrica contra pico de tensão. Um pico pode
causar leitura incorreta, reinicialização ou dano físico ao ESP32, LCD e
sensores. Se o ESP32 apenas reiniciar sem sofrer dano, o `setup()` recompõe a
rede e o Python tenta reconectar automaticamente.

Na montagem física, use alimentação regulada compatível com 3,3 V, fonte
adequada, aterramento comum e proteção elétrica apropriada. Essa proteção
depende do hardware e não pode ser substituída por uma exceção no Python.

### Outras limitações importantes

- Se o notebook desligar ou o Flask parar, o ESP32 continua lendo sensores e
  atualizando LCD/LEDs com o último humor recebido, mas não recebe novos
  cálculos do Python e o navegador deixa de funcionar.
- Se o DNS falhar, ainda é possível testar a rede pelo IP do ESP32 e acessar o
  notebook pelo IP configurado, mas `pet.planta` não será resolvido.
- Falha física no LCD ou em um LED não é detectada por software; o código envia
  os comandos normalmente, mas não possui retorno confirmando que o componente
  acendeu ou exibiu a informação.
- O botão BOOT possui debounce de 50 ms, mas as leituras analógicas não têm
  filtro eletrônico ou média móvel neste sketch.

## 12. Estrutura

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
