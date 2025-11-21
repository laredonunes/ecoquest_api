# EcoQuest

EcoQuest é um projeto dividido em duas partes principais: um site estático e uma Cloud Function.

## Estrutura do Projeto

- **/site**: Contém o front-end da aplicação, desenvolvido com HTML, CSS e JavaScript.
- **/cloud_function**: Contém o back-end, uma função serverless pronta para ser implantada em provedores de nuvem como Google Cloud, AWS ou Azure.

## Como Executar

### Site Estático

O site pode ser visualizado diretamente no seu navegador.

1.  Navegue até o diretório `site`.
2.  Abra o arquivo `index.html` em seu navegador de preferência.

Para publicar o site, você pode usar serviços de hospedagem de sites estáticos como GitHub Pages, Netlify ou Vercel, apontando para o diretório `site`.

### Cloud Function

A função Python pode ser testada localmente e implantada na nuvem.

1.  Navegue até o diretório `cloud_function`.
2.  Crie um ambiente virtual:
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows, use `venv\Scripts\activate`
    ```
3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
4.  Para testar ou implantar, siga a documentação do seu provedor de nuvem (Google Cloud Functions, AWS Lambda, etc.). O ponto de entrada da função está em `main.py`.
