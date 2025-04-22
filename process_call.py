#!/usr/bin/env python3.6 
import os
import sys
import requests
import subprocess
import time
import json

# Captura o ID da chamada passado pelo dialplan (UNIQUEID)
call_id = sys.argv[1]
caller_number = sys.argv[2]
data = {'asterisk': call_id, 'numero': caller_number}

# Definir o caminho do áudio gravado e o áudio de resposta com o ID da chamada
recorded_audio_wav = f"/tmp/call_{call_id}_in.wav"  # Gravação inicial em WAV
recorded_audio_ogg = f"/tmp/call_{call_id}_in.ogg"  # Converter para OGG (Opus)
received_audio = f"/tmp/call_{call_id}_IA.ogg"  # Áudio recebido da IA
converted_audio = f"/tmp/call_{call_id}_out.gsm"  # Áudio convertido para GSM
transfer_header_file = f"/tmp/transfer_header_{call_id}.txt"  # Caminho para salvar o header Transfer

# Caminho para o arquivo JSON
JSON_FILE_PATH = f"/tmp/variables_{call_id}.json"

def agi_verbose(message):
    sys.stdout.write(f"VERBOSE \"{message}\" 1\n")
    sys.stdout.flush()

def load_variables():
    """Carrega as variáveis do arquivo JSON."""
    try:
        if not os.path.exists(JSON_FILE_PATH):
            agi_verbose("Arquivo JSON não existe, carregando valores padrão.")
            return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}
        with open(JSON_FILE_PATH, "r") as file:
            agi_verbose(f"Arquivo JSON carregado com sucesso: {JSON_FILE_PATH}")
            return json.load(file)
    except Exception as e:
        agi_verbose(f"Erro ao carregar arquivo JSON: {str(e)}")
        return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}


def save_variables(variables):
    """Salva as variáveis no arquivo JSON."""
    try:
        with open(JSON_FILE_PATH, "w") as file:
            json.dump(variables, file)
        agi_verbose(f"Variáveis salvas com sucesso no arquivo: {JSON_FILE_PATH}")
    except Exception as e:
        agi_verbose(f"Erro ao salvar variáveis no arquivo JSON: {str(e)}")


def increment_empty_body_count(body=False):
    """Função principal para gerenciar EMPTY_BODY_COUNT."""
    agi_verbose("Iniciando incremento de EMPTY_BODY_COUNT")

    # Carrega as variáveis do arquivo JSON
    variables = load_variables()
    empty_body_count = variables.get("EMPTY_BODY_COUNT", 0)

    agi_verbose(f"EMPTY_BODY_COUNT inicial: {empty_body_count}")

    if not body:
        agi_verbose("Executando incremento do EMPTY_BODY_COUNT")
        if empty_body_count == 2:
            variables["CLOSING"] = True
        elif empty_body_count > 2:
            variables["CLOSING"] = False
            variables["HUNGRUP"] = True
        elif empty_body_count < 2:
            variables["CLOSING"] = False

        # Incrementa o contador
        empty_body_count += 1
        variables["EMPTY_BODY_COUNT"] = empty_body_count
    else:
        agi_verbose("Resetando EMPTY_BODY_COUNT")
        # Reseta os valores
        empty_body_count = 0
        variables["EMPTY_BODY_COUNT"] = empty_body_count
        variables["CLOSING"] = False
        variables["HUNGRUP"] = False

    # Salva as variáveis no arquivo JSON
    save_variables(variables)

    # Imprime as variáveis atualizadas
    sys.stdout.write(f"EMPTY_BODY_COUNT={variables['EMPTY_BODY_COUNT']}\n")
    sys.stdout.write(f"CLOSING={variables['CLOSING']}\n")
    sys.stdout.write(f"HUNGRUP={variables['HUNGRUP']}\n")
    sys.stdout.flush()


