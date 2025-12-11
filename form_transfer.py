#!/usr/bin/env python3.6 
import sys
import os
import requests

# Valida argumentos
if len(sys.argv) < 7:
    print("Uso: python form_transfer.py CALL_ID NUMERO CHATVOICE_ID BUCKET FORM_TYPE FINISH")
    sys.exit(1)

call_id = sys.argv[1]
caller_number = sys.argv[2]
chatvoice_id = sys.argv[3]
bucket = sys.argv[4].strip()
form_type = sys.argv[5]
finish = sys.argv[6]


def agi_verbose(message):
    sys.stdout.write(f'VERBOSE "{message}" 1\n')
    sys.stdout.flush()


def agi_set_variable(name, value):
    sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
    sys.stdout.flush()


# Configurações
url = f"http://147.182.191.150:8000/form-transfer/{chatvoice_id}"
audio_path = f"/tmp/response_{call_id}_{form_type}.wav"

agi_verbose(f"Iniciando envio do formulário - Tipo: {form_type}, Finalizar: {finish}")

# Dados do formulário
data = {
    'asterisk': call_id,
    'numero': caller_number,
    'type': form_type,
    'finish': finish
}

# Envia arquivo de áudio
try:
    if not os.path.exists(audio_path):
        agi_verbose(f"Arquivo de áudio não encontrado: {audio_path}")
        sys.exit(1)

    with open(audio_path, 'rb') as audio_file:
        files = {'file': (audio_path, audio_file, 'audio/wav')}
        response = requests.post(url, data=data, files=files)

    agi_verbose(f"Status HTTP: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        agi_verbose(f"Resposta: {result}")
        
        # Se for o último campo do formulário, pode setar variável de conclusão
        if finish == "true":
            agi_set_variable("FORM_COMPLETED", "true")
            agi_verbose("Formulário concluído!")
    else:
        agi_verbose(f"Erro na requisição: {response.status_code}")

except FileNotFoundError:
    agi_verbose(f"Arquivo de áudio não encontrado: {audio_path}")
    sys.exit(1)
except Exception as e:
    agi_verbose(f"Erro ao enviar formulário: {str(e)}")
    sys.exit(1)

sys.exit(0)
