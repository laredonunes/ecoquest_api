// js/config.js

/**
 * Configuração central para o front-end.
 *
 * Com a arquitetura de Reverse Proxy, o front-end e o back-end são servidos
 * pela mesma origem (o Nginx). Portanto, a URL base da API é o próprio
 * endereço do site.
 *
 * As chamadas para a API devem ser feitas para caminhos relativos, 
 * começando com '/api'. Por exemplo: '/api/floresta'.
 */
const API_BASE_URL = ""; // Vazio, pois a origem é a mesma.

// Torna a variável acessível globalmente no objeto window
window.config = {
  API_BASE_URL: API_BASE_URL,
};
