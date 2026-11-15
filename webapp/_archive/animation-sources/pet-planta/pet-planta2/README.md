# Pet Planta

Mascote em pixel art 64x64 com 7 humores (8 quadros cada) e 42 transições animadas.

## Pastas
- `sprites/` — **é isto que vai para o ESP32 (LittleFS)**
  - `<humor>/<humor>-sheet.png` + `.json` — loops: happy, party, sunny, cold, sleep, dry, sick
  - `party/moves/` — coreografia do modo festa (braçada, desmaio, giro, pisada, corcunda, braço erguido, apontando)
  - `transitions/<de>-to-<para>.png` — uma transição para cada par de humores
  - `sprites.json` — índice (humores, transições, humor padrão)
  - `bg/` — cenários dinâmicos (céu, nuvens, vista, sala, luz) + `backgrounds.json` (partículas)
  - `pet-planta.js` — player para o app web
- `previews/` — GIFs de visualização e `demo.html`
- `tools/` — geradores em Python (Pillow)
- `run/` — referências, manifest e relatórios de validação

## Uso no app web
```html
<!-- com cenário: canvas 256x144 (sem cenário: 64x64 e scene:false) -->
<canvas id="c" width="256" height="144" style="width:100%;image-rendering:pixelated"></canvas>
<script src="sprites/pet-planta.js"></script>
<script>
  (async () => {
    const pet = await new PetPlanta(document.getElementById('c'), { base: 'sprites/', scene: true }).load();
    pet.start();            // começa no humor padrão (happy)
    // pet.setMood('sunny'); // troca com a transição feliz -> sol
  })();
</script>
```

## Modo festa sincronizado com a música
A música **não** vem no zip. O ritmo dela já está gravado em `sprites.json` (`states.party.beat`: 79,178 BPM,
primeira batida forte em 2,1673 s) junto com a linha do tempo da coreografia (`states.party.timeline`).
Basta tocar a música num `<audio>` e ligar o sincronismo:
```js
pet.syncAudio(document.querySelector('audio'));
pet.setMood('party');
```
- 0:00–0:11 e 3:06–3:17: a planta faz os passos do clipe (braçada, desmaio, giro, pisada, corcunda, braço erguido, apontando)
- resto da música: balanço de festa (16 quadros = 1 compasso, cai na batida)
- se pular para outro ponto da música, a dança acompanha na hora
- sem música, a festa roda no mesmo andamento (sem a coreografia)

Na demo, use o botão "escolher a música da festa" para carregar o arquivo do seu computador.

## Ver a demo localmente
```
python3 -m http.server 8000
```
e abra http://localhost:8000/previews/demo.html

## Regerar
```
python3 tools/gen_plant.py && python3 tools/gen_party_moves.py && python3 tools/gen_transitions.py && python3 tools/gen_backgrounds.py && python3 tools/preview_transitions.py
```
