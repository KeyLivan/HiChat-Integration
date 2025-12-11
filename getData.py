#!/usr/bin/env python3.6
import requests
import json
import os
import sys
import re
from minio import Minio
from minio.error import ResponseError
from configMinio import MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ENDPOINT


def agi_verbose(message):
    sys.stdout.write(f'VERBOSE "{message}" 1\n')
    sys.stdout.flush()

def agi_set_variable(name, value):
    sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
    sys.stdout.flush()

def download_audio(client, bucket_minio, audio_path_minio):
    """Baixa áudio GSM do MinIO para o diretório local."""
    audio_dir = os.path.join("/tmp", bucket_minio)
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    local_audio_path = os.path.join(audio_dir, audio_path_minio)

    try:
        # Remove arquivo existente se houver
        if os.path.exists(local_audio_path):
            os.remove(local_audio_path)

        # Baixa o áudio GSM do MinIO
        client.fget_object(bucket_minio, audio_path_minio, local_audio_path)
        
        size = os.path.getsize(local_audio_path)
        if size == 0:
            agi_verbose(f"Arquivo está vazio: {local_audio_path}")
            return False

        agi_verbose(f"Áudio baixado: {local_audio_path} ({size} bytes)")
        return True

    except ResponseError as e:
        agi_verbose(f"Erro ao baixar áudio {audio_path_minio}: {e}")
        return False
    except Exception as e:
        agi_verbose(f"Erro inesperado ao processar áudio {audio_path_minio}: {e}")
        return False


def adjust_channel_name(channel_name):
    return channel_name.replace("_", "-")

# --- INÍCIO DO SCRIPT ---
CHANNEL = sys.argv[1]

match = re.match(r'^[^/]+/([^-]+(?:-[^-]+)*?)-[\w]+$', CHANNEL)
ramal = match.group(1) if match else CHANNEL
ramal = adjust_channel_name(ramal)
bucket = f"{ramal}bucket"

agi_verbose(f"Bucket usado: {bucket}")
endpoint_url = f"http://147.182.191.150:8000/public/chatvoice/{bucket}"

try:
    response = requests.get(endpoint_url)
    response.raise_for_status()
    data = response.json()
    chatvoice_id = data.get("chatvoice_id")

    agi_set_variable("BUCKET_MINIO", bucket)
    agi_set_variable("CHATVOICE_ID", chatvoice_id)

    if not chatvoice_id:
        agi_verbose("Resposta não contém 'chatvoice_id'. Abortando.")
    else:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )

        audio_dir = os.path.join("/tmp", bucket)
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)

        filename = os.path.join(audio_dir, f"data_chatvoice_{chatvoice_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        agi_verbose(f"Arquivo JSON salvo com sucesso: {filename}")

        gravacoes = data.get("gravacoes", {})
        for key, audio_path_minio in gravacoes.items():
            if audio_path_minio:
                download_audio(client, bucket, audio_path_minio)

        form_list = data.get("form", [])
        ultimo_audio = None

        for form_item in form_list:
            audio_path_minio = form_item.get("audio_path")
            if audio_path_minio:
                if download_audio(client, bucket, audio_path_minio):
                    ultimo_audio = audio_path_minio

        if ultimo_audio:
            agi_set_variable("ULTIMO_AUDIO", ultimo_audio)

        for idx, form_item in enumerate(form_list):
            audio_path_minio = form_item.get("audio_path")
            form_type = form_item.get("type")
            if audio_path_minio and form_type:
                # Remove extensão para o Asterisk (ele adiciona .gsm automaticamente)
                audio_base = os.path.splitext(audio_path_minio)[0]
                agi_set_variable(f"FORM_AUDIO_{idx}", audio_base)
                agi_set_variable(f"FORM_TYPE_{idx}", form_type)

        agi_set_variable("FORM_COUNT", str(len(form_list)))

except requests.exceptions.RequestException as e:
    agi_verbose(f"Erro ao fazer requisição: {e}")

agi_verbose("Script executado com sucesso")
