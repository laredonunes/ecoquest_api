# EcoQuest - API de RPG Ambiental

EcoQuest é uma plataforma de jogos investigativos em formato de RPG de texto, onde você assume o papel de um agente ambiental para solucionar crimes na fauna e flora brasileira. A aplicação é construída como uma API RESTful usando Flask, com a narrativa gerada dinamicamente pela API da Groq (usando o modelo Llama 3).

## Estrutura do Projeto

- **/cloud_function**: Contém a aplicação Flask que serve a API.
  - `main.py`: Ponto de entrada da API. Define as rotas, cenários e gerencia as requisições.
  - `/floresta`: Contém a lógica específica de cada cenário de jogo.
    - `floresta.py`: Handler para o cenário "Operação Cinzas da Floresta".
    - `mangue.py`: Handler para o cenário "Guardiões do Mangue".
    - `mar.py`: Handler para o cenário "Redes da Sobrevivência".
  - `.env`: Arquivo para configurar suas variáveis de ambiente (não versionado).
  - `requirements.txt`: Dependências do projeto.

- **/site**: (Opcional) Contém um front-end estático que pode ser usado para interagir com a API.

## Como Configurar e Executar

### 1. Pré-requisitos

- Python 3.9+
- Uma chave de API da [Groq](https://console.groq.com/keys)

### 2. Instalação

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd ecoquest_cloufunction
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r cloud_function/requirements.txt
    ```

4.  **Configure sua chave de API:**
    - Renomeie o arquivo `cloud_function/.env.example` para `cloud_function/.env` (se houver um example) ou crie um novo.
    - Adicione sua chave da Groq ao arquivo `.env`:
      ```
      GROQ_API_KEY="gsk_SUA_CHAVE_SECRETA_AQUI"
      ```

### 3. Executando o Servidor Local

Com o ambiente ativado, inicie o servidor Flask:

```bash
python cloud_function/main.py
```

O servidor estará rodando em `http://localhost:8080`.

## Como Usar a API

A API é projetada para ser stateful do lado do cliente. O cliente (seu front-end ou ferramenta de API) é responsável por receber o `game_state` do servidor e enviá-lo de volta a cada turno.

### Endpoints Principais

- `GET /`: Retorna a documentação da API com os cenários disponíveis.
- `GET /health`: Verifica o status da aplicação.
- `GET /api/cenarios`: Lista os detalhes de todos os cenários jogáveis.

### Fluxo de Jogo (Exemplo com o cenário "floresta")

1.  **Iniciar o jogo:**
    Envie uma requisição POST para o endpoint do cenário com a ação "start".

    ```bash
    curl -X POST http://localhost:8080/api/floresta \
         -H "Content-Type: application/json" \
         -d '{"action": "start"}'
    ```

    A resposta conterá a primeira cena (`narrative`) e o estado inicial do jogo (`game_state`).

2.  **Continuar o jogo:**
    Para o próximo turno, envie a decisão do jogador e o `game_state` que você recebeu.

    ```bash
    curl -X POST http://localhost:8080/api/floresta \
         -H "Content-Type: application/json" \
         -d '{
               "action": "continue",
               "player_decision": "Analisar as cinzas de perto",
               "game_state": { ... o objeto game_state recebido anteriormente ... }
             }'
    ```

    A resposta trará a nova cena e o `game_state` atualizado. Repita este passo para progredir na história.

## Cenários Disponíveis

- **🔥 Operação Cinzas da Floresta**: Investigue um incêndio criminoso que esconde uma operação de desmatamento ilegal.
- **🌊 Guardiões do Mangue**: Lute contra a supressão de áreas de mangue com base em documentos falsificados.
- **🐟 Redes da Sobrevivência**: Medie o conflito entre pesca ilegal em larga escala e a subsistência de comunidades locais.

Flask
flask-cors
requests
python-dotenv
gunicorn
functions-framework