import os
import json
from datetime import datetime
import requests

# ==================== CONFIGURAÇÃO - MAR ====================
INVESTIGATION_PHASES = {
    "denuncia": {
        "phase_number": 1,
        "title": "O Grito do Oceano",
        "key_clues": ["Barco industrial em área artesanal", "Redes de arrasto", "Comunidade local tensa"],
        "atmosphere": "Conflito social, urgência"
    },
    "confronto_inicial": {
        "phase_number": 2,
        "title": "Capitão do Aço",
        "key_clues": ["Licença de pesca questionável", "Argumento de 'eficiência'", "Desprezo pela pesca local"],
        "atmosphere": "Tensão, arrogância"
    },
    "inspecao": {
        "phase_number": 3,
        "title": "Porões da Ganância",
        "key_clues": ["Espécies ameaçadas capturadas", "Redes com malha ilegal", "GPS adulterado"],
        "atmosphere": "Descoberta chocante, evidência"
    },
    "comunidade": {
        "phase_number": 4,
        "title": "Vozes da Tradição",
        "key_clues": ["Relatos de intimidação", "Queda drástica na pesca", "Dependência do ecossistema"],
        "atmosphere": "Empatia, drama humano"
    },
    "decisao": {
        "phase_number": 5,
        "title": "A Balança da Justiça",
        "key_clues": ["Apreensão do barco", "Multa milionária", "Proteção da área"],
        "atmosphere": "Clímax, decisão de alto impacto"
    }
}

SYSTEM_PROMPT = """Você é narrador de crime ambiental sobre PESCA ILEGAL.

CONTEXTO: Agente fiscaliza denúncia de pesca industrial em área reservada para pescadores artesanais. Um barco de arrasto de grande porte está operando na área, ameaçando a subsistência da comunidade local e o ecossistema.

ENREDO: Recebe denúncia → Confronta o capitão do barco industrial → Inspeciona o barco e encontra irregularidades (espécies ameaçadas, redes ilegais) → Conversa com a comunidade local → Decide sobre a apreensão do barco e multa.

TEMAS EDUCATIVOS:
- Lei 9.605/98 (Crimes Ambientais) e Lei 11.959/09 (Política Nacional de Pesca).
- Impacto da pesca de arrasto no leito marinho.
- Diferença entre pesca industrial e artesanal/subsistência.
- Importância das áreas de exclusão para a recuperação de espécies.

DILEMAS:
- Pressão econômica da indústria pesqueira.
- Risco de conflito direto com a tripulação do barco.
- A necessidade de provas concretas para justificar uma apreensão cara.

FORMATO JSON:
{
  "scene": "Descrição visual e tensa (2 parágrafos)",
  "options": ["Opção 1", "Opção 2", "Opção 3"],
  "clue": "Pista ou null",
  "danger": "baixo|médio|alto|crítico",
  "phase": "fase atual"
}

Tom: Documental, tenso, focado no impacto humano e ambiental. JSON válido apenas."""


class ContextManager:
    """Gerencia contexto para economizar tokens"""
    def __init__(self, max_history=3):
        self.max_history = max_history

    def compress_history(self, history: list, current_phase: str) -> list:
        if len(history) <= self.max_history * 2: return history
        recent = history[-(self.max_history * 2):]
        summary = self._create_summary(history[:-self.max_history * 2])
        return [{"role": "user", "content": f"RESUMO: {summary}"}] + recent

    def _create_summary(self, old_history: list) -> str:
        decisions = [
            msg["content"].split("Decisão:")[1].split("\n")[0].strip(' "')
            for msg in old_history
            if msg["role"] == "user" and "Decisão:" in msg.get("content", "")
        ]
        return f"Ações: {' → '.join(decisions[-3:])}" if decisions else "Investigando"

    def prioritize_content(self, phase_info: dict, evidence: list) -> str:
        parts = [f"Fase {phase_info['phase_number']}/5: {phase_info['title']}", f"Pistas: {', '.join(phase_info['key_clues'])}"]
        if evidence and (recent := [e for e in evidence[-3:] if e]):
            parts.append(f"Evidências: {', '.join(recent)}")
        return " | ".join(parts)


