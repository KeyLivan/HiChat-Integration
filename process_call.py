#!/usr/bin/env python3.6 
import os
import sys
import requests
import json
from minio import Minio
from minio.error import S3Error
from configMinio import MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_ENDPOINT

call_id = sys.argv[1]
caller_number = sys.argv[2]
chatvoice_id = sys.argv[3]
bucket = sys.argv[4].strip()
data = {'asterisk': call_id, 'numero': caller_number}

recorded_audio_wav = f"/tmp/call_{call_id}_in.wav"
output_audio_gsm = f"/tmp/call_{call_id}_out.gsm"
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
    """Carrega variáveis de estado do arquivo JSON."""
    try:
        if not os.path.exists(JSON_FILE_PATH):
            return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}
        with open(JSON_FILE_PATH, "r") as file:
            return json.load(file)
    except Exception as e:
        agi_verbose(f"Erro ao carregar JSON: {str(e)}")
        return {"EMPTY_BODY_COUNT": 0, "CLOSING": False, "HUNGRUP": False}


def save_variables(variables):
    """Salva variáveis de estado no arquivo JSON."""
    try:
        with open(JSON_FILE_PATH, "w") as file:
            json.dump(variables, file)
    except Exception as e:
        agi_verbose(f"Erro ao salvar JSON: {str(e)}")


def update_empty_body_count(has_response=False):
    """
    Atualiza contador de respostas vazias e seta variáveis AGI.
    - has_response=True: reseta contador (resposta recebida)
    - has_response=False: incrementa contador (sem resposta)
    """
    variables = load_variables()
    empty_count = variables.get("EMPTY_BODY_COUNT", 0)

    if has_response:
        # Resposta recebida - reseta tudo
        variables["EMPTY_BODY_COUNT"] = 0
        variables["CLOSING"] = False
        variables["HUNGRUP"] = False
    else:
        # Sem resposta - incrementa
        empty_count += 1
        variables["EMPTY_BODY_COUNT"] = empty_count
        
        if empty_count == 3:
            variables["CLOSING"] = True
            variables["HUNGRUP"] = False
        elif empty_count > 3:
            variables["CLOSING"] = False
            variables["HUNGRUP"] = True
        else:
            variables["CLOSING"] = False
            variables["HUNGRUP"] = False

    save_variables(variables)
    
    # Seta variáveis no Asterisk via AGI
    agi_set_variable("CLOSING", str(variables["CLOSING"]))
    agi_set_variable("HUNGRUP", str(variables["HUNGRUP"]))
    
    agi_verbose(f"EMPTY_BODY_COUNT={variables['EMPTY_BODY_COUNT']}, CLOSING={variables['CLOSING']}, HUNGRUP={variables['HUNGRUP']}")


def remove_file_if_exists(file_path):
    """Remove arquivo se existir."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            agi_verbose(f"Arquivo removido: {file_path}")
    except Exception as e:
        agi_verbose(f"Erro ao remover {file_path}: {str(e)}")


def download_audio_from_minio(audio_path_minio):
    """
    Baixa áudio GSM do MinIO para o arquivo de saída.
    Retorna True se sucesso, False caso contrário.
    """
    if not audio_path_minio.startswith("minio://"):
        agi_verbose(f"Formato inválido de audio_path: {audio_path_minio}")
        return False

    minio_path = audio_path_minio.replace("minio://", "")
    parts = minio_path.split("/", 1)
    
    if len(parts) != 2:
        agi_verbose("Formato inválido de audio_path_minio.")
        return False

    bucket_name, object_path = parts
    agi_verbose(f"Baixando do MinIO - Bucket: {bucket_name}, Objeto: {object_path}")

    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )
        client.fget_object(bucket_name, object_path, output_audio_gsm)
        
        size = os.path.getsize(output_audio_gsm)
        if size == 0:
            agi_verbose("Arquivo baixado está vazio!")
            return False
            
        agi_verbose(f"Áudio GSM baixado com sucesso: {output_audio_gsm} ({size} bytes)")
        return True
        
    except S3Error as e:
        agi_verbose(f"Erro ao baixar do MinIO: {str(e)}")
        return False
    except Exception as e:
        agi_verbose(f"Erro inesperado ao baixar do MinIO: {str(e)}")
        return False


# --- INÍCIO DO PROCESSAMENTO ---
agi_verbose("Iniciando script AGI process_call...")

# Limpa arquivos anteriores
remove_file_if_exists(output_audio_gsm)

endpoint_url = f"http://147.182.191.150:8000/chatvoices/{chatvoice_id}/base_new"

if not os.path.exists(recorded_audio_wav):
    agi_verbose("Arquivo de entrada não encontrado.")
    update_empty_body_count(has_response=False)
    exit_with_error("Sem áudio para processar")

agi_verbose(f"Arquivo de entrada: {recorded_audio_wav}")
input_size = os.path.getsize(recorded_audio_wav)
agi_verbose(f"Tamanho do arquivo de entrada: {input_size} bytes")

if input_size == 0:
    agi_verbose("ERRO: Arquivo de entrada está vazio!")
    update_empty_body_count(has_response=False)
    exit_with_error("Arquivo de entrada vazio")

try:
    # Envia áudio para a API
    agi_verbose(f"Enviando áudio para a API: {endpoint_url}")
    with open(recorded_audio_wav, 'rb') as audio_file:
        files = {'file': audio_file}
        response = requests.post(endpoint_url, files=files, data=data, timeout=30)

    agi_verbose(f"Status HTTP: {response.status_code}")
    agi_verbose(f"Response Headers: {dict(response.headers)}")
    agi_verbose(f"Response Body (primeiros 500 chars): {response.text[:500]}")

    if response.status_code != 200:
        update_empty_body_count(has_response=False)
        exit_with_error(f"Erro HTTP: {response.status_code}")

    # Processa resposta JSON
    json_response = response.json()
    agi_verbose(f"Resposta JSON completa: {json_response}")

    # Verifica transferência confirmada
    transferencia = json_response.get("transferencia_confirmada")
    if transferencia is not None:
        agi_set_variable("TRANSFER_CONFIRMADA", str(transferencia).lower())
        agi_verbose(f"TRANSFER_CONFIRMADA = {transferencia}")

    # Obtém caminho do áudio
    audio_path = json_response.get("audio_path_minio")
    
    if not audio_path:
        agi_verbose("Resposta não contém audio_path_minio.")
        update_empty_body_count(has_response=False)
        exit_with_error("Resposta sem áudio")

    # Baixa áudio GSM do MinIO
    if download_audio_from_minio(audio_path):
        update_empty_body_count(has_response=True)
        agi_verbose("Processamento concluído com sucesso!")
    else:
        update_empty_body_count(has_response=False)
        exit_with_error("Falha ao baixar áudio do MinIO")

except json.JSONDecodeError:
    agi_verbose("Resposta não é JSON válido.")
    update_empty_body_count(has_response=False)
    exit_with_error("Resposta inválida da API")

except requests.exceptions.RequestException as e:
    agi_verbose(f"Erro de conexão: {str(e)}")
    update_empty_body_count(has_response=False)
    exit_with_error("Erro de conexão com a API")

except Exception as e:
    agi_verbose(f"Erro inesperado: {str(e)}")
    update_empty_body_count(has_response=False)
    exit_with_error("Erro inesperado")

sys.exit(0)
