from flask import Flask, render_template, request, jsonify
import requests
import json

from datetime import datetime

app = Flask(__name__)


# Base da URL
base_url = "https://api-publica.datajud.cnj.jus.br/"

# Dicionário com URLs para cada tribunal
urls_api_publica = {
    "trf1": base_url + "api_publica_trf1/_search",
    "trf2": base_url + "api_publica_trf2/_search",
    "trf3": base_url + "api_publica_trf3/_search",
    "trf4": base_url + "api_publica_trf4/_search",
    "trf5": base_url + "api_publica_trf5/_search",
    "trf6": base_url + "api_publica_trf6/_search",
}

# Chaves de API
api_key_datajud = "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="  # Substitua pela sua chave pública do Datajud

# URL do webhook (substitua pelo seu webhook real)
url_webhook = ""

def consultar_api_chatgpt(texto, objetivo):
    """
    Consulta a API do GPT-4 para reformular um texto com base no objetivo especificado.
    """
    url_chatgpt = "https://api.openai.com/v1/chat/completions"
    api_key_chatgpt = ""  # Substitua pela sua chave da API do GPT-4
    
    headers = {
        "Authorization": f"Bearer {api_key_chatgpt}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um assistente virtual especializado em informar ao cliente final do advogado sobre o status do processo judicial. Sua tarefa é:\n\n"
                    "1. **Informar a Última Movimentação:** Explique de forma simples e clara a última movimentação processual registrada, eliminando termos jurídicos complexos.\n\n"
                    "2. **Explicar o Próximo Passo:** Mostre qual será o próximo passo no processo, considerando o andamento natural e previsível do caso.\n\n"
                    "3. **Orientar sobre o Que Fazer Agora:** Indique ao cliente o que ele pode ou deve fazer enquanto aguarda o próximo passo. Seja empático e tranquilizador, reduzindo a ansiedade.\n\n"
                    "4. **Manter um Tom Tranquilizador:** O foco é acalmar o cliente e oferecer clareza, sem entrar em especulações ou criar expectativas irreais.\n\n"
                    "Formato de Resposta (para envio no WhatsApp):\n"
                    "Última Movimentação: [Explicação clara]\n"
                    "Próximo Passo: [O que deve acontecer]\n"
                    "Orientação ao Cliente: [Orientação ou tranquilização]\n"
                    "Obs: Quebre a mensagem em blocos curtos para facilitar o entendimento no WhatsApp."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Explique em termos simples a seguinte informação para que um leigo possa entender:\n\n"
                    f"{texto}\n\n"
                    f"Objetivo: {objetivo}"
                )
            }
        ]
    }

    try:
        response = requests.post(url_chatgpt, headers=headers, json=payload)
        response_json = response.json()  # Converte a resposta em JSON
        
        # Verifica se a resposta contém 'choices'
        if 'choices' in response_json and response_json['choices']:
            return response_json['choices'][0]['message']['content']
        else:
            print("Resposta inesperada da API do GPT-4:")
            print(json.dumps(response_json, indent=4))  # Log detalhado da resposta
            return None

    except Exception as e:
        print(f"Erro ao consultar a API do GPT-4: {e}")
        return None

def enviar_para_webhook(url_webhook, mensagem):
    """
    Envia uma mensagem para um webhook.
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": mensagem
    }
    
    try:
        response = requests.post(url_webhook, headers=headers, json=payload)
        if response.status_code == 200:
            print("Mensagem enviada com sucesso para o webhook!")
        else:
            print(f"Falha ao enviar a mensagem. Código HTTP: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro ao enviar a mensagem para o webhook: {e}")


@app.route('/')
def index():
    
    return render_template('index.html')

@app.route('/consultar', methods=['POST'])

def consultar():
    try:
        # Acessando os dados como JSON
        data = request.get_json()

        # Agora você pode acessar os dados do JSON
        tribunal = data.get('tribunal', '').strip().lower()
        numero_processo = data.get('numero_processo', '').strip()

        if not tribunal or not numero_processo:
            return jsonify({"error": "Dados inválidos ou incompletos."}), 400

        if tribunal not in urls_api_publica:
            return jsonify({"error": "Tribunal inválido!"}), 400

        url = urls_api_publica[tribunal]
        
        payload = json.dumps({
            "size": 10,
            "query": {
                "term": {"numeroProcesso.keyword": numero_processo}
            },
            "sort": [{"dataAjuizamento": {"order": "desc"}}]
        })
        
        headers = {
            'Authorization': api_key_datajud,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, data=payload)
        
        if response.status_code == 200:
            dados_dict = response.json()
            hits = dados_dict.get('hits', {}).get('hits', [])
            
            if hits:
                primeiro_resultado = hits[0]
                movimentos = primeiro_resultado.get('_source', {}).get('movimentos', [])
                
                if movimentos:
                    movimentacao_mais_recente = max(
                        movimentos, 
                        key=lambda mov: datetime.strptime(mov.get('dataHora', '1900-01-01T00:00:00')[:19], '%Y-%m-%dT%H:%M:%S')
                    )
                    descricao_movimentacao = json.dumps(movimentacao_mais_recente, indent=4)
                    
                    explicacao_simples = consultar_api_chatgpt(
                        descricao_movimentacao, 
                        "Explicar o que aconteceu na movimentação processual mais recente."
                    )
                    
                    if explicacao_simples:
                        # Aqui, formatamos a explicação com <p> para cada parágrafo
                        explicacao_formatada = ''.join(f'<p>{par}</p>' for par in explicacao_simples.split('\n'))
                        
                        # Envia a explicação para o webhook
                        #enviar_para_webhook(url_webhook, explicacao_formatada)
                        
                        return jsonify({"result": explicacao_formatada}), 200
                    else:
                        return jsonify({"error": "Não foi possível obter uma explicação simples."}), 500
                else:
                    return jsonify({"error": "Nenhuma movimentação encontrada para o processo."}), 404
            else:
                return jsonify({"error": "Nenhum dado encontrado para o filtro informado."}), 404
        else:
            return jsonify({"error": f"Erro na requisição: {response.status_code} - {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Erro inesperado: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)

