#!/usr/bin/env python3.6 
import sys
import requests

if len(sys.argv) < 5:
    print("Uso: python enviar_audio.py CALL_ID NUMERO CHATVOICE_ID BUCKET")
    sys.exit(1)

call_id = sys.argv[1]
caller_number = sys.argv[2]
chatvoice_id = sys.argv[3]
bucket = sys.argv[4].strip()
form_type = sys.argv[5]
finish = sys.argv[6]

# Configurações fixas
url = f"http://localhost:8000/formulario/{chatvoice_id}"  # Ajuste conforme o seu endpoint real
audio_path = f"/tmp/response_{call_id}_{form_type}.wav"   # Exemplo de onde está o arquivo
finish = "false"    # ou "true"

# Dados do formulário
data = {
    'asterisk': call_id,
    'numero': caller_number,
    'type': form_type,
    'finish': finish
}

# Arquivo de áudio
try:
    with open(audio_path, 'rb') as audio_file:
        files = {
            'file': (audio_path, audio_file, 'audio/wav')
        }

        response = requests.post(url, data=data, files=files)
        print("Status:", response.status_code)
        print("Resposta:", response.json())
except FileNotFoundError:
    print(f"[ERRO] Arquivo de áudio não encontrado: {audio_path}")
except Exception as e:
    print(f"[ERRO] Falha ao enviar formulário por voz: {str(e)}")
