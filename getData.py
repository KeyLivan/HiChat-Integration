#!/usr/bin/env python3.6
import json
import requests
import sys
import os
from minio import Minio
from minio.error import S3Error

def ensure_dir(path):
    """Cria o diretório se ele não existir."""
    if not os.path.exists(path):
        os.makedirs(path)

def collect_and_save_data(url, dataAsterisk, params=None, headers=None):
    """
    Faz uma requisição HTTP para coletar dados e salva em um arquivo JSON no diretório /tmp.

    :return: Caminho do arquivo JSON gerado
    """
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        output_file = f"/tmp/data_{dataAsterisk['trunk']}.json"
        with open(output_file, "w") as json_file:
            json.dump(data, json_file, indent=4)

        print(f"[✓] Dados salvos com sucesso em: {output_file}")
        return output_file

    except requests.exceptions.RequestException as e:
        print(f"[x] Erro na requisição: {e}")
    except ValueError as e:
        print(f"[x] Erro ao processar resposta como JSON: {e}")
    except IOError as e:
        print(f"[x] Erro ao salvar arquivo JSON: {e}")

def download_audios(bucket_name, object_names):
    """
    Baixa múltiplos arquivos do MinIO para uma pasta local baseada no nome do bucket.
    """
    try:
        minio_client = Minio(
            endpoint="localhost:9000",  # Altere se necessário
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )

        output_dir = os.path.join("/temp", bucket_name)
        ensure_dir(output_dir)

        if not minio_client.bucket_exists(bucket_name):
            print(f"[x] Bucket '{bucket_name}' não encontrado.")
            return

        for object_name in object_names:
            output_path = os.path.join(output_dir, object_name)
            try:
                minio_client.fget_object(bucket_name, object_name, output_path)
                print(f"[✓] Baixado: {object_name}")
            except S3Error as e:
                print(f"[x] Erro ao baixar '{object_name}': {e}")

        print(f"[✓] Todos os áudios salvos em: {output_dir}")

    except Exception as e:
        print(f"[x] Falha geral: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Uso: ./baixar_audios.py <call_id> <caller_number> <trunk_name> <api_url>")
        sys.exit(1)

    call_id = sys.argv[1]
    caller_number = sys.argv[2]
    trunk_name = sys.argv[3]
    api_url = sys.argv[4]

    dataAsterisk = {
        "id": call_id,
        "numero": caller_number,
        "trunk": trunk_name
    }

    # 1. Coletar os dados e salvar JSON
    json_path = collect_and_save_data(api_url, dataAsterisk)

    # 2. Ler o JSON salvo e baixar os áudios do MinIO
    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                payload = json.load(f)
                bucket_name = payload.get("bucket_name")
                object_names = payload.get("object_names", [])

                if bucket_name and object_names:
                    download_audios(bucket_name, object_names)
                else:
                    print("[x] JSON inválido: 'bucket_name' ou 'object_names' ausente.")
        except Exception as e:
            print(f"[x] Erro ao processar o JSON: {e}")
