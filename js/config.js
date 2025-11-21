// js/config.js

/**
 * Configuração central para o front-end.
 *
 * IMPORTANTE: Este arquivo é a forma de simular um ".env" para o lado do cliente.
 * Ao fazer o deploy da sua aplicação, você DEVE alterar a variável API_BASE_URL
 * para o endereço do seu servidor de produção.
 *
 * Exemplo em produção:
 * const API_BASE_URL = "https://sua-aplicacao-em-producao.com";
 */
const API_BASE_URL = "http://localhost:8080";

// Torna a variável acessível globalmente no objeto window
window.config = {
  API_BASE_URL: API_BASE_URL,
};