class MarGameMaster:
    """Game Master - Cenário do Mar"""

    def __init__(self, groq_api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = groq_api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.context_manager = ContextManager(max_history=3)
        print(f'🐟 Mar - Usando: {self.model}')

    def _call_groq(self, messages: list, max_tokens: int = 1500) -> str:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.8, "top_p": 0.95}
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na API Groq: {str(e)}")

    def _clean_json_response(self, response_text: str) -> dict:
        response_text = response_text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return {"scene": "O oceano ruge. Uma decisão precisa ser tomada.", "options": ["Abordar o barco", "Observar à distância", "Contatar a base"], "clue": None, "danger": "médio", "phase": "denuncia"}

    def start_game(self) -> dict:
        opening_prompt = """ABERTURA - "REDES DA SOBREVIVÊNCIA"

Cenário: Lancha de fiscalização, mar agitado. No horizonte, um barco industrial gigante opera onde apenas pequenos barcos de pesca artesanal deveriam estar. O rádio chia com a voz desesperada do líder da comunidade local.

[DILEMA] A indústria pesqueira é poderosa. Uma abordagem errada pode custar seu emprego. Não fazer nada condena uma comunidade inteira à fome.

Crie a cena inicial. 3 opções de ação. JSON apenas."""
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": opening_prompt}]
            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)
            standardized = {
                "panel_description": game_response.get("scene", ""),
                "inner_voice_options": game_response.get("options", []),
                "evidence_discovered": game_response.get("clue"),
                "danger_level": game_response.get("danger", "médio"),
                "phase": game_response.get("phase", "denuncia")
            }
            initial_state = {
                "phase": "denuncia",
                "evidence_collected": [standardized["evidence_discovered"]] if standardized["evidence_discovered"] else [],
                "danger_meter": 40,
                "conversation_history": [{"role": "user", "content": opening_prompt}, {"role": "assistant", "content": response_text}]
            }
            return {"status": "success", "operation": "REDES DA SOBREVIVÊNCIA", "chapter": "CAPÍTULO 1: O GRITO DO OCEANO", "timestamp": datetime.now().isoformat(), "narrative": standardized, "game_state": initial_state}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def continue_game(self, player_decision: str, game_state: dict) -> dict:
        phase_info = INVESTIGATION_PHASES.get(game_state["phase"], INVESTIGATION_PHASES["denuncia"])
        context = self.context_manager.prioritize_content(phase_info, game_state.get("evidence_collected", []))
        compressed_history = self.context_manager.compress_history(game_state.get("conversation_history", []), game_state["phase"])
        continue_prompt = f"""CONTINUAR
{context}
Decisão: "{player_decision}"
Narre. Nova pista. 3 opções. JSON."""
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + compressed_history + [{"role": "user", "content": continue_prompt}]
            response_text = self._call_groq(messages)
            game_response = self._clean_json_response(response_text)
            standardized = {
                "panel_description": game_response.get("scene", ""),
                "inner_voice_options": game_response.get("options", []),
                "evidence_discovered": game_response.get("clue"),
                "danger_level": game_response.get("danger", "médio"),
                "phase": game_response.get("phase", game_state["phase"])
            }
            if standardized["evidence_discovered"]: game_state["evidence_collected"].append(standardized["evidence_discovered"])
            danger_map = {"baixo": 20, "médio": 40, "alto": 70, "crítico": 95}
            game_state["danger_meter"] = danger_map.get(standardized["danger_level"], 40)
            game_state["phase"] = standardized["phase"]
            game_state["conversation_history"].extend([{"role": "user", "content": continue_prompt}, {"role": "assistant", "content": response_text}])
            chapter_map = {"denuncia": "CAPÍTULO 1: O GRITO DO OCEANO", "confronto_inicial": "CAPÍTULO 2: CAPITÃO DO AÇO", "inspecao": "CAPÍTULO 3: PORÕES DA GANÂNCIA", "comunidade": "CAPÍTULO 4: VOZES DA TRADIÇÃO", "decisao": "CAPÍTULO 5: A BALANÇA DA JUSTIÇA"}
            return {"status": "success", "operation": "REDES DA SOBREVIVÊNCIA", "chapter": chapter_map.get(game_state["phase"], "INVESTIGAÇÃO"), "timestamp": datetime.now().isoformat(), "player_action": player_decision, "narrative": standardized, "game_state": game_state, "progress": f"{len(game_state['evidence_collected'])} evidências"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

def mar_handler(data: dict, groq_api_key: str) -> dict:
    """Handler para o cenário do mar"""
    game_master = MarGameMaster(groq_api_key)
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
    print('🐟 REDES DA SOBREVIVÊNCIA - TESTE LOCAL')
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
        game = MarGameMaster(api_key)
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
