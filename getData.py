#!/usr/bin/env python3.6
import requests
import json
import os
import sys
import re
import subprocess
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
    audio_dir = os.path.join("/tmp", bucket_minio)
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)

    original_audio_path = os.path.join(audio_dir, audio_path_minio)
    converted_audio_path = os.path.splitext(original_audio_path)[0] + ".gsm"

    try:
        if os.path.exists(original_audio_path):
            os.remove(original_audio_path)
        if os.path.exists(converted_audio_path):
            os.remove(converted_audio_path)

        client.fget_object(bucket_minio, audio_path_minio, original_audio_path)
        agi_verbose(f"Áudio baixado: {original_audio_path}")

        size = os.path.getsize(original_audio_path)
        if size == 0:
            agi_verbose(f"Arquivo .opus está vazio: {original_audio_path}")
            return

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", original_audio_path,
            "-ar", "8000", "-ac", "1", "-ab", "13k", converted_audio_path
        ]
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            agi_verbose(f"Áudio convertido para GSM: {converted_audio_path}")
            os.remove(original_audio_path)
        else:
            agi_verbose(f"Erro ao converter {original_audio_path}:\n{result.stderr.decode('utf-8')}")

    except ResponseError as e:
        agi_verbose(f"Erro ao baixar áudio {audio_path_minio}: {e}")
    except Exception as e:
        agi_verbose(f"Erro inesperado ao processar áudio {audio_path_minio}: {e}")


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

bucket = f"{ramal}bucket"  # Altere conforme necessário
agi_verbose(f"Bucket usado: {bucket}")
endpoint_url = f"http://3.82.106.88:8000/public/chatvoice/{bucket}"

try:
    # Requisição ao endpoint
    response = requests.get(endpoint_url)
    response.raise_for_status()

    # Carrega o conteúdo JSON
    data = response.json()
    chatvoice_id = data.get("chatvoice_id")

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

        # Salvar os áudios do formulário e setar variável AGI com o último áudio
        form_list = data.get("form", [])
        ultimo_audio = None

        for form_item in form_list:
            audio_path_minio = form_item.get("audio_path")
            if audio_path_minio:
                download_audio(client, bucket, audio_path_minio)
                ultimo_audio = audio_path_minio  # Atualiza para o último arquivo encontrado

        if ultimo_audio:
            agi_set_variable("ULTIMO_AUDIO", ultimo_audio)

        # Adiciona variáveis para cada áudio e tipo do formulário (para o dialplan)
        for idx, form_item in enumerate(form_list):
            audio_path_minio = form_item.get("audio_path")
            form_type = form_item.get("type")
        
            if audio_path_minio and form_type:
                # Define o nome convertido para .gsm
                converted_audio_path = os.path.splitext(audio_path_minio)[0]
                
                agi_set_variable(f"FORM_AUDIO_{idx}", converted_audio_path)
                agi_set_variable(f"FORM_TYPE_{idx}", form_type)


        agi_set_variable("FORM_COUNT", str(len(form_list)))

except requests.exceptions.RequestException as e:
    agi_verbose(f"Erro ao fazer requisição: {e}")

agi_verbose("Script executado com sucesso")
