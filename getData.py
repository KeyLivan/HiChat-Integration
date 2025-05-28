#!/usr/bin/env python3.6
import requests
import json
import os
import sys
import re
from minio import Minio
from minio.error import ResponseError
from configMinio import MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ENDPOINT  # Importando as credenciais


def agi_verbose(message):
    sys.stdout.write(f'VERBOSE "{message}" 1\n')
    sys.stdout.flush()

def agi_set_variable(name, value):
    sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
    sys.stdout.flush()

# Função para baixar e salvar o áudio usando o cliente MinIO
def download_audio(client, bucket_minio, audio_path_minio):
    # Cria o diretório para o bucket, caso não exista
    audio_dir = os.path.join("/tmp", bucket_minio)
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    original_audio_path = os.path.join(audio_dir, audio_path_minio)
    converted_audio_path = os.path.splitext(original_audio_path)[0] + ".gsm"

    try:
        # Baixar o áudio do MinIO
        client.fget_object(bucket_minio, audio_path_minio, original_audio_path)
        agi_verbose(f"Áudio baixado: {original_audio_path}")

        # Converter para .gsm usando ffmpeg
        ffmpeg_cmd = f'ffmpeg -y -i "{original_audio_path}" -ar 8000 -ac 1 -ab 13k "{converted_audio_path}"'
        result = os.system(ffmpeg_cmd)

        if result == 0:
            agi_verbose(f"Áudio convertido para GSM: {converted_audio_path}")
            os.remove(original_audio_path)  # Opcional: remover o arquivo original .opus
        else:
            agi_verbose(f"Erro ao converter para GSM: {converted_audio_path}")

    except ResponseError as e:
        agi_verbose(f"Erro ao baixar áudio {audio_path_minio}: {e}")

# Função para ajustar o nome do ramal
def adjust_channel_name(channel_name):
    # Substitui "_" por "-"
    return channel_name.replace("_", "-")

# Configurações
CHANNEL = sys.argv[1]

# Remove o prefixo (como PJSIP/) e o sufixo (-00000017)
match = re.match(r'^[^/]+/([^-]+(?:-[^-]+)*?)-[\w]+$', CHANNEL)

if match:
    ramal = match.group(1)
else:
    ramal = CHANNEL  # fallback caso não combine

# Ajusta o nome do ramal para substituir "_" por "-"
ramal = adjust_channel_name(ramal)

bucket = f"{ramal}-bucket"  # Altere conforme necessário
endpoint_url = f"http://3.82.106.88:8000/public/chatvoiceqa/{bucket}"

try:
    # Requisição ao endpoint
    response = requests.get(endpoint_url)
    response.raise_for_status()

    # Carrega o conteúdo JSON
    data = response.json()
    chatvoice_id = data.get("chatvoice_id")
    bucket = data["qas"][0]["bucket_minio"]

    agi_set_variable("BUCKET_MINIO", bucket)
    agi_set_variable("CHATVOICE_ID", chatvoice_id)

    if not chatvoice_id:
        agi_verbose("Resposta não contém 'chatvoice_id'. Abortando.")
    else:
        # Conectar ao MinIO
        client = Minio(
            MINIO_ENDPOINT,  # Usando o endereço configurado em configMinio.py
            access_key=MINIO_ACCESS_KEY,  # Usando a chave de acesso configurada
            secret_key=MINIO_SECRET_KEY,  # Usando a chave secreta configurada
            secure=False  # Se estiver usando HTTP, defina como False
        )

        # Salvar o JSON no diretório correto
        audio_dir = os.path.join("/tmp", bucket)  # Diretório onde os áudios serão salvos
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)

        filename = os.path.join(audio_dir, f"data_chatvoice_{chatvoice_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        agi_verbose(f"Arquivo JSON salvo com sucesso: {filename}")

        # Salvar os áudios de gravações
        gravacoes = data.get("gravacoes", {})
        for key, audio_path_minio in gravacoes.items():
            if audio_path_minio:
                download_audio(client, bucket, audio_path_minio)


except requests.exceptions.RequestException as e:
    agi_verbose(f"Erro ao fazer requisição: {e}")
