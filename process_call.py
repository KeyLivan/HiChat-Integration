#!/usr/bin/env python3.6 
import os
import sys
import requests
import subprocess
import time
import json
from minio import Minio
from minio.error import ResponseError
from configMinio import MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ENDPOINT

call_id = sys.argv[1]
caller_number = sys.argv[2]
chatvoice_id = sys.argv[3]
bucket = sys.argv[4].strip()
data = {'asterisk': call_id, 'numero': caller_number}

recorded_audio_wav = f"/tmp/call_{call_id}_in.wav"
recorded_audio_ogg = f"/tmp/call_{call_id}_in.ogg"
received_audio = f"/tmp/call_{call_id}_IA.opus"
converted_audio = f"/tmp/call_{call_id}_out.gsm"
transfer_header_file = f"/tmp/transfer_header_{call_id}.txt"
JSON_FILE_PATH = f"/tmp/variables_{call_id}.json"

def agi_verbose(message):
    sys.stdout.write(f'VERBOSE "{message}" 1\n')
    sys.stdout.flush()

def agi_set_variable(name, value):
    sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
    sys.stdout.flush()

def exit_with_error(msg):
    agi_verbose(f"Saída com erro controlado: {msg}")
    sys.exit(0)

def load_variables():
    try:
        if not os.path.exists(JSON_FILE_PATH):
            agi_verbose("Arquivo JSON não encontrado. Usando valores padrão.")
            return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}
        with open(JSON_FILE_PATH, "r") as file:
            agi_verbose(f"Arquivo JSON carregado: {JSON_FILE_PATH}")
            return json.load(file)
    except Exception as e:
        agi_verbose(f"Erro ao carregar JSON: {str(e)}")
        return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}

def save_variables(variables):
    try:
        with open(JSON_FILE_PATH, "w") as file:
            json.dump(variables, file)
        agi_verbose(f"Variáveis salvas: {JSON_FILE_PATH}")
    except Exception as e:
        agi_verbose(f"Erro ao salvar JSON: {str(e)}")

def increment_empty_body_count(body=False):
    agi_verbose("Iniciando verificação do EMPTY_BODY_COUNT...")
    variables = load_variables()
    empty_body_count = variables.get("EMPTY_BODY_COUNT", 0)
    agi_verbose(f"EMPTY_BODY_COUNT atual: {empty_body_count}")

    if not body:
        agi_verbose("Incrementando EMPTY_BODY_COUNT...")
        if empty_body_count == 2:
            variables["CLOSING"] = True
        elif empty_body_count > 2:
            variables["CLOSING"] = False
            variables["HUNGRUP"] = True
        else:
            variables["CLOSING"] = False
        empty_body_count += 1
        variables["EMPTY_BODY_COUNT"] = empty_body_count
    else:
        agi_verbose("Resetando EMPTY_BODY_COUNT...")
        variables["EMPTY_BODY_COUNT"] = 0
        variables["CLOSING"] = False
        variables["HUNGRUP"] = False

    save_variables(variables)
    sys.stdout.write(f'EMPTY_BODY_COUNT={variables["EMPTY_BODY_COUNT"]}\n')
    sys.stdout.write(f'CLOSING={variables["CLOSING"]}\n')
    sys.stdout.write(f'HUNGRUP={variables["HUNGRUP"]}\n')
    sys.stdout.flush()

