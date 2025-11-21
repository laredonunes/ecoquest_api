import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from floresta.floresta import operacao_cinzas_handler
from floresta.mangue import mangue_handler
from floresta.mar import mar_handler
import logging
from datetime import datetime

# Carrega as variáveis de ambiente do arquivo .env na raiz do projeto
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY não configurada!")
    raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")

# ==================== CENÁRIOS DISPONÍVEIS ====================
SCENARIOS = {
    "floresta": {
        "titulo": "Operação Cinzas da Floresta",
        "descricao": "Incêndio criminoso e milícia desmatadora",
        "handler": operacao_cinzas_handler,
        "icon": "🔥"
    },
    "mangue": {
        "titulo": "Guardiões do Mangue",
        "descricao": "Supressão de mangue e documentos falsos",
        "handler": mangue_handler,
        "icon": "🌊"
    },
    "mar": {
        "titulo": "Redes da Sobrevivência",
        "descricao": "Pesca ilegal vs subsistência",
        "handler": mar_handler,
        "icon": "🐟"
    }
}


# ==================== ROTAS ====================

@app.route('/', methods=['GET'])
def home():
    """Página inicial com documentação"""
    return jsonify({
        "nome": "ECO QUEST - API de RPG Ambiental",
        "versao": "2.0.0",
        "descricao": "Plataforma de jogos investigativos sobre crimes ambientais",
        "cenarios": {
            key: {
                "titulo": info["titulo"],
                "descricao": info["descricao"],
                "icon": info["icon"],
                "endpoint": f"/api/{key}"
            }
            for key, info in SCENARIOS.items()
        },
        "endpoints_gerais": {
            "GET /": "Esta documentação",
            "GET /health": "Health check",
            "GET /api/cenarios": "Lista de cenários disponíveis"
        },
        "exemplo_uso": {
            "iniciar": {
                "url": "/api/floresta",
                "method": "POST",
                "body": {"action": "start"}
            },
            "continuar": {
                "url": "/api/floresta",
                "method": "POST",
                "body": {
                    "action": "continue",
                    "player_decision": "Sua escolha",
                    "game_state": {}
                }
            }
        }
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "groq_api_configured": bool(GROQ_API_KEY),
        "cenarios_disponiveis": len(SCENARIOS)
    }), 200


@app.route('/api/cenarios', methods=['GET'])
def list_scenarios():
    """Lista todos os cenários disponíveis"""
    return jsonify({
        "status": "success",
        "total": len(SCENARIOS),
        "cenarios": [
            {
                "id": key,
                "titulo": info["titulo"],
                "descricao": info["descricao"],
                "icon": info["icon"],
                "endpoint": f"/api/{key}"
            }
            for key, info in SCENARIOS.items()
        ]
    }), 200


# ==================== ROTAS DOS CENÁRIOS ====================

def create_scenario_route(scenario_key: str):
    """Factory para criar rotas de cenários"""

    def scenario_endpoint():
        try:
            if not request.is_json:
                return jsonify({
                    "status": "error",
                    "error": "Content-Type deve ser application/json",
                    "code": "INVALID_CONTENT_TYPE"
                }), 400

            data = request.get_json()
            action = data.get('action')

            if not action:
                return jsonify({
                    "status": "error",
                    "error": "Campo 'action' é obrigatório",
                    "valid_actions": ["start", "continue"],
                    "code": "MISSING_ACTION"
                }), 400

            if action not in ['start', 'continue']:
                return jsonify({
                    "status": "error",
                    "error": f"Action '{action}' inválida",
                    "valid_actions": ["start", "continue"],
                    "code": "INVALID_ACTION"
                }), 400

            # Validação para continue
            if action == 'continue':
                if 'player_decision' not in data or 'game_state' not in data:
                    return jsonify({
                        "status": "error",
                        "error": "Campos 'player_decision' e 'game_state' são obrigatórios",
                        "code": "MISSING_FIELDS"
                    }), 400

            logger.info(f"[{scenario_key.upper()}] Action: {action}")

            # Chama o handler específico do cenário
            handler = SCENARIOS[scenario_key]["handler"]
            resultado = handler(data, GROQ_API_KEY)

            status_code = 200 if resultado.get('status') == 'success' else 500
            return jsonify(resultado), status_code

        except Exception as e:
            logger.exception(f"Erro em {scenario_key}:")
            return jsonify({
                "status": "error",
                "error": str(e),
                "code": "INTERNAL_ERROR"
            }), 500

    return scenario_endpoint


# Registra rotas para cada cenário
for scenario_key in SCENARIOS.keys():
    route_name = f'scenario_{scenario_key}'
    app.add_url_rule(
        f'/api/{scenario_key}',
        route_name,
        create_scenario_route(scenario_key),
        methods=['POST']
    )


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "error": "Endpoint não encontrado",
        "code": "NOT_FOUND",
        "endpoints_disponiveis": [
            "GET /",
            "GET /health",
            "GET /api/cenarios",
            "POST /api/floresta",
            "POST /api/mangue",
            "POST /api/mar"
        ]
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "error": "Método HTTP não permitido",
        "code": "METHOD_NOT_ALLOWED"
    }), 405


@app.errorhandler(500)
def internal_error(error):
    logger.exception("Erro interno:")
    return jsonify({
        "status": "error",
        "error": "Erro interno do servidor",
        "code": "INTERNAL_ERROR"
    }), 500


# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_ENV') == 'development'

    print('=' * 80)
    print('🎮 ECO QUEST - SERVIDOR DE RPG AMBIENTAL')
    print('=' * 80)
    print()
    print(f'🚀 Servidor na porta {port}')
    print(f'🔑 API Groq: {"✅" if GROQ_API_KEY else "❌"}')
    print()
    print('📋 CENÁRIOS DISPONÍVEIS:')
    for key, info in SCENARIOS.items():
        print(f'   {info["icon"]} {info["titulo"]}')
        print(f'      → POST /api/{key}')
    print()
    print('💡 TESTES RÁPIDOS:')
    print(
        f'   curl -X POST http://localhost:{port}/api/floresta -H "Content-Type: application/json" -d \'{{"action": "start"}}\'')
    print(
        f'   curl -X POST http://localhost:{port}/api/mangue -H "Content-Type: application/json" -d \'{{"action": "start"}}\'')
    print(
        f'   curl -X POST http://localhost:{port}/api/mar -H "Content-Type: application/json" -d \'{{"action": "start"}}\'')
    print()
    print('⏹️  Para parar: Ctrl+C')
    print('=' * 80)
    print()

    app.run(host='0.0.0.0', port=port, debug=debug)
