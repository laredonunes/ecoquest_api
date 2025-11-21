import os
import json
import time
from datetime import datetime
import requests

# ==================== CONFIGURAÇÃO DA HISTÓRIA ====================
INVESTIGATION_PHASES = {
    "descoberta": {
        "phase_number": 1,
        "title": "O Chamado das Cinzas",
        "key_clues": ["Fogo irregular", "Floresta úmida queimando"],
        "atmosphere": "Mistério, tensão"
    },
    "investigacao_inicial": {
        "phase_number": 2,
        "title": "Rastros na Mata",
        "key_clues": ["Cortes nas árvores", "Marcas de motosserra"],
        "atmosphere": "Descoberta perturbadora"
    },
    "evidencias": {
        "phase_number": 3,
        "title": "A Máquina da Destruição",
        "key_clues": ["Trator escondido", "Documentos falsos"],
        "atmosphere": "Perigo iminente"
    },
    "confronto": {
        "phase_number": 4,
        "title": "Faces da Impunidade",
        "key_clues": ["Milícia local", "Gado ilegal", "Corrupção"],
        "atmosphere": "Revelação chocante"
    },
    "resolucao": {
        "phase_number": 5,
        "title": "Justiça ou Silêncio",
        "key_clues": ["Dossiê completo", "Evidências"],
        "atmosphere": "Clímax"
    }
}

# System prompt COMPACTO (essencial para economizar tokens)
SYSTEM_PROMPT = """Você é narrador noir de crime ambiental no Brasil.

HISTÓRIA: Agente investiga incêndio suspeito em floresta úmida → descobre árvores cortadas → encontra trator → revela milícia (desmatamento+gado+documentos falsos) → leva ao MP.

ESTILO:
- Narrativa visual tipo HQ noir
- Jogador = voz interior do agente
- Tom dramático, tenso
- Pistas GRADUAIS
- Mencione Lei 9.605/98 quando relevante

FORMATO JSON:
{
  "scene": "Descrição visual (2 parágrafos)",
  "options": ["Ação 1", "Ação 2", "Ação 3"],
  "clue": "Pista ou null",
  "danger": "baixo|médio|alto|crítico",
  "phase": "fase atual"
}

Responda APENAS JSON válido."""


class ContextManager:
    """Gerencia contexto para economizar tokens"""

    def __init__(self, max_history=3):
        """
        Args:
            max_history: Máximo de mensagens recentes a manter
        """
        self.max_history = max_history

    def compress_history(self, history: list, current_phase: str) -> list:
        """
        Comprime histórico mantendo apenas essencial

        Args:
            history: Lista completa de mensagens
            current_phase: Fase atual do jogo

        Returns:
            Lista comprimida de mensagens
        """
        if len(history) <= self.max_history * 2:
            return history

        # Mantém apenas últimas N interações
        recent = history[-(self.max_history * 2):]

        # Cria resumo do que aconteceu antes
        summary = self._create_summary(history[:-self.max_history * 2])

        # Retorna: [resumo] + [histórico recente]
        return [
            {"role": "user", "content": f"RESUMO ANTERIOR: {summary}"}
        ] + recent

    def _create_summary(self, old_history: list) -> str:
        """Cria resumo compacto do histórico antigo"""
        # Extrai apenas decisões do jogador
        decisions = []
        for msg in old_history:
            if msg["role"] == "user" and "Decisão:" in msg.get("content", ""):
                # Extrai apenas a decisão
                content = msg["content"]
                if "Decisão:" in content:
                    decision = content.split("Decisão:")[1].split("\n")[0].strip(' "')
                    decisions.append(decision)

        if decisions:
            return f"Ações anteriores: {' → '.join(decisions[-3:])}"  # Últimas 3 ações
        return "Investigação em andamento"

    def prioritize_content(self, phase_info: dict, evidence: list) -> str:
        """Prioriza informações mais importantes"""
        parts = []

        # Fase atual (sempre incluir)
        parts.append(f"Fase {phase_info['phase_number']}/5: {phase_info['title']}")

        # Pistas da fase (essencial)
        parts.append(f"Pistas: {', '.join(phase_info['key_clues'])}")

        # Evidências coletadas (últimas 3)
        if evidence:
            recent_evidence = [e for e in evidence[-3:] if e]
            if recent_evidence:
                parts.append(f"Evidências: {', '.join(recent_evidence)}")

        return " | ".join(parts)


