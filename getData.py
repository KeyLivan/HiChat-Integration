#!/usr/bin/env python3.6
import requests
import json
import os
import sys
import re


def agi_verbose(message):
    sys.stdout.write(f'VERBOSE "{message}" 1\n')
    sys.stdout.flush()

# Função para baixar e salvar o áudio usando o cliente MinIO
def download_audio(bucket_minio, audio_path_minio):
    # Conectar ao MinIO
    client = Minio(
        "localhost:9000",  # Endereço do MinIO
        access_key="seu_access_key",  # Sua chave de acesso
        secret_key="seu_secret_key",  # Sua chave secreta
        secure=False  # Se estiver usando HTTP, defina como False
    )
    
    # Cria o diretório para o bucket, caso não exista
    audio_dir = os.path.join("/tmp", bucket_minio)
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    audio_path = os.path.join(audio_dir, audio_path_minio)

    try:
        # Baixar o áudio do MinIO
        client.fget_object(bucket_minio, audio_path_minio, audio_path)
        agi_verbose(f"Áudio salvo em: {audio_path}")
    except ResponseError as e:
        agi_verbose(f"Erro ao baixar áudio {audio_path_minio}: {e}")


# Configurações
CHANNEL = sys.argv[1]

# Remove o prefixo (como PJSIP/) e o sufixo (-00000017)
match = re.match(r'^[^/]+/([^-]+(?:-[^-]+)*?)-[\w]+$', CHANNEL)

if match:
    ramal = match.group(1)
else:
    ramal = CHANNEL  # fallback caso não combine
bucket = "user-1-chatvoice-17-bucket"  # Altere conforme necessário
endpoint_url = f"http://3.82.106.88:8000/public/chatvoiceqa/{ramal}"

try:
    # Requisição ao endpoint
    response = requests.get(endpoint_url)
    response.raise_for_status()

    # Carrega o conteúdo JSON
    data = response.json()
    chatvoice_id = data.get("chatvoice_id")

    if not chatvoice_id:
        agi_verbose("Resposta não contém 'chatvoice_id'. Abortando.")
    else:
        # Salvar o JSON no caminho /tmp
        filename = os.path.join("/tmp", f"data_chatvoice_{chatvoice_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        agi_verbose(f"Arquivo JSON salvo com sucesso: {filename}")

        # Salvar os áudios conforme os dados do JSON
        for qa in data.get("qas", []):
            bucket_minio = qa.get("bucket_minio")
            audio_path_minio = qa.get("audio_path_minio")
            if bucket_minio and audio_path_minio:
                download_audio(bucket_minio, audio_path_minio)

except requests.exceptions.RequestException as e:
    agi_verbose(f"Erro ao fazer requisição: {e}")
