import os
import json
import time
from datetime import datetime
import requests

# ==================== CONFIGURAÇÃO - MANGUE ====================
INVESTIGATION_PHASES = {
    "chegada": {
        "phase_number": 1,
        "title": "A Costa Dourada",
        "key_clues": ["Pier sobre mangue", "Documentos de herança", "Área de preservação"],
        "atmosphere": "Tensão inicial, dilema ético"
    },
    "dialogo": {
        "phase_number": 2,
        "title": "O Proprietário",
        "key_clues": ["Família antiga", "Reforma vs construção", "Casa de palha original"],
        "atmosphere": "Negociação difícil, argumentos"
    },
    "documentacao": {
        "phase_number": 3,
        "title": "Análise dos Documentos",
        "key_clues": ["Escritura suspeita", "Data da reserva", "Datas inconsistentes"],
        "atmosphere": "Investigação técnica, dúvida"
    },
    "evidencias": {
        "phase_number": 4,
        "title": "A Verdade Oculta",
        "key_clues": ["Documentos falsificados", "Área suprimida recentemente", "Provas fotográficas"],
        "atmosphere": "Revelação, confronto"
    },
    "desfecho": {
        "phase_number": 5,
        "title": "Decisão Final",
        "key_clues": ["Multa aplicada", "Ordem de retirada", "Recuperação do mangue"],
        "atmosphere": "Justiça vs pressão social"
    }
}

SYSTEM_PROMPT = """Você é narrador de crime ambiental sobre SUPRESSÃO DE MANGUE.

CONTEXTO: Agente fiscaliza mansão com pier construído sobre mangue protegido. Proprietário alega herança familiar anterior à reserva. Documentos parecem legítimos mas há inconsistências.

ENREDO: Chegada ao local → Diálogo com proprietário → Análise de documentos → Descoberta de falsificação → Aplicação da multa (dilema: pressão social vs dever legal)

TEMAS EDUCATIVOS:
- Importância do mangue: berçário marinho, proteção costeira, carbono azul
- Lei 12.651/2012 (Código Florestal) - APP de mangue
- Dificuldade de fiscalização: pressão, documentos, certeza jurídica
- Diferença entre reforma e construção nova

DILEMAS:
- Proprietário idoso, família tradicional
- Documentos aparentemente legítimos
- Risco de sanção se multa for incorreta
- Pressão de vizinhos ricos

FORMATO JSON:
{
  "scene": "Descrição (2 parágrafos)",
  "options": ["Opção 1", "Opção 2", "Opção 3"],
  "clue": "Pista ou null",
  "danger": "baixo|médio|alto|crítico",
  "phase": "fase"
}

Tom: Realista, dilema moral, educativo. JSON válido apenas."""


class ContextManager:
    """Gerencia contexto para economizar tokens"""

    def __init__(self, max_history=3):
        self.max_history = max_history

    def compress_history(self, history: list, current_phase: str) -> list:
        if len(history) <= self.max_history * 2:
            return history
        recent = history[-(self.max_history * 2):]
        summary = self._create_summary(history[:-self.max_history * 2])
        return [{"role": "user", "content": f"RESUMO: {summary}"}] + recent

    def _create_summary(self, old_history: list) -> str:
        decisions = []
        for msg in old_history:
            if msg["role"] == "user" and "Decisão:" in msg.get("content", ""):
                content = msg["content"]
                if "Decisão:" in content:
                    decision = content.split("Decisão:")[1].split("\n")[0].strip(' "')
                    decisions.append(decision)
        return f"Ações: {' → '.join(decisions[-3:])}" if decisions else "Investigando"

    def prioritize_content(self, phase_info: dict, evidence: list) -> str:
        parts = [f"Fase {phase_info['phase_number']}/5: {phase_info['title']}"]
        parts.append(f"Pistas: {', '.join(phase_info['key_clues'])}")
        if evidence:
            recent = [e for e in evidence[-3:] if e]
            if recent:
                parts.append(f"Evidências: {', '.join(recent)}")
        return " | ".join(parts)


