#!/usr/bin/env python3.6 
import json
import requests
import sys
import os

def collect_and_save_data(url, dataAsterisk, params=None, headers=None):
    """
    Faz uma requisição HTTP para coletar dados e salva em um arquivo JSON no diretório /tmp.

    :param url: URL da API para a requisição
    :param params: Parâmetros opcionais para a requisição (dicionário)
    :param headers: Cabeçalhos opcionais para a requisição (dicionário)
    :return: Caminho do arquivo JSON gerado
    """
    try:
        # Fazendo a requisição HTTP GET
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Verifica se houve erros na requisição

        # Convertendo os dados da resposta para JSON
        data = response.json()

        # Definindo o caminho do arquivo de saída
        output_file = f"/tmp/data_{dataAsterisk['trunk']}.json"

        # Salvando os dados no arquivo JSON
        with open(output_file, "w") as json_file:
            json.dump(data, json_file, indent=4)

        print(f"Dados salvos com sucesso em: {output_file}")
        return output_file

    except requests.exceptions.RequestException as e:
        print(f"Erro ao fazer a requisição: {e}")
    except ValueError as e:
        print(f"Erro ao processar a resposta como JSON: {e}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
 
# Exemplo de uso
callId = sys.argv[1]
callerNumber = sys.argv[2]
trunkName = sys.argv[3]
dataAsterisk = {'id': callId, 'numero': callerNumber, 'trunk': trunkName}
api_url = "https://jsonplaceholder.typicode.com/posts"  # URL de exemplo
collect_and_save_data(api_url, dataAsterisk)