def remove_file_if_exists(file_path):
    try:
        if os.path.exists(file_path):
            result = subprocess.run(['rm', '-f', file_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
            if result.returncode == 0:
                agi_verbose(f"Arquivo removido: {file_path}")
            else:
                agi_verbose(f"Erro ao remover {file_path}: {result.stderr}")
    except Exception as e:
        agi_verbose(f"Exceção ao remover {file_path}: {str(e)}")

agi_verbose("Iniciando script AGI e removendo arquivos anteriores...")
remove_file_if_exists(received_audio)
remove_file_if_exists(converted_audio)
remove_file_if_exists(recorded_audio_ogg)

endpoint_url = f"http://147.182.191.150:8000/chatvoices/{chatvoice_id}/base_new"

if os.path.exists(recorded_audio_wav):
    agi_verbose(f"Arquivo de entrada encontrado: {recorded_audio_wav}")
    try:
        start_time = time.time()
        agi_verbose("iniciando request.")
        with open(recorded_audio_wav, 'rb') as audio_file:
            files = {'file': audio_file}
            response = requests.post(endpoint_url, files=files, data=data)

        elapsed_time = time.time() - start_time
        agi_verbose(f"Tempo da requisição: {elapsed_time:.2f}s")
        agi_verbose(f"Status HTTP: {response.status_code}")

        if response.status_code != 200:
            increment_empty_body_count()
            exit_with_error(f"Erro HTTP: {response.status_code}")

        try:
            json_response = response.json()
            agi_verbose(f"Resposta JSON recebida: {json_response}")

            # Verifica se existe o campo transferencia_confirmada
            transferencia = json_response.get("transferencia_confirmada")
            if transferencia is not None:
                agi_set_variable("TRANSFER_CONFIRMADA", str(transferencia).lower())
                agi_verbose(f"Variável TRANSFER_CONFIRMADA setada: {transferencia}")

            audio_path = json_response.get("audio_path_minio")
            if audio_path and audio_path.startswith("minio://"):
                agi_verbose("Extraindo caminho do MinIO...")

                # Extrair caminho do MinIO
                minio_path = audio_path.replace("minio://", "")
                parts = minio_path.split("/", 1)
                if len(parts) != 2:
                    agi_verbose("Formato inválido de audio_path_minio.")
                    exit_with_error("Formato inválido de audio_path_minio")

                bucket_name, object_path = parts
                local_opus_path = f"/tmp/{call_id}_downloaded.opus"

                agi_verbose(f"Bucket: {bucket_name}")
                agi_verbose(f"Objeto: {object_path}")

                try:
                    client = Minio(
                        MINIO_ENDPOINT,
                        access_key=MINIO_ACCESS_KEY,
                        secret_key=MINIO_SECRET_KEY,
                        secure=False
                    )
                    client.fget_object(bucket_name, object_path, local_opus_path)
                    agi_verbose(f"Áudio baixado com sucesso: {local_opus_path}")
                except S3Error as e:
                    agi_verbose(f"Erro ao baixar do MinIO: {str(e)}")
                    exit_with_error("Falha ao baixar o áudio do MinIO")

                # Converter OPUS para GSM
                conversion_result = subprocess.run(
                    ['ffmpeg', '-i', local_opus_path, '-ar', '8000', '-ac', '1', '-b:a', '13k', '-c:a', 'gsm', converted_audio],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
                )

                if conversion_result.returncode == 0:
                    agi_verbose(f"Áudio convertido com sucesso: {converted_audio}")
                    increment_empty_body_count(True)
                    sys.exit(0)
                else:
                    agi_verbose(f"Erro ao converter o áudio: {conversion_result.stderr}")
                    exit_with_error("Falha ao converter o áudio para GSM")

            else:
                agi_verbose("Resposta JSON não contém o campo audio_path_minio.")
                increment_empty_body_count()
                exit_with_error("Resposta JSON inválida")

        except json.JSONDecodeError:
            agi_verbose("Resposta não é JSON, tentando usar como binário de áudio...")
            if response.content:
                with open(received_audio, 'wb') as f:
                    f.write(response.content)

                transcricao = response.headers.get('transcricao')
                resposta_formatada = response.headers.get('resposta_formatada')
                transfer_value = response.headers.get('Transfer')

                if transfer_value:
                    with open(transfer_header_file, 'w') as f:
                        f.write(transfer_value)
                    agi_verbose(f"Header Transfer salvo: {transfer_value}")

                agi_verbose(f"Transcrição: {transcricao}")
                agi_verbose(f"Resposta formatada: {resposta_formatada}")

                if os.path.exists(received_audio) and os.path.getsize(received_audio) > 0:
                    agi_verbose("Convertendo resposta OPUS para GSM...")
                    conversion_result = subprocess.run(
                        ['ffmpeg', '-i', received_audio, '-ar', '8000', '-ac', '1', '-b:a', '13k', '-c:a', 'gsm', converted_audio],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
                    )
                    if conversion_result.returncode == 0:
                        agi_verbose(f"Resposta convertida com sucesso para GSM: {converted_audio}")
                    else:
                        agi_verbose(f"Erro ao converter para GSM: {conversion_result.stderr}")
                else:
                    agi_verbose("Arquivo de resposta vazio ou ausente.")
    except Exception as e:
        agi_verbose(f"Erro inesperado durante processamento: {str(e)}")
        exit_with_error("Exceção no processamento")
else:
    agi_verbose("Arquivo de entrada não encontrado ou está vazio.")
    exit_with_error("Sem áudio para processar")

agi_verbose("Execução do AGI finalizada com sucesso.")
sys.exit(0)
