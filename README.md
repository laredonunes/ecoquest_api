# EcoQuest - API de RPG Ambiental com Docker

EcoQuest é uma plataforma de jogos investigativos em formato de RPG de texto, onde você assume o papel de um agente ambiental para solucionar crimes na fauna e flora brasileira. A aplicação é totalmente containerizada usando Docker e Docker Compose.

A arquitetura utiliza um **Nginx como Reverse Proxy**, que serve tanto o site estático (front-end) quanto a API RESTful (back-end), garantindo uma implantação robusta e escalável.

---

## 🚀 Demo ao Vivo

**Quer testar agora sem instalar nada?**

Acesse a versão de demonstração hospedada em um servidor particular e comece a jogar imediatamente!

- **[Acessar a Demo do EcoQuest](https://imersao_dev_alura2025.igniscomputo.com/index.html)**

> **Nota:** Por ser um ambiente de teste compartilhado, a API pode apresentar instabilidade ou estar offline. Para a melhor experiência, recomenda-se rodar o projeto localmente via Docker.

---

## Arquitetura

O projeto é orquestrado pelo `docker-compose.yml` e dividido em dois serviços principais:

1.  **`proxy` (Nginx):**
    - É o único ponto de entrada da aplicação, exposto na porta `8080`.
    - Serve os arquivos estáticos do site (`index.html`, `floresta.html`, etc.).
    - Atua como **Reverse Proxy**: todas as requisições que começam com `/api/` são redirecionadas internamente para o serviço `backend`.

2.  **`backend` (Flask + Gunicorn):**
    - Roda a API Flask, que contém a lógica dos cenários de jogo.
    - **Não é exposto diretamente ao exterior**. Só o serviço `proxy` pode se comunicar com ele, o que aumenta a segurança.
    - Utiliza a API da Groq para gerar a narrativa dinâmica dos jogos.

## Como Executar Localmente

### 1. Pré-requisitos

- Docker e Docker Compose instalados.
- Uma chave de API da [Groq](https://console.groq.com/keys).

### 2. Configuração

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/laredonunes/ecoquest_api.git
    cd ecoquest_api
    ```

2.  **Crie seu arquivo de ambiente:**
    - Na raiz do projeto, copie o arquivo de exemplo `.env.example` para um novo arquivo chamado `.env`.
      ```bash
      cp .env.example .env
      ```
    - Abra o arquivo `.env` e **insira sua chave da API da Groq** na variável `GROQ_API_KEY`.

### 3. Executando a Aplicação

Com o Docker em execução, inicie todo o ambiente com um único comando:

```bash
docker-compose up --build
```

- `--build`: Garante que as imagens Docker serão reconstruídas se houver alguma alteração nos `Dockerfiles`.
- Para parar a aplicação, pressione `Ctrl+C` no terminal. Para remover os contêineres, use `docker-compose down`.

### 4. Acessando a Aplicação

Após a inicialização, tudo estará disponível em `http://localhost:8080`:

- **Site Principal:** `http://localhost:8080`
- **Cenários:** `http://localhost:8080/floresta.html`, `http://localhost:8080/mangue.html`, etc.

O front-end já está configurado para se comunicar com a API através do Nginx, então tudo deve funcionar de forma integrada.

## Fluxo da API

A comunicação entre o front-end e o back-end segue um fluxo simples:

1.  **Iniciar um Cenário:**
    - O cliente envia um `POST` para `/api/<nome-do-cenario>`.
    - Corpo da requisição: `{"action": "start"}`.
    - O servidor responde com a primeira cena e o estado inicial do jogo (`game_state`).

2.  **Continuar a História:**
    - O cliente envia um `POST` para o mesmo endpoint.
    - Corpo da requisição: `{"action": "continue", "player_decision": "...", "game_state": {...}}`.
    - O servidor usa o `game_state` para dar continuidade à narrativa e responde com a nova cena e o estado atualizado.
