import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from floresta.floresta import operacao_cinzas_handler
from floresta.mangue import mangue_handler
from floresta.mar import mar_handler
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
from functools import wraps

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


# ==================== RATE LIMITER ====================
class RateLimiter:
    """Sistema de rate limiting por IP"""

    def __init__(self):
        # Controle de requisições por minuto
        self.ip_requests = defaultdict(deque)  # {ip: deque de timestamps}
        self.max_requests_per_minute = 20
        self.time_window = timedelta(seconds=60)

        # Controle de cooldown (3 segundos entre requisições)
        self.last_request_time = {}  # {ip: timestamp}
        self.cooldown_seconds = 3

        # Cleanup periódico
        self.last_cleanup = datetime.now()

        logger.info(
            f'🛡️ Rate Limiter ativado: {self.max_requests_per_minute} req/min por IP + {self.cooldown_seconds}s cooldown')

    def get_client_ip(self):
        """Obtém o IP real do cliente (considera proxies/load balancers)"""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr

    def check_cooldown(self, ip: str) -> tuple[bool, float]:
        """
        Verifica cooldown de 3 segundos entre requisições

        Returns:
            (permitido: bool, tempo_restante: float)
        """
        now = datetime.now()

        if ip in self.last_request_time:
            time_since_last = (now - self.last_request_time[ip]).total_seconds()

            if time_since_last < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_last
                return False, remaining

        return True, 0

    def check_rate_limit(self, ip: str) -> tuple[bool, dict]:
        """
        Verifica limite de 20 requisições por minuto

        Returns:
            (permitido: bool, info: dict)
        """
        now = datetime.now()

        # Remove requisições antigas
        ip_queue = self.ip_requests[ip]
        while ip_queue and (now - ip_queue[0]) > self.time_window:
            ip_queue.popleft()

        current_count = len(ip_queue)

        if current_count >= self.max_requests_per_minute:
            oldest = ip_queue[0]
            retry_after = int((oldest + self.time_window - now).total_seconds()) + 1

            return False, {
                "allowed": False,
                "current_count": current_count,
                "max_allowed": self.max_requests_per_minute,
                "retry_after": retry_after
            }

        return True, {
            "allowed": True,
            "current_count": current_count + 1,
            "max_allowed": self.max_requests_per_minute,
            "remaining": self.max_requests_per_minute - (current_count + 1)
        }

    def register_request(self, ip: str):
        """Registra uma requisição bem-sucedida"""
        now = datetime.now()
        self.ip_requests[ip].append(now)
        self.last_request_time[ip] = now

        # Cleanup periódico (a cada 5 minutos)
        if (now - self.last_cleanup) > timedelta(minutes=5):
            self._cleanup()

    def _cleanup(self):
        """Remove IPs inativos há mais de 1 hora"""
        now = datetime.now()
        inactive_threshold = timedelta(hours=1)

        # Limpa ip_requests
        ips_to_remove = []
        for ip, queue in self.ip_requests.items():
            if not queue or (now - queue[-1]) > inactive_threshold:
                ips_to_remove.append(ip)

        for ip in ips_to_remove:
            del self.ip_requests[ip]

        # Limpa last_request_time
        for ip in list(self.last_request_time.keys()):
            if ip not in self.ip_requests:
                del self.last_request_time[ip]

        if ips_to_remove:
            logger.info(f"🧹 Cleanup: removidos {len(ips_to_remove)} IPs inativos")

        self.last_cleanup = now


# Instância global do rate limiter
rate_limiter = RateLimiter()


# ==================== DECORATOR ====================
def apply_rate_limit(f):
    """Decorator para aplicar rate limiting em rotas"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = rate_limiter.get_client_ip()

        # 1️⃣ VERIFICA COOLDOWN (3 segundos)
        cooldown_ok, time_remaining = rate_limiter.check_cooldown(ip)
        if not cooldown_ok:
            logger.warning(f"⏳ Cooldown: IP {ip} tentou requisição muito rápida ({time_remaining:.1f}s restantes)")
            return jsonify({
                "status": "error",
                "error": f"Aguarde {int(time_remaining) + 1} segundos antes de fazer outra requisição.",
                "code": "COOLDOWN_ACTIVE",
                "retry_after": int(time_remaining) + 1
            }), 429

        # 2️⃣ VERIFICA RATE LIMIT (20 req/min)
        rate_ok, rate_info = rate_limiter.check_rate_limit(ip)
        if not rate_ok:
            logger.warning(f"🚫 Rate limit: IP {ip} excedeu {rate_info['max_allowed']} req/min")
            return jsonify({
                "status": "error",
                "error": f"Limite de {rate_info['max_allowed']} requisições por minuto excedido.",
                "code": "RATE_LIMIT_EXCEEDED",
                "current_count": rate_info['current_count'],
                "max_allowed": rate_info['max_allowed'],
                "retry_after": rate_info['retry_after']
            }), 429

        # 3️⃣ REGISTRA REQUISIÇÃO
        rate_limiter.register_request(ip)

        # Log de sucesso
        logger.info(
            f"✅ IP {ip}: {rate_info['current_count']}/{rate_info['max_allowed']} req (restam {rate_info['remaining']})")

        # 4️⃣ EXECUTA A ROTA
        response = f(*args, **kwargs)

        # 5️⃣ ADICIONA HEADERS INFORMATIVOS
        if isinstance(response, tuple):
            response_obj, status_code = response
        else:
            response_obj = response
            status_code = 200

        if hasattr(response_obj, 'headers'):
            response_obj.headers['X-RateLimit-Limit'] = str(rate_info['max_allowed'])
            response_obj.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
            response_obj.headers['X-RateLimit-Cooldown'] = str(rate_limiter.cooldown_seconds)

        return response_obj if not isinstance(response, tuple) else (response_obj, status_code)

    return decorated_function


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
        "rate_limiting": {
            "max_requests_per_minute": rate_limiter.max_requests_per_minute,
            "cooldown_seconds": rate_limiter.cooldown_seconds,
            "descricao": "Cada IP pode fazer no máximo 20 requisições por minuto, com intervalo mínimo de 3 segundos entre requisições"
        },
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
        "cenarios_disponiveis": len(SCENARIOS),
        "rate_limiting_active": True,
        "limits": {
            "max_requests_per_minute": rate_limiter.max_requests_per_minute,
            "cooldown_seconds": rate_limiter.cooldown_seconds
        }
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


# ==================== ROTAS DOS CENÁRIOS (COM RATE LIMIT) ====================

def create_scenario_route(scenario_key: str):
    """Factory para criar rotas de cenários"""

    @apply_rate_limit  # 🛡️ APLICA RATE LIMITING
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
    print(
        f'🛡️ Rate Limiting: ✅ ({rate_limiter.max_requests_per_minute} req/min + {rate_limiter.cooldown_seconds}s cooldown)')
    print()
    print('📋 CENÁRIOS DISPONÍVEIS:')
    for key, info in SCENARIOS.items():
        print(f'   {info["icon"]} {info["titulo"]}')
        print(f'      → POST /api/{key}')
    print()
    print('💡 TESTES RÁPIDOS:')
    print(f'   curl http://localhost:{port}/health')
    print(
        f'   curl -X POST http://localhost:{port}/api/floresta -H "Content-Type: application/json" -d \'{{"action": "start"}}\'')
    print()
    print('⏹️ Para parar: Ctrl+C')
    print('=' * 80)
    print()

    app.run(host='0.0.0.0', port=port, debug=debug)