class MangueGameMaster:
    """Game Master - Cenário do Mangue"""

    def __init__(self, groq_api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = groq_api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.context_manager = ContextManager(max_history=3)
        print(f'🌊 Mangue - Usando: {self.model}')

    def _call_groq(self, messages: list, max_tokens: int = 1500) -> str:
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
        response_text = response_text.strip()
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
            return {
                "scene": "O mangue aguarda. Decisões difíceis pela frente.",
                "options": ["Investigar mais", "Confrontar proprietário", "Buscar provas"],
                "clue": None,
                "danger": "médio",
                "phase": "chegada"
            }

    def start_game(self) -> dict:
        opening_prompt = """ABERTURA - "GUARDIÕES DO MANGUE"

Cenário: Costa luxuosa. Mansões com piers sobre mangue. Você é o agente ambiental.

Proprietário idoso, família tradicional. Alega: "Meu avô construiu isso antes da reserva. Tenho documentos."

Mangue = berçário marinho + proteção costeira. Mas... e se ele estiver certo?

[DILEMA] Multa errada = sanção disciplinar. Não multar = crime continua.

Crie cena inicial. 3 opções. JSON apenas."""

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": opening_prompt}
            ]
            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)

            standardized = {
                "panel_description": game_response.get("scene", ""),
                "inner_voice_options": game_response.get("options", []),
                "evidence_discovered": game_response.get("clue"),
                "danger_level": game_response.get("danger", "médio"),
                "phase": game_response.get("phase", "chegada")
            }

            initial_state = {
                "phase": "chegada",
                "evidence_collected": [standardized["evidence_discovered"]] if standardized[
                    "evidence_discovered"] else [],
                "danger_meter": 30,
                "conversation_history": [
                    {"role": "user", "content": opening_prompt},
                    {"role": "assistant", "content": response_text}
                ]
            }

            return {
                "status": "success",
                "operation": "GUARDIÕES DO MANGUE",
                "chapter": "CAPÍTULO 1: A COSTA DOURADA",
                "timestamp": datetime.now().isoformat(),
                "narrative": standardized,
                "game_state": initial_state
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def continue_game(self, player_decision: str, game_state: dict) -> dict:
        phase_info = INVESTIGATION_PHASES.get(game_state["phase"], INVESTIGATION_PHASES["chegada"])
        context = self.context_manager.prioritize_content(phase_info, game_state.get("evidence_collected", []))
        compressed_history = self.context_manager.compress_history(game_state.get("conversation_history", []),
                                                                   game_state["phase"])

        continue_prompt = f"""CONTINUAR
{context}
Decisão: "{player_decision}"
Narre. Nova pista. 3 opções. JSON."""

        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + compressed_history + [
                {"role": "user", "content": continue_prompt}]
            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)

            standardized = {
                "panel_description": game_response.get("scene", ""),
                "inner_voice_options": game_response.get("options", []),
                "evidence_discovered": game_response.get("clue"),
                "danger_level": game_response.get("danger", "médio"),
                "phase": game_response.get("phase", game_state["phase"])
            }

            if standardized["evidence_discovered"]:
                game_state["evidence_collected"].append(standardized["evidence_discovered"])

            danger_map = {"baixo": 20, "médio": 40, "alto": 70, "crítico": 95}
            game_state["danger_meter"] = danger_map.get(standardized["danger_level"], 40)
            game_state["phase"] = standardized["phase"]

            game_state["conversation_history"].append({"role": "user", "content": continue_prompt})
            game_state["conversation_history"].append({"role": "assistant", "content": response_text})

            chapter_map = {
                "chegada": "CAPÍTULO 1: A COSTA DOURADA",
                "dialogo": "CAPÍTULO 2: O PROPRIETÁRIO",
                "documentacao": "CAPÍTULO 3: ANÁLISE DOS DOCUMENTOS",
                "evidencias": "CAPÍTULO 4: A VERDADE OCULTA",
                "desfecho": "CAPÍTULO 5: DECISÃO FINAL"
            }

            return {
                "status": "success",
                "operation": "GUARDIÕES DO MANGUE",
                "chapter": chapter_map.get(game_state["phase"], "INVESTIGAÇÃO"),
                "timestamp": datetime.now().isoformat(),
                "player_action": player_decision,
                "narrative": standardized,
                "game_state": game_state,
                "progress": f"{len(game_state['evidence_collected'])} evidências"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


def mangue_handler(data: dict, groq_api_key: str) -> dict:
    """Handler para o cenário do mangue"""
    game_master = MangueGameMaster(groq_api_key)
    action = data.get('action', 'start')

    if action == 'start':
        return game_master.start_game()
    elif action == 'continue':
        return game_master.continue_game(data.get('player_decision', ''), data.get('game_state', {}))
    else:
        return {"status": "error", "error": "Ação inválida"}

# ==================== TESTE LOCAL ====================
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Carrega o .env da raiz do projeto (dois níveis acima)
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    print('=' * 80)
    print('🌊 GUARDIÕES DO MANGUE - TESTE LOCAL')
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
        game = MangueGameMaster(api_key)
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