# Função para remover arquivos usando subprocess e o comando 'rm'
def remove_file_if_exists(file_path):
    try:
        result = subprocess.run(['rm', '-f', file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode == 0:
            agi_verbose(f"Arquivo {file_path} removido com sucesso.")
        else:
            agi_verbose(f"Erro ao remover arquivo {file_path}: {result.stderr}")
    except Exception as e:
        agi_verbose(f"Erro ao tentar remover {file_path}: {str(e)}")


# Remover arquivos anteriores de forma segura
agi_verbose("Removendo arquivos de áudio anteriores...")
remove_file_if_exists(received_audio)
remove_file_if_exists(converted_audio)
remove_file_if_exists(recorded_audio_ogg)

# URL do servidor de STT/IA
endpoint_url = "http://54.172.12.60:8000/chatvoices/5/voice"

# Verifica se o arquivo de áudio gravado existe e tem mais de 0 bytes
if os.path.exists(recorded_audio_wav): # and os.path.getsize(recorded_audio_wav) > 0:
    agi_verbose(f"O arquivo de áudio {recorded_audio_wav} existe e será convertido para OGG Opus.")

    try:
        # Converte o arquivo de áudio gravado em WAV para OGG (Opus)
        conversion_result = subprocess.run(
            ['ffmpeg', '-i', recorded_audio_wav, '-c:a', 'libopus', '-ar', '16000', recorded_audio_ogg],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )

        if conversion_result.returncode == 0:
            agi_verbose(f"Áudio convertido com sucesso para {recorded_audio_ogg}.")
        else:
            agi_verbose(f"Erro na conversão: {conversion_result.stderr}")
            sys.exit(1)

        # Inicia a medição de tempo
        start_time = time.time()

        # Abre o arquivo de áudio convertido (OGG Opus)
        with open(recorded_audio_ogg, 'rb') as audio_file:
            # Envia o áudio e o ID da chamada para o servidor
            files = {'file': audio_file}
            response = requests.post(endpoint_url, files=files, data=data)

        # Finaliza a medição de tempo
        end_time = time.time()

        # Calcula o tempo de execução
        elapsed_time = end_time - start_time
        agi_verbose(f"Tempo da requisição: {elapsed_time:.2f} segundos")

        # Verifica se a resposta do servidor foi bem-sucedida
        if response.status_code == 200:
            # Verifica se o body da resposta está vazio
            if not response.content:
                increment_empty_body_count()
                raise Exception("Body vazio")  # Interrompe a execução com uma mensagem de erro
            else:
                increment_empty_body_count(True)

            # Salva o áudio de resposta no caminho definido
            with open(received_audio, 'wb') as f:
                f.write(response.content)

            # Salva o valor do header Transfer, se existir
            transfer_value = response.headers.get('Transfer')
            transcricao = response.headers.get('transcricao')
            resposta_formatada = response.headers.get('resposta_formatada')
            if transfer_value is not None:
                with open(transfer_header_file, 'w') as f:
                    f.write(transfer_value)
                agi_verbose(f"Valor do header Transfer salvo em {transfer_header_file}: {transfer_value}")
            else:
                agi_verbose("Header Transfer não encontrado na resposta.")
            agi_verbose(f"Resultado do stt: {transcricao}")
            agi_verbose("***")
            agi_verbose(f"Resposta da IA em texto antes do tts: {resposta_formatada}")

            # Verifica se o áudio de resposta foi salvo corretamente
            if os.path.exists(received_audio) and os.path.getsize(received_audio) > 0:
                agi_verbose(f"Áudio de resposta salvo em {received_audio}.")

                # Converter o áudio recebido de OGG para GSM
                conversion_result = subprocess.run(
                    ['ffmpeg', '-i', received_audio, '-ar', '8000', '-ac', '1','-b:a', '13k', '-c:a', 'gsm', converted_audio],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
                )

                if conversion_result.returncode == 0:
                    agi_verbose(f"Áudio convertido com sucesso para {converted_audio}.")
                else:
                    agi_verbose(f"Erro na conversão para GSM: {conversion_result.stderr}")
            else:
                agi_verbose("Erro: O arquivo de resposta foi salvo, mas está vazio.")
        else:
            increment_empty_body_count()
            agi_verbose(f"Erro ao enviar o áudio. Código de retorno: {response}.")
    except Exception as e:
        agi_verbose(f"Erro ao processar o áudio: {str(e)}")
else:
    agi_verbose("Arquivo de áudio gravado não existe ou está vazio.")