class GroqGameMaster:
    """Game Master usando Groq API"""

    def __init__(self, groq_api_key: str, model: str = "llama-3.3-70b-versatile"):
        """
        Inicializa o Game Master com Groq

        Args:
            groq_api_key: Chave da API Groq
            model: Modelo a usar
        """
        self.api_key = groq_api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.context_manager = ContextManager(max_history=3)
        print(f'🤖 Usando Groq: {self.model}')

    def _call_groq(self, messages: list, max_tokens: int = 1500) -> str:
        """
        Chama API da Groq

        Args:
            messages: Lista de mensagens
            max_tokens: Máximo de tokens na resposta

        Returns:
            Texto da resposta
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.8,
            "top_p": 0.95
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na API Groq: {str(e)}")

    def _clean_json_response(self, response_text: str) -> dict:
        """Limpa e parseia resposta JSON"""
        response_text = response_text.strip()

        # Remove markdown
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback
            return {
                "scene": "A floresta aguarda sua decisão. O tempo passa.",
                "options": ["Avançar cautelosamente", "Analisar o ambiente", "Chamar reforços"],
                "clue": None,
                "danger": "médio",
                "phase": "descoberta"
            }

    def start_game(self) -> dict:
        """Inicia uma nova investigação"""

        opening_prompt = """ABERTURA - "OPERAÇÃO CINZAS DA FLORESTA"

Cenário: Agente ambiental, 05:47h, estrada de terra. Incêndio em floresta úmida (estação chuvosa). IMPOSSÍVEL naturalmente.

O agente sente: algo está ERRADO. 15 anos de experiência não mentem.

[VOZ INTERIOR - VOCÊ]
Primeira decisão. O que o agente faz?

Crie cena de abertura dramática estilo HQ noir. 3 opções de ação.
Responda APENAS JSON."""

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": opening_prompt}
            ]

            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)

            # Padroniza chaves (scene -> panel_description, etc)
            standardized = {
                "panel_description": game_response.get("scene", game_response.get("panel_description", "")),
                "inner_voice_options": game_response.get("options", game_response.get("inner_voice_options", [])),
                "evidence_discovered": game_response.get("clue", game_response.get("evidence_discovered")),
                "danger_level": game_response.get("danger", game_response.get("danger_level", "médio")),
                "phase": game_response.get("phase", "descoberta")
            }

            initial_state = {
                "phase": "descoberta",
                "evidence_collected": [standardized["evidence_discovered"]] if standardized[
                    "evidence_discovered"] else [],
                "danger_meter": 25,
                "conversation_history": [
                    {"role": "user", "content": opening_prompt},
                    {"role": "assistant", "content": response_text}
                ]
            }

            return {
                "status": "success",
                "operation": "OPERAÇÃO CINZAS DA FLORESTA",
                "chapter": "CAPÍTULO 1: O CHAMADO DAS CINZAS",
                "timestamp": datetime.now().isoformat(),
                "narrative": standardized,
                "game_state": initial_state
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def continue_game(self, player_decision: str, game_state: dict) -> dict:
        """Continua a investigação"""

        phase_info = INVESTIGATION_PHASES.get(
            game_state["phase"],
            INVESTIGATION_PHASES["descoberta"]
        )

        # OTIMIZAÇÃO: Cria contexto compacto
        context = self.context_manager.prioritize_content(
            phase_info,
            game_state.get("evidence_collected", [])
        )

        # OTIMIZAÇÃO: Comprime histórico
        compressed_history = self.context_manager.compress_history(
            game_state.get("conversation_history", []),
            game_state["phase"]
        )

        # Prompt compacto
        continue_prompt = f"""CONTINUAR

{context}
Atmosfera: {phase_info['atmosphere']}

Decisão do jogador: "{player_decision}"

