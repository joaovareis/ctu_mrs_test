#!/bin/bash

# Determina a pasta onde o script está
SCRIPT_DIR=$(dirname "$(realpath "$0")")

# Como o .env está na mesma pasta, a raiz de busca passa a ser o próprio SCRIPT_DIR
PROJECT_ROOT="$SCRIPT_DIR"

# Carrega as variáveis de ambiente definidas no arquivo .env, ignorando linhas comentadas
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
else
    echo "Arquivo .env não encontrado em: $PROJECT_ROOT"
    exit 1
fi

# Define o nome da imagem Docker
IMAGE_NAME="imav_26"

# Constrói a imagem Docker utilizando os argumentos de build necessários
docker build --build-arg GIT_USER_EMAIL="$GIT_USER_EMAIL" \
             --build-arg GIT_USER_NAME="$GIT_USER_NAME" \
             --build-arg GITHUB_TOKEN="$GITHUB_TOKEN" \
             -t "$IMAGE_NAME" \
             -f "$SCRIPT_DIR/Dockerfile" \
             "$PROJECT_ROOT"
             
# Exibe mensagem de sucesso
echo "Imagem '$IMAGE_NAME' construída com sucesso!"