Narre consequências. Revele NOVA pista se apropriado. 3 opções.
JSON apenas."""

        try:
            messages = [
                           {"role": "system", "content": SYSTEM_PROMPT}
                       ] + compressed_history + [
                           {"role": "user", "content": continue_prompt}
                       ]

            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)

            # Padroniza chaves
            standardized = {
                "panel_description": game_response.get("scene", game_response.get("panel_description", "")),
                "inner_voice_options": game_response.get("options", game_response.get("inner_voice_options", [])),
                "evidence_discovered": game_response.get("clue", game_response.get("evidence_discovered")),
                "danger_level": game_response.get("danger", game_response.get("danger_level", "médio")),
                "phase": game_response.get("phase", game_state["phase"])
            }

            # Atualiza estado
            if standardized["evidence_discovered"]:
                game_state["evidence_collected"].append(standardized["evidence_discovered"])

            danger_map = {"baixo": 20, "médio": 40, "alto": 70, "crítico": 95}
            game_state["danger_meter"] = danger_map.get(standardized["danger_level"], 40)

            game_state["phase"] = standardized["phase"]

            # Adiciona ao histórico (será comprimido na próxima chamada)
            game_state["conversation_history"].append({"role": "user", "content": continue_prompt})
            game_state["conversation_history"].append({"role": "assistant", "content": response_text})

            chapter_map = {
                "descoberta": "CAPÍTULO 1: O CHAMADO DAS CINZAS",
                "investigacao_inicial": "CAPÍTULO 2: RASTROS NA MATA",
                "evidencias": "CAPÍTULO 3: A MÁQUINA DA DESTRUIÇÃO",
                "confronto": "CAPÍTULO 4: FACES DA IMPUNIDADE",
                "resolucao": "CAPÍTULO 5: JUSTIÇA OU SILÊNCIO"
            }

            return {
                "status": "success",
                "operation": "OPERAÇÃO CINZAS DA FLORESTA",
                "chapter": chapter_map.get(game_state["phase"], "INVESTIGAÇÃO"),
                "timestamp": datetime.now().isoformat(),
                "player_action": player_decision,
                "narrative": standardized,
                "game_state": game_state,
                "progress": f"{len(game_state['evidence_collected'])} evidências",
                "context_info": f"Histórico: {len(game_state['conversation_history'])} msgs (comprimido)"
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


# ==================== FUNÇÃO STANDALONE ====================
def operacao_cinzas_handler(data: dict, groq_api_key: str) -> dict:
    """
    Handler standalone para usar em rotas

    Args:
        data: {"action": "start|continue", "player_decision": "...", "game_state": {...}}
        groq_api_key: Chave da API Groq

    Returns:
        dict: Resposta do jogo
    """
    game_master = GroqGameMaster(groq_api_key)

    action = data.get('action', 'start')

    if action == 'start':
        return game_master.start_game()
    elif action == 'continue':
        player_decision = data.get('player_decision', '')
        game_state = data.get('game_state', {})
        return game_master.continue_game(player_decision, game_state)
    else:
        return {
            "status": "error",
            "error": f"Ação '{action}' inválida. Use 'start' ou 'continue'."
        }


# ==================== TESTE LOCAL ====================
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Carrega o .env da raiz do projeto (dois níveis acima)
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    print('=' * 80)
    print('🔥 OPERAÇÃO CINZAS DA FLORESTA - TESTE LOCAL')
    print('=' * 80)
    print()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print('❌ GROQ_API_KEY não configurada.')
        print('   Certifique-se de que o arquivo .env está na raiz do projeto.')
        exit(1)

    print(f'✅ API Key encontrada no .env da raiz.')
    print()

    try:
        # O resto do código de teste permanece o mesmo...
        game = GroqGameMaster(api_key)
        print('🎬 Iniciando investigação...')
        resultado = game.start_game()

        if resultado.get('status') == 'error':
            print(f'❌ ERRO: {resultado.get("error")}')
            exit(1)

        print('=' * 80)
        print(f'📖 {resultado["chapter"]}')
        print('=' * 80)
        narrative = resultado['narrative']
        print('🎨 CENA:')
        print(narrative['panel_description'])
        print('\n💭 SUAS OPÇÕES:')
        for i, opt in enumerate(narrative['inner_voice_options'], 1):
            print(f'   {i}. {opt}')
        
        print('\n' + '=' * 80)
        print('✅ TESTE CONCLUÍDO!')
        print('=' * 80)

    except Exception as e:
        print(f'❌ ERRO GERAL NO TESTE: {e}')
        import traceback
        traceback.print_exc()
